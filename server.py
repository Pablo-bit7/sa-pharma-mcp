#!/usr/bin/env python3
"""
MCP server for South African pharma intelligence.

This module exposes a FastMCP server with tools that query public SAHPRA
endpoints to retrieve licensed establishment lists and registered product
records. The server is stateless over HTTP and returns Markdown tables.

Tools:
- `get_licensed_companies`: Fetches official establishment lists by category.
- `search_sahpra_products`: Searches registered products by company name.
- `analyse_ndoh_market`: Analyses the NDoH Master Health Product List for
    public sector procurement trends, pricing, and supplier market share.
- `analyse_private_market`: Analyses the Single Exit Price (MPR) database
    for private sector pricing, molecule competitiveness, and applicant presence.
"""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sahpra_utils import get_sahpra_nonce
from mhpl_utils import get_latest_ndoh_prod_list_df
from mpr_utils import get_latest_mpr_list_df
import httpx
import pandas
import os
import sys


mcp = FastMCP(
    "za-pharma-intelligence",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
)


@mcp.tool()
async def get_licensed_companies(category: str = "Manufacturers & Packers", limit: int = 50, offset: int = 0) -> str:
    """
    Use this to retrieve the official SAHPRA list of establishments for a specific catagory.

    :param category: Valid options:
        'API Manufacturers', 'Bond Stores',
        'Cannabis Cultivation Licences', 'Distribution of Scheduled Substances',
        'Gas Manufacturers', 'Holders of Certificate of Product Registration',
        'Manufacturers & Packers', 'Private Only Wholesalers',
        'Provincial Depots', 'Testing Laboratories'.
    :type category: str
    :param limit: Number of records to return per page. Max recommended is 100 to save context window.
    :type limit: int
    :param offset: Number of records to skip for pagination.
    :type offset: int
    :return: A markdown table containing the first 50 licensed establishments for the requested category.
    :rtype: str
    """
    API_URL = "https://www.sahpra.org.za/wp-admin/admin-ajax.php"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://www.sahpra.org.za/approved-licences/",
        "X-Requested-With": "XMLHttpRequest"
    }

    TABLE_MAP = {
        "API Manufacturers": "6964",
        "Bond Stores": "6972",
        "Cannabis Cultivation Licences": "6591",
        "Distribution of Scheduled Substances": "6868",
        "Gas Manufacturers": "9444",
        "Holders of Certificate of Product Registration": "7144",
        "Manufacturers & Packers": "6968",
        "Private Only Wholesalers": "6974",
        "Provincial Depots": "6970",
        "Testing Laboratories": "7872"
    }

    table_id = TABLE_MAP.get(category)
    if not table_id:
        return f"Error: The category `{category}` was not found."

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        try:
            nonce = await get_sahpra_nonce(client)

            print(f"DEBUG: Using nonce {nonce} for category '{category}'", file=sys.stderr)

            params = {
                "action": "wp_ajax_ninja_tables_public_action",
                "table_id": table_id,
                "target_action": "get-all-data",
                "default_sorting": "old_first",
                "skip_rows": "0", # Fetch all
                "limit_rows": "0",
                "ninja_table_public_nonce": nonce
            }

            response = await client.get(API_URL, params=params, headers=headers)
            response.raise_for_status()

            raw_data = response.json()
            if not raw_data:
                return f"No records for `{category}`"
            
            clean_data = [row.get("value", {}) for row in raw_data]
            
            df = pandas.DataFrame(clean_data)
            total_records = len(df)

            # Slice dataframe based on pagination parameters
            paginated_df = df.iloc[offset: offset + limit]
            meta_info = f"**Category** {category} | **Showing** {offset + 1} - {min(offset + limit, total_records)} of {total_records}\n\n"

            return meta_info + paginated_df.to_markdown(index=False)

        except Exception as e:
            return f"Failed to retrieve companies: {str(e)}"


