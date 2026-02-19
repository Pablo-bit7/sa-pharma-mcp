#!/usr/bin/env python3
"""
Utilities for retrieving the NDoH Master Health Product List (MHPL).

The module discovers the latest MHPL Excel link from the NDoH tenders page,
downloads and parses the file, and caches a cleaned CSV locally for faster
reuse. If an update fails, it falls back to the most recent cached data.
"""
import pandas
import httpx
import sys
import os
import re
import io
from urllib.parse import urljoin
import asyncio


CACHE_DIR = "./data"
os.makedirs(CACHE_DIR, exist_ok=True)
LINK_TRACKER = os.path.join(CACHE_DIR, "latest_link.txt")
CACHE_FILE = os.path.join(CACHE_DIR, "ndoh_mhpl_cache.csv")


async def discover_latest_ndoh_prod_list_link(client: httpx.AsyncClient) -> str:
    """
    Scrapes the NDoH Tenders page to find the current Master Health Product List link.
    """
    URL = "https://www.health.gov.za/tenders/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = await client.get(URL, headers=headers, follow_redirects=True)
    response.raise_for_status()

    match = re.search(
        r'href=["\']([^"\']*(?:Master-Health-Product-List|MHPL)[^"\']+\.xlsx)["\']',
        response.text,
        re.IGNORECASE
    )

    if match:
        RELATIVE_PATH = match.group(1)
        FULL_URL = urljoin(URL, RELATIVE_PATH)

        return FULL_URL
    
    raise ValueError(
        f"Could not find the Master Health Product List link at {URL}."
    )


async def get_latest_ndoh_prod_list_df() -> pandas.DataFrame:
    """
    Returns the NDoH Master Hesalth Product List.
    Downloads only if a newer link is found.
    """
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        try:
            current_link = await discover_latest_ndoh_prod_list_link(client)

            last_link = ""
            if os.path.exists(LINK_TRACKER):
                with open(LINK_TRACKER, "r") as file:
                    last_link = file.read().strip()
            
            if last_link == current_link and os.path.exists(CACHE_FILE):
                print(f"DEBUG: MHPL cache is up to date.", file=sys.stderr)
                return pandas.read_csv(CACHE_FILE)
            
            print(f"DEBUG: Downloading new MHPL: {current_link}", file=sys.stderr)
            response = await client.get(current_link)
            response.raise_for_status()

            print(f"DEBUG: Parsing Excel file...", file=sys.stderr)
            raw_df = pandas.read_excel(io.BytesIO(response.content), header=3)

            target_columns = [0, 2, 3, 9, 11, 13, 14, 15, 17, 19, 20, 29, 31]
            df = raw_df.iloc[:, target_columns].copy()

            df.columns = [
                "Contract", "NSN", "Description", "INN", "Supplier",
                "Unit_Price", "Lead_Time_Days", "EML_Status", "ATC_Code",
                "Care_Level", "Quantity_Awarded", "MOQ", "Contract_Expiry"
            ]

            df.dropna(subset=["Description"], inplace=True)

            df.to_csv(CACHE_FILE, index=False)
            with open(LINK_TRACKER, "w") as file:
                file.write(current_link)

            print(f"DEBUG: MHPL cache rebuilt.", file=sys.stderr)
            return df

        except Exception as e:
            if os.path.exists(CACHE_FILE):
                print(f"ERROR: Update failed, falling back to stale cache: {str(e)}", file=sys.stderr)

                return pandas.read_csv(CACHE_FILE)
            raise e


if __name__ == "__main__":
    async def test_utility():
        print("\n" + "="*50, file=sys.stderr)
        print("RUNNING NDOH UTILITY TEST", file=sys.stderr)
        print("="*50 + "\n", file=sys.stderr)
        
        try:
            df = await get_latest_ndoh_prod_list_df()

            print(f"Success: Loaded {len(df)} products.", file=sys.stderr)
            print(f"Columns: {list(df.columns)}", file=sys.stderr)
            
            print("\n--- DATA SAMPLE (TOP 5) ---")
            print(df.head(5).to_markdown(index=False))
            
            mock_query = "Aspirin"

            print(f"\n--- MOCK SEARCH: '{mock_query}' ---")
            results = df[df['Description'].str.contains(mock_query, case=False, na=False)]
            if not results.empty:
                print(results.head(3).to_markdown(index=False))
            else:
                print(f"No results found for {mock_query}")
                
            print("\n" + "="*50, file=sys.stderr)
            print("TEST COMPLETE", file=sys.stderr)
            print("="*50, file=sys.stderr)

        except Exception as e:
            print(f"\n❌ TEST FAILED: {str(e)}", file=sys.stderr)


    asyncio.run(test_utility())
