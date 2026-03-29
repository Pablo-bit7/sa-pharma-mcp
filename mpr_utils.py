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
os.makedirs(CACHE_DIR, exist_ok=True)
LINK_TRACKER = os.path.join(CACHE_DIR, "mpr_latest_link.txt")
CACHE_FILE = os.path.join(CACHE_DIR, "mpr_sep_cache.csv")


async def discover_latest_mpr_list_link(client: httpx.AsyncClient) -> str:
    """
    Scrapes the NDoH NHI page to find the current Database of Medicine Prices
    link.
    """
    URL = "https://www.health.gov.za/nhi/"

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

        return FULL_URL
    
    raise ValueError(
        f"Could not find the Database of Medicine Prices link at {URL}."
    )
