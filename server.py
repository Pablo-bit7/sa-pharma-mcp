#!/usr/bin/env python3
"""
Docstring for sa-pharma-mcp.server
"""
from mcp.server.fastmcp import FastMCP
from bs4 import BeautifulSoup
import httpx
import pandas


mcp = FastMCP("SA_Pharma")

SAHPRA_SEARCH_URL = "https://www.sahpra.org.za/registered-health-products/"


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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(follow_redirects=True, http2=True) as client:
        try:
            response = await client.get(SAHPRA_SEARCH_URL, headers=headers, timeout=20.0)
            response.raise_for_status()
        except Exception as e:
            return f"SAHRPA currently unreachable: {str(e)}"

    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table")
    if not table:
        return "Could not find database table on the SAHPRA website."

    df = pandas.read_html(str(table))[0]
    result = df[df["Applicant Name"].str.contains(company_name, case=False, na=False)]

    if result.empty:
        return f"No registered products found for '{company_name}'."

    return result.to_markdown(index=False)


if __name__ == "__main__":
    mcp.run()