@mcp.tool()
async def search_sahpra_products(company_name: str, limit: int = 15, offset: int = 0) -> str:
    """
    Use this to search the SAHPRA website database table for health products
    registered to a specific company.
    
    :param company_name: The name of the applicant or company to search for (e.g., 'Cipla', 'Aspen').
    :type company_name: str
    :param limit: Number of products to return per page.
    :type limit: int
    :param offset: Number of products to skip for pagination.
    :type offset: int
    :return: A markdown table of matching registered products, or a 'No products found' message.
    :rtype: str
    """
    API_URL = "https://medapps.sahpra.org.za:6006/Home/getData"

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://medapps.sahpra.org.za:6006",
    "Referer": "https://medapps.sahpra.org.za:6006/",
    "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    }

    payload = {
        "draw": "1",
        "start": str(offset),
        "length": str(limit),
        "search[value]": company_name,
        "search[regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc"
    }

    columns = ["applicantName", "productName", "api", "licence_no", "application_no", "reg_date", "status", "secureId"]
    for i, column_name in enumerate(columns):
        payload[f"columns[{i}][data]"] = column_name
        payload[f"columns[{i}][name]"] = column_name if column_name != "secureId" else ""
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = "true"
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        try:
            response = await client.post(API_URL, data=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            total_records = data.get("recordsFiltered", 0)
            df = pandas.DataFrame(data["data"])

            if df.empty:
                return f"No products found for '{company_name}'"
            
            display_map = {
                "applicantName": "Company",
                "productName": "Product",
                "licence_no": "Reg No.",
                "reg_date": "Date"
            }

            meta_info = f"**Search:** {company_name} | **Showing:** {offset + 1} - {min(offset + limit, total_records)} of {total_records}\n\n"
            
            return meta_info + df[list(display_map.keys())].rename(columns=display_map).to_markdown(index=False)

        except Exception as e:
            return f"Search failed: {str(e)}"


@mcp.tool()
async def analyse_ndoh_market(
    query: str = None,
    filter_type: str = "all",
    aggregate_by: str = None,
    sort_by: str = "Unit_Price",
    limit: int = 15,
    offset: int = 0
) -> str:
    """
    Use this to analyse the NDoH Master Health Product List for the South African
    public sector. Provides real-time procurement data, pricing, and market
    share.

    :param query: Text to search for (e.g., "Aspirin", "J05", "Cipla").
    :type query: str
    :param filter_type: Where to look. Valid options: "inn", "supplier", "atc", "all".
    :type filter_type: str
    :param aggregate_by: Set to "Supplier", "INN", or "Care_Level" for summarized statistics.
    :type aggregate_by: str
    :param sort_by: Column to sort by. Valid options: "Unit_Price", "Quantity_Awarded", "Contract_Expiry".
    :type sort_by: str
    :param limit: Number of rows to return per page (default 15). Keep low to save context window.
    :type limit: int
    :param offset: Number of rows to skip for pagination.
    :type offset: int
    :return: A markdown table containing the analysis results.
    :rtype: str
    """
    df = await get_latest_ndoh_prod_list_df()

    df["Unit_Price"] = pandas.to_numeric(df["Unit_Price"], errors="coerce").fillna(0)
    df["Quantity_Awarded"] = pandas.to_numeric(df["Quantity_Awarded"], errors="coerce").fillna(0)
    df["Award_Value"] = df["Unit_Price"] * df["Quantity_Awarded"]
    df["Contract_Expiry"] = pandas.to_datetime(df["Contract_Expiry"], errors="coerce")
    df["Days_Remaining"] = (df["Contract_Expiry"] - pandas.Timestamp.now()).dt.days

    if query:
        if filter_type == "inn":
            df = df[df["INN"].str.contains(query, case=False, na=False)]
        elif filter_type == "supplier":
            df = df[df["Supplier"].str.contains(query, case=False, na=False)]
        elif filter_type == "atc":
            df = df[df["ATC_Code"].str.startswith(query.upper(), na=False)]
        else:
            mask = df.apply(lambda x: x.astype(str).str.contains(query, case=False).any(), axis=1)
            df = df[mask]

    if df.empty:
        return f"No procurement data found for `{query}` with filter `{filter_type}`."
    
    total_records = len(df)

    if aggregate_by and aggregate_by in df.columns:
        summary = df.groupby(aggregate_by).agg({
            "Contract": "count",
            "Award_Value": "sum",
            "Quantity_Awarded": "sum",
            "Unit_Price": ["min", "max", "mean"],
            "Days_Remaining": "mean"
        }).reset_index()

        summary.columns = [
            aggregate_by,
            "Contracts", "Total_Value_ZAR", "Total_Qty",
            "Min_Price", "Max_Price", "Avg_Price", "Avg_Days_Left"
        ]
        summary = summary.sort_values(by="Total_Value_ZAR", ascending=False)

        paginated_summary = summary.iloc[offset : offset + limit]
        meta_info = f"**Aggregate Analysis by {aggregate_by}** | Showing {offset + 1} - {min(offset + limit, len(summary))} of {len(summary)}\n\n"

        return meta_info + paginated_summary.to_markdown(index=False)
    
    df = df.sort_values(by=sort_by, ascending=(sort_by == "Unit_Price"))

    paginated_df = df.iloc[offset : offset + limit]
    meta_info = f"**Granular Contract View** | Showing {offset + 1} - {min(offset + limit, total_records)} of {total_records}\n\n"

    return meta_info + paginated_df.to_markdown(index=False)


@mcp.tool()
async def analyse_private_market(
    query: str = None,
    filter_type: str = "all",
    aggregate_by: str = None,
    sort_by: str = "SEP",
    limit: int = 15,
    offset: int = 0
) -> str:
    """
    Use this to analyse the Database of Medicine Prices (MPR) for South
    African private sector pricing, molecule competetiveness, and applicant
    presence.

    :param query: Text to search for (e.g., "Paracetamol", "Cipla").
    :type query: str
    :param filter_type: Where to look. Valid options: "active_ingredient", "applicant", "nappi", "all".
    :type filter_type: str
    :param aggregate_by: Set to "Applicant" or "Active_Ingredient" for summarized statistics.
    :type aggregate_by: str
    :param sort_by: Column to sort by. Valid options: "SEP", "Manufacturer_Price".
    :type sort_by: str
    :param limit: Number of rows to return per page (default 15). Keep low to save context window.
    :type limit: int
    :param offset: Number of rows to skip for pagination.
    :type offset: int
    :return: A markdown table containing the analysis results.
    :rtype: str
    """
    df, doc_date, is_live = await get_latest_mpr_list_df()

    status = "[LIVE]" if is_live else "[CACHE]"
    freshness_info = f"Source: {doc_date}{status}"

    df["SEP"] = pandas.to_numeric(df["SEP"], errors="coerce").fillna(0)
    df["Manufacturer_Price"] = pandas.to_numeric(df["Manufacturer_Price"], errors="coerce").fillna(0)
    df["Effective_Date"] = pandas.to_datetime(df["Effective_Date"], format='mixed', errors="coerce")

    df = df[df["SEP"] > 0] # Filter out placeholder rows where SEP is 0.
    df["Price_Age_Days"] = (pandas.Timestamp.now() - df["Effective_Date"]).dt.days

    if query:
        if filter_type == "active_ingredient":
            df = df[df["Active_Ingredient"].str.contains(query, case=False, na=False)]
        elif filter_type == "applicant":
            df = df[df["Applicant"].str.contains(query, case=False, na=False)]
        elif filter_type == "nappi":
            df = df[df["NAPPI_Code"].str.startswith(query.upper(), na=False)]
        else:
            mask = df.apply(lambda x: x.astype(str).str.contains(query, case=False).any(), axis=1)
            df = df[mask]
    
    if df.empty:
        return f"No private sector data found for `{query}` with filter `{filter_type}`."
    
    total_records = len(df)
    
    if aggregate_by and aggregate_by in df.columns:
        summary = df.groupby(aggregate_by).agg({
            "Proprietery_Name": "count",
            "SEP": ["min", "max", "mean"],
            "Manufacturer_Price": ["min", "max", "mean"],
            "Price_Age_Days": "mean"
        }).reset_index()
    
        summary.columns = [
            aggregate_by,
            "Total_Products",
            "Min_SEP", "Max_SEP", "Avg_SEP",
            "Min_Mfg_Price", "Max_Mfg_Price", "Avg_Mfg_Price",
            "Avg_Price_Age_Days"
        ]
        summary = summary.sort_values(by="Total_Products", ascending=False)

        paginated_summary = summary.iloc[offset : offset + limit]
        meta_info = (
            f"**Aggregate Private Market Analysis by {aggregate_by}**\n"
            f"{freshness_info} | Showing {offset + 1} - {min(offset + limit, len(summary))} of {len(summary)}\n\n"
        )

        return meta_info + paginated_summary.to_markdown(index=False)
    
    df = df.sort_values(by=sort_by if sort_by in df.columns else "SEP", ascending=True)

    paginated_df = df.iloc[offset : offset + limit]
    meta_info = (
        f"**Granular Private Sector View**\n"
        f"{freshness_info} | Showing {offset + 1} - {min(offset + limit, total_records)} of {total_records}\n\n"
    )

    return meta_info + paginated_df.to_markdown(index=False)


@mcp.prompt()
def supplier_integrity_audit(company: str) -> str:
    """
    Standardized workflow to audit a supplier's public sector footprint against
    their regulatory standing using multi-page data validation.
    """
    return f"""
    Perform a multi-source integrity audit for: {company}

    1. **Tender Footprint:** Use 'analyse_ndoh_market' (filter_type='supplier'). 
       **Data Integrity Rule:** If the metadata shows more than one page (e.g., 'Showing 1-15 of 45'), you MUST use the `offset` parameter to fetch all subsequent pages. Calculate the absolute 'Total Award Value' only after all records are retrieved.
    2. **Regulatory Check:** Verify license status in 'get_licensed_companies'.
    3. **Product Portfolio:** Use 'search_sahpra_products' to list their registered medicines.
    
    **Visual Render Protocol:** Generate a 'Supplier Risk Scorecard'. 
    Map their listed molecules against their won tenders visually. Use a color-coded matrix (green for matched, red for discrepancy). 
    **Metadata Note:** Explicitly state in the scorecard that the audit covers 100% of the {company} records found across the {company} datasets.
    """


@mcp.prompt()
def therapeutic_category_assessment(atc_code: str) -> str:
    """
    Analyzes a therapeutic class (e.g., J05) to identify dominance and supply risk.
    """
    return f"""
    Analyze the market landscape for Therapeutic Class (ATC): {atc_code}

    1. **Market Size & Concentration:** Use 'analyse_ndoh_market' (filter_type='atc', aggregate_by='INN'). 
    2. **Dominance Check:** Use 'analyse_ndoh_market' (filter_type='atc', aggregate_by='Supplier').
       **Pagination Rule:** If the category is vast, fetch at least the first 3 pages (45 records) to ensure mid-tier suppliers are not ignored in your concentration analysis.
    3. **Renewal Pipeline:** Analyze the 'Avg_Days_Left' for top suppliers.
    
    **Visual Render Protocol:** Create an SVG pie chart showing the market share of the top 5 dominant suppliers. 
    Render a visual 'Stability Rating' meter. If the 'Avg_Days_Left' for the #1 supplier is < 90 days, flag the category as "High Renewal Risk" in red.
    """


@mcp.prompt()
def market_entry_scouting(molecule_name: str) -> str:
    """
    Assess the viability of entering the market with a new generic product.
    """
    return f"""
    I am scouting the market for a potential new entry of: {molecule_name}

    1. **State Demand:** Use 'analyse_ndoh_market' (filter_type='inn') to find the 'Avg_Price' and 'Quantity_Awarded'.
    2. **Competitive Density:** Use 'search_sahpra_products' with the molecule name. 
       **Data Valve Logic:** You must retrieve the FULL list of registered competitors. If the metadata shows 'Showing 1-15 of 60', scroll through all 4 pages.
    
    **Visual Render Protocol:** Execute a 'Gap Analysis' dashboard. 
    Use a quadrant plot: X-axis = Number of Registered Competitors (SAHPRA), Y-axis = Total State Spend (NDoH). 
    Position {molecule_name} on this plot to show if the market is saturated or a "Blue Ocean" opportunity.
    """


@mcp.prompt()
def private_market_disruption_scouting(molecule: str) -> str:
    """
    Analyze the MPR landscape for a molecule to identify overpriced originators.
    """
    return f"""
    I am scouting the South African private sector market for potential entry with: {molecule}

    1. **Landscape Assessment:** Use 'analyse_private_market' (filter_type='active_ingredient') to find the pricing spectrum.
    2. **The Disruption Window:** Check all pages of results to find the gap between the lowest cost generic and the maximum listed price.
    3. **Activity Check:** Identify applicants with 'Avg_Price_Age_Days' > 365 as "Stale/Vulnerable" competitors.
    
    **Visual Render Protocol:** Create a 'Disruption Dashboard'. 
    Render an SVG bar chart showing Applicants vs. SEP pricing. Highlight the 'Disruption Gap' visually where a new entrant could target the margin. 
    """


@mcp.prompt()
def cross_market_viability_check(molecule: str) -> str:
    """
    Compare public sector tender prices with private sector SEPs.
    """
    return f"""
    Perform a multi-market price parity audit for: {molecule}

    1. **Public Sector:** Use 'analyse_ndoh_market' (filter_type='inn') for average awarded Unit Price.
    2. **Private Sector:** Use 'analyse_private_market' (filter_type='active_ingredient') for the SEP range.
       **Pagination Note:** Ensure you have the full pricing spectrum from both datasets before comparing.
    
    **Visual Render Protocol:** Construct a 'Market Parity Chart' (dual-bar visual). 
    Clearly illustrate the gap between State procurement prices vs. Private Pharmacy SEPs. 
    Conclude with a visual indicator (Green/Yellow/Red) denoting whether the margin profile for entering this molecule is "Healthy" or "Cutthroat."
    """


if __name__ == "__main__":
    port = os.getenv("PORT")

    if port:
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=int(port),
        )
    else:
        mcp.run()
