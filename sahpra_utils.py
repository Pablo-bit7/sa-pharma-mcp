#!/usr/bin/env python3
"""
Utilities for interacting with SAHPRA public data endpoints.

Includes a cached helper to fetch the Ninja Tables public nonce used by
SAHPRA's approved-licences tables. The nonce is stored in-memory for
12 hours to reduce repeated page fetches.
"""
import httpx
import time
import re
import asyncio


_nonce_cache = {"value": None, "timestamp": 0}
CACHE_LIFETIME = 43200

async def get_sahpra_nonce(client: httpx.AsyncClient) -> str:
    """
    Gets and caches Ninja Tables nonce every 12hrs.
    
    :param client: Description
    :type client: httpx.AsyncClient
    :return: Description
    :rtype: str
    """
    global _nonce_cache
    now = time.time()

    if _nonce_cache["value"] and (now - _nonce_cache["timestamp"] < CACHE_LIFETIME):
        return _nonce_cache["value"]
    
    URL = "https://www.sahpra.org.za/approved-licences/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    }

    response = await client.get(URL, headers=headers, follow_redirects=True)
    response.raise_for_status()

    match = re.search(r'["\']ninja_table_public_nonce["\']\s*:\s*["\']([a-f0-9]+)["\']', response.text)
    if not match:
        raise ValueError("Nonce not found.")
    
    _nonce_cache["value"] = match.group(1)
    _nonce_cache["timestamp"] = now

    return _nonce_cache["value"]


if __name__ == "__main__":
    async def test_get_sahpra_nonce():
        """
        Quick manual test: fetch the SAHPRA nonce and print it to stdout.
        """
        async with httpx.AsyncClient(verify=False) as client:
            try:
                nonce = await get_sahpra_nonce(client)
                print(f"Nonce: {nonce}")
            except Exception as e:
                print(f"Error: {e}")
    
    asyncio.run(test_get_sahpra_nonce())
