#!/usr/bin/env python3
"""
MCP server for South African pharma intelligence.

This module exposes a FastMCP server with tools that query public SAHPRA
endpoints to retrieve licensed establishment lists and registered product
records. The server is stateless over HTTP and returns Markdown tables.

Tools:
- `get_licensed_companies`: Fetches official establishment lists by category.
- `search_sahpra_products`: Searches registered products by company name.
"""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sahpra_utils import get_sahpra_nonce
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

    Available categories:
    - API Manufacturers
    - Bond Stores
    - Cannabis Cultivation Licences
    - Distribution of Scheduled Substances
    - Gas Manufacturers
    - Holders of Certificate of Product Registration
    - Manufacturers & Packers
    - Private Only Wholesalers
    - Provincial Depots
    - Testing Laboratories

    :param category: Description
    :type category: str
    :return: Description
    :rtype: list[str]
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
    
    :param company_name: Description
    :type company_name: str
    :return: Description
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


if __name__ == "__main__":
    port = os.getenv("PORT")

    if port:
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=int(port),
        )
    else:
        print("Starting local MCP server...", file=sys.stderr)
        mcp.run()
