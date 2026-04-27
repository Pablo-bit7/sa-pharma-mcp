#!/usr/bin/env python3
"""
Utilities for retrieving the Database of Medicine Prices (MPR/SEP).

The module dicovers the latest Database of Medicine Prices Excel link from the
NDoH NHI page, downloads and parses the file, and caches a cleaned CSV locally.
If an update fails, it falls back to the most recent cached data.
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
LINK_TRACKER = os.path.join(CACHE_DIR, "ndoh_mpr_latest_link.txt")
CACHE_FILE = os.path.join(CACHE_DIR, "ndoh_mpr_sep_cache.csv")

_CACHED_DF = None
_CACHED_LINK = None
_CACHED_DATE = None


async def discover_latest_mpr_list_link(client: httpx.AsyncClient) -> tuple[str, str]:
    """
    Scrapes the NDoH NHI page to find the current Database of Medicine Prices
    link.
    """
    URL = "https://www.health.gov.za/nhi-pee/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = await client.get(URL, headers=headers, follow_redirects=True)
    response.raise_for_status()

    match = re.search(
        r'href=["\']([^"\']*(?:database|prices)[^"\']+\.xlsx)["\']',
        response.text,
        re.IGNORECASE
    )

    if match:
        RELATIVE_PATH = match.group(1)
        FULL_URL = urljoin(URL, RELATIVE_PATH)

        date_match = re.search(
            r'([0-9]{1,2}[- _][A-Za-z]+[- _][0-9]{4})',
            RELATIVE_PATH
        )
        doc_date = date_match.group(1).replace('-', ' ').replace('_', ' ') if date_match else "Unknown Date"

        return FULL_URL, doc_date
    
    raise ValueError(
        f"Could not find the Database of Medicine Prices link at {URL}."
    )


async def get_latest_mpr_list_df() -> tuple[pandas.DataFrame, str, bool]:
    """
    Returns the Database of Medicine Prices as a Pandas DataFrame. Downloads
    only if a newer link is found or if the cache is missing.
    """
    global _CACHED_DF, _CACHED_LINK, _CACHED_DATE

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        try:
            current_link, doc_date = await discover_latest_mpr_list_link(client)

            # RAM Cache Hit
            if _CACHED_LINK == current_link and _CACHED_DF is not None:
                print(f"DEBUG: MPR cache hit in RAM ({doc_date}).", file=sys.stderr)
                return _CACHED_DF, doc_date, True

            # Disk Cache Hit
            if os.path.exists(LINK_TRACKER) and os.path.exists(CACHE_FILE):
                with open(LINK_TRACKER, "r") as file:
                    if file.read().strip() == current_link:
                        print(f"DEBUG: MPR RAM empty, but Disk cache is up to date ({doc_date}). Loading...", file=sys.stderr)
                        _CACHED_DF = pandas.read_csv(CACHE_FILE)
                        _CACHED_LINK = current_link
                        _CACHED_DATE = doc_date
                        return _CACHED_DF, doc_date, True

            # Downlaod & Parse (New link found)
            print(f"DEBUG: Downloading new MPR: {current_link}, {doc_date}", file=sys.stderr)
            response = await client.get(current_link)
            response.raise_for_status()

            print(f"DEBUG: Parsing Excel file...", file=sys.stderr)
            raw_df = pandas.read_excel(io.BytesIO(response.content), header=1)

            target_columns = [1, 6, 7, 10, 11, 12, 3, 13, 14, 16, 18]
            df = raw_df.iloc[:, target_columns].copy()

            df.columns = [
                "Applicant", "Proprietery_Name", "Active_Ingredient",
                "Dosage_Form", "Pack_Size", "Quantity", "NAPPI_Code",
                "Manufacturer_Price", "Logistics_Fee", "SEP", "Effective_Date"
            ]

            cols_to_fill = [
                "Applicant", "Proprietery_Name",
                "Dosage_Form", "Pack_Size",
                "Quantity", "NAPPI_Code",
                "Manufacturer_Price", "Logistics_Fee",
                "SEP", "Effective_Date"
            ]
            df[cols_to_fill] = df[cols_to_fill].ffill()

            df.dropna(subset=["Active_Ingredient"], inplace=True)

            # Update RAM state
            _CACHED_DF, _CACHED_LINK, _CACHED_DATE = df, current_link, doc_date

            # Persistence Logic
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                df.to_csv(CACHE_FILE, index=False)
                with open(LINK_TRACKER, "w") as file:
                    file.write(current_link)
                print(f"DEBUG: MPR cache rebuilt and saved to disk.", file=sys.stderr)

            except OSError as e:
                print(f"WARNING: Skipping disk persistence (Read-Only FS): {e}", file=sys.stderr)
            
            return df, doc_date, True
        
        except Exception as e:
            if _CACHED_DF is not None:
                print(f"ERROR: Update failed, falling back to RAM cache: {str(e)}", file=sys.stderr)
                return _CACHED_DF, _CACHED_DATE or "Unknown", False
            
            elif os.path.exists(CACHE_FILE):
                print(f"ERROR: Update failed, falling back to stale Disk cache: {str(e)}", file=sys.stderr)
                df = pandas.read_csv(CACHE_FILE)
                return df, "Previous release (Stale)", False

            raise e


if __name__ == "__main__":
    async def test_utility():
        print("\n" + "="*50, file=sys.stderr)
        print("RUNNING MPR UTILITY TEST", file=sys.stderr)
        print("="*50 + "\n", file=sys.stderr)
        
        try:
            df, doc_date, is_live = await get_latest_mpr_list_df()

            status = "LIVE" if is_live else "STALE/CACHED"
            print(f"Success: Loaded {len(df)} medicines.", file=sys.stderr)
            print(f"Source Date: {doc_date} [{status}]", file=sys.stderr)
            print(f"Columns: {list(df.columns)}", file=sys.stderr)
            
            print("\n--- DATA SAMPLE (TOP 5) ---")
            try:
                print(df.head(5).to_markdown(index=False))
            except ImportError:
                print(df.head(5).to_string(index=False))
            
            mock_query = "Paracetamol"

            print(f"\n--- MOCK SEARCH: '{mock_query}' ---")
            results = df[df['Active_Ingredient'].str.contains(mock_query, case=False, na=False)]
            if not results.empty:
                try:
                    print(results.head(3).to_markdown(index=False))
                except ImportError:
                    print(results.head(3).to_string(index=False))
            else:
                print(f"No results found for {mock_query}")
                
            print("\n" + "="*50, file=sys.stderr)
            print("TEST COMPLETE", file=sys.stderr)
            print("="*50, file=sys.stderr)

        except Exception as e:
            print(f"\n❌ TEST FAILED: {str(e)}", file=sys.stderr)

    asyncio.run(test_utility())
