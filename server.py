#!/usr/bin/env python3
"""
Docstring for sa-pharma-mcp.server
"""
from mcp.server.fastmcp import FastMCP
from bs4 import BeautifulSoup
import httpx
import pandas
import io


mcp = FastMCP("SA_Pharma")

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

    async with httpx.AsyncClient(follow_redirects=True, http1=True, http2=True, timeout=30.0) as client:
        try:
            landing_response = await client.get(LANDING_URL, headers=headers)
            landing_response.raise_for_status()
        except Exception as e:
            return f"SAHRPA currently unreachable: {str(e)}"

        soup = BeautifulSoup(landing_response.text, "html.parser")

        file_url = None
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if ("Medicine" in href or "Product" in href) and (href.endswith(".csv") or href.endswith(".xlsx")):
                file_url = href
                break

        if not file_url:
            return "Couldn't directly find a link to the data"
        
        try:
            file_response = await client.get(file_url, headers=headers)
            file_response.raise_for_status()

            if file_url.endswith(".csv"):
                df = pandas.read_csv(io.BytesIO(file_response.content))
            else:
                df = pandas.read_excel(io.BytesIO(file_response.content))
        except httpx.HTTPStatusError as e:
            return f"An error occured upon data download. Status: {e.response.status_code}"
        except Exception as e:
            return f"Failed to process the resgister: {str(e)}"

        df.columns = [str(c).strip() for c in df.columns]
        target_column = next((c for c in df.columns if "Applicant" in c or "Holder" in c), None)

        if not target_column:
            return f"Could not find a company column in the table. Columns found: {list(df.columns)}"

        results = df[df[target_column].astype(str).str.contains(company_name, case=False, na=False)]

        if results.empty:
            return f"No results for {company_name}"
    
    return results.head(15).to_markdown(index=False)


if __name__ == "__main__":
    mcp.run()
