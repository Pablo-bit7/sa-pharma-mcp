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
"""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sahpra_utils import get_sahpra_nonce
from ndoh_utils import get_latest_ndoh_prod_list_df
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
async def get_licensed_companies(category: str = "Manufacturers & Packers") -> str:
    """
    Use this to retrieve the official SAHPRA list of establishments for a specific catagory.

    :param category: Valid options:
        'API Manufacturers', 'Bond Stores',
        'Cannabis Cultivation Licences', 'Distribution of Scheduled Substances',
        'Gas Manufacturers', 'Holders of Certificate of Product Registration',
        'Manufacturers & Packers', 'Private Only Wholesalers',
        'Provincial Depots', 'Testing Laboratories'.
    :type category: str
    :type category: str
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
                "skip_rows": "0",
                "limit_rows": "0",
                "ninja_table_public_nonce": nonce
            }

            response = await client.get(API_URL, params=params, headers=headers)
            response.raise_for_status()

            raw_data = response.json()
            if not raw_data:
                return f"No records for `{category}`"
            
            df = pandas.DataFrame(raw_data)

            return df.head(50).to_markdown(index=False)

        except Exception as e:
            return f"Failed to retrieve companies: {str(e)}"


@mcp.tool()
async def search_sahpra_products(company_name: str) -> str:
    """
    Use this to search the SAHPRA website database table for health products
    registered to a specific company.
    
    :param company_name: The name of the applicant or company to search for (e.g., 'Cipla', 'Aspen').
    :type company_name: str
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
        "start": "0",
        "length": "10",
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
            df = pandas.DataFrame(data["data"])

            if df.empty:
                return f"No products found for '{company_name}'"
            
            display_map = {
                "applicantName": "Company",
                "productName": "Product",
                "licence_no": "Reg No.",
                "reg_date": "Date"
            }

            return df[list(display_map.keys())].rename(columns=display_map).to_markdown(index=False)

        except Exception as e:
            return f"Search failed: {str(e)}"


@mcp.tool()
async def analyse_ndoh_market(
    query: str = None,
    filter_type: str = "all",
    aggregate_by: str = None,
    sort_by: str = "Unit_Price",
    top_n: int = 15
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
    :param top_n: Number of rows to return (default 15). Keep low to save context window.
    :type top_n: int
    :return: Description
    :rtype: str
    """
    df = await get_latest_ndoh_prod_list_df()

    df["Unit_Price"] = pandas.to_numeric(df["Unit_Price"], errors="coerce").fillna(0)
    df["Quantity_Awarded"] = pandas.to_numeric(df["Quantity_Awarded"], errors="coerce").fillna(0)
    df["Award_Value"] = df["Unit_Price"] * df["Quantity_Awarded"]

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

    if aggregate_by and aggregate_by in df.columns:
        summary = df.groupby(aggregate_by).agg({
            "Contract": "count",
            "Award_Value": "sum",
            "Quantity_Awarded": "sum",
            "Unit_Price": ["min", "max", "mean"]
        }).reset_index()

        summary.columns = [aggregate_by, "Contracts", "Total_Value_ZAR", "Total_Qty", "Min_Price", "Max_Price", "Avg_Price"]
        summary = summary.sort_values(by="Total_Value_ZAR", ascending=False)

        return (f"Aggregate Analysis by {aggregate_by}\n" + 
                summary.head(top_n).to_markdown(index=False))
    
    df = df.sort_values(by=sort_by, ascending=(sort_by == "Unit_Price"))

    return (f"Granular Contract View (Top {top_n})\n" + 
            df.head(top_n).to_markdown(index=False))


@mcp.prompt()
def supplier_integrity_audit(company: str) -> str:
    """
    Standardized workflow to adit a supplier's public sector footprint against
    their regulatory standing
    """
    return f"""
    Perform a multi-source integrity audit for: {company}

    1. **Tender Footprint:** Use 'analyse_ndoh_market' (filter_type='supplier') to 
       calculate their total award value, contract volume, and average pricing.
    2. **Regulatory Check:** Use 'get_licensed_companies' to verify if they are 
       officially licensed as 'Manufacturers & Packers' or 'Holders of Certificate of Product Registration'.
    3. **Product Portfolio:** Use 'search_sahpra_products' to list their registered medicines.
    4. **Synthesis:** Do their registered products match their tender awards? 
       Flag any instances where they are winning contracts for molecules not 
       immediately visible in their registered products list.
    """


@mcp.prompt()
def therapeutic_category_assessment(atc_code: str) -> str:
    """
    Analyzes a specific therapeutic class (e.g., J05 for ARVs) to identify 
    market dominance and supply chain risk.
    """
    return f"""
    Analyze the market landscape for Therapeutic Class (ATC): {atc_code}

    1. **Market size:** Use 'analyse_ndoh_market' (filter_type='atc', aggregate_by='INN')
       to rank molecules by total award value and quantity.
    2. **Market Concentration:** Use 'analyse_ndoh_market' with filter_type='atc' 
       and aggregate_by='Supplier' to find the top 3 dominant companies.
    3. **Pricing Efficiency:** For this ATC category, use the same tool to 
       compare 'Min_Price' vs 'Max_Price'. Identify if there is a wide variance 
       suggesting procurement inefficiency.
    4. **Operational Risk:** Use a granular view of the ATC category to flag 
       contracts with lead times > 14 days or expiry dates within the next 6 months.
    5. **Regulatory Density:** For the top 3 suppliers identified, check 
       'get_licensed_companies' to see if they are local manufacturers or 
       private wholesalers.
    6. **Synthesis:** Summarise category maturity (competitive vs. niche),
       flag any single-supplier dependencies, and identify pricing outliers.

    Conclude with a 'Stability Rating' for this category.
    """


@mcp.prompt()
def market_entry_scouting(molecule_name: str) -> str:
    """
    Assess the viability of entering the market with a new generic product.
    """
    return f"""
    I am scouting the market for a potential new entry of: {molecule_name}

    1. **State Spend:** Use 'analyse_ndoh_market' (filter_type='inn') to find 
       the current 'Avg_Price' and total 'Quantity_Awarded' in the public sector.
    2. **Competitor Density:** Use 'search_sahpra_products' with the molecule name 
       to see how many other companies already have a registered product for this molecule.
    3. **The 'Gap' Analysis:** Compare the number of registered competitors 
       (SAHPRA) vs. the number of companies actually winning tenders (NDoH). 
       Is the market saturated, or is there a dominant player that could be disrupted?
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
