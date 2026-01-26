#!/usr/bin/env python3
"""
Docstring for sa-pharma-mcp.server
"""
from mcp.server.fastmcp import FastMCP
import httpx
import pandas


mcp = FastMCP(
    "za-pharma-intelligence",
    descrption="Integrated pharmaceutical intelligence hub for South Africa"
)


API_URL = "https://medapps.sahpra.org.za:6006/Home/getData"


@mcp.tool()
async def get_licensed_companies() -> list[str]:
    """
    Use this to search the SAHPRA website database table for the official list
    of licensed establishments.
    
    :return: Description
    :rtype: list[str]
    """
    pass


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
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        path="/mcp"
    )
