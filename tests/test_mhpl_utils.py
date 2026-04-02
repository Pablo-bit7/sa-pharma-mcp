"""
Tests for mhpl_utils.py – link discovery, caching, DataFrame parsing, and
fallback behaviour.
"""
import io
import os
import tempfile
import pytest
import pandas as pd
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, mock_open


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(content=b"", text="", status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = content
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _minimal_mhpl_excel() -> bytes:
    """
    Build an in-memory Excel file that mimics the MHPL structure
    (data starts at row 4, i.e. header=3 for pandas).
    Columns used: 0,2,3,9,11,13,14,15,17,19,20,29,31 (0-indexed).
    We create 32 columns so the target indices are valid.
    """
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active

    # Rows 1-3 are skipped metadata; row 4 is the header read by pandas.
    ws.append(["skip1"])
    ws.append(["skip2"])
    ws.append(["skip3"])

    # Header row (row 4 in Excel, index 3 for pandas header=3).
    num_cols = 32
    headers = [f"col_{i}" for i in range(num_cols)]
    ws.append(headers)

    # One data row with recognisable values at the target column positions.
    # Positions: 0=Contract, 2=NSN, 3=Desc, 9=INN, 11=Supplier,
    #            13=Unit_Price, 14=Lead_Time, 15=EML, 17=ATC, 19=Care,
    #            20=Qty, 29=MOQ, 31=Expiry
    row = [""] * num_cols
    row[0] = "C001"          # Contract
    row[2] = "NSN123"        # NSN
    row[3] = "Aspirin 100mg" # Description (non-null → row kept)
    row[9] = "Aspirin"       # INN
    row[11] = "Bayer"        # Supplier
    row[13] = "5.50"         # Unit_Price
    row[14] = "7"            # Lead_Time_Days
    row[15] = "EML"          # EML_Status
    row[17] = "N02BA"        # ATC_Code
    row[19] = "PHC"          # Care_Level
    row[20] = "1000"         # Quantity_Awarded
    row[29] = "100"          # MOQ
    row[31] = "2025-12-31"   # Contract_Expiry
    ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


TENDERS_HTML_WITH_LINK = (
    '<a href="/wp-content/uploads/Master-Health-Product-List-2024.xlsx">'
    "Download MHPL</a>"
)

TENDERS_HTML_WITHOUT_LINK = "<html><body>Nothing here</body></html>"


# ---------------------------------------------------------------------------
# Tests – discover_latest_ndoh_prod_list_link
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discover_link_returns_absolute_url():
    import mhpl_utils

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(text=TENDERS_HTML_WITH_LINK)

    url = await mhpl_utils.discover_latest_ndoh_prod_list_link(mock_client)

    assert url.startswith("http")
    assert "Master-Health-Product-List-2024.xlsx" in url


@pytest.mark.asyncio
async def test_discover_link_raises_when_not_found():
    import mhpl_utils

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(text=TENDERS_HTML_WITHOUT_LINK)

    with pytest.raises(ValueError, match="Master Health Product List"):
        await mhpl_utils.discover_latest_ndoh_prod_list_link(mock_client)


@pytest.mark.asyncio
async def test_discover_link_case_insensitive():
    """The regex should match 'mhpl' in any case."""
    import mhpl_utils

    html = '<a href="/files/MHPL_2024.xlsx">Download</a>'
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(text=html)

    url = await mhpl_utils.discover_latest_ndoh_prod_list_link(mock_client)
    assert "MHPL_2024.xlsx" in url


# ---------------------------------------------------------------------------
# Tests – get_latest_ndoh_prod_list_df
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_df_uses_cache_when_link_unchanged(tmp_path):
    """If the stored link matches the current link, return the cached CSV."""
    import mhpl_utils

    link = "https://example.com/Master-Health-Product-List.xlsx"

    # Write a minimal cache CSV.
    cache_csv = tmp_path / "ndoh_mhpl_cache.csv"
    cache_df = pd.DataFrame({"Contract": ["C1"], "Description": ["Drug A"]})
    cache_df.to_csv(cache_csv, index=False)

    link_file = tmp_path / "ndoh_mhpl_latest_link.txt"
    link_file.write_text(link)

    with (
        patch.object(mhpl_utils, "CACHE_FILE", str(cache_csv)),
        patch.object(mhpl_utils, "LINK_TRACKER", str(link_file)),
        patch("mhpl_utils.discover_latest_ndoh_prod_list_link", new=AsyncMock(return_value=link)),
    ):
        df = await mhpl_utils.get_latest_ndoh_prod_list_df()

    assert not df.empty
    assert "Contract" in df.columns


@pytest.mark.asyncio
async def test_get_df_downloads_when_link_changed(tmp_path):
    """When a new link is found, the Excel file is downloaded and the cache rebuilt."""
    import mhpl_utils

    new_link = "https://example.com/Master-Health-Product-List-NEW.xlsx"
    old_link = "https://example.com/Master-Health-Product-List-OLD.xlsx"

    link_file = tmp_path / "ndoh_mhpl_latest_link.txt"
    link_file.write_text(old_link)

    cache_csv = tmp_path / "ndoh_mhpl_cache.csv"

    excel_bytes = _minimal_mhpl_excel()
    excel_response = _make_response(content=excel_bytes)

    with (
        patch.object(mhpl_utils, "CACHE_FILE", str(cache_csv)),
        patch.object(mhpl_utils, "LINK_TRACKER", str(link_file)),
        patch("mhpl_utils.discover_latest_ndoh_prod_list_link", new=AsyncMock(return_value=new_link)),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = excel_response
        mock_cls.return_value = mock_client

        df = await mhpl_utils.get_latest_ndoh_prod_list_df()

    assert not df.empty
    assert "Description" in df.columns
    assert cache_csv.exists()
    assert link_file.read_text() == new_link


@pytest.mark.asyncio
async def test_get_df_falls_back_to_stale_cache_on_error(tmp_path):
    """When the network fails and a cache file exists, it must be returned."""
    import mhpl_utils

    cache_csv = tmp_path / "ndoh_mhpl_cache.csv"
    stale_df = pd.DataFrame({"Contract": ["C999"], "Description": ["Stale Drug"]})
    stale_df.to_csv(cache_csv, index=False)

    link_file = tmp_path / "ndoh_mhpl_latest_link.txt"

    with (
        patch.object(mhpl_utils, "CACHE_FILE", str(cache_csv)),
        patch.object(mhpl_utils, "LINK_TRACKER", str(link_file)),
        patch("mhpl_utils.discover_latest_ndoh_prod_list_link", new=AsyncMock(side_effect=RuntimeError("network down"))),
    ):
        df = await mhpl_utils.get_latest_ndoh_prod_list_df()

    assert not df.empty
    assert df["Contract"].iloc[0] == "C999"


@pytest.mark.asyncio
async def test_get_df_raises_when_no_cache_and_network_fails(tmp_path):
    """When no cache exists and the network fails, the exception propagates."""
    import mhpl_utils

    cache_csv = tmp_path / "ndoh_mhpl_cache.csv"  # does NOT exist
    link_file = tmp_path / "ndoh_mhpl_latest_link.txt"

    with (
        patch.object(mhpl_utils, "CACHE_FILE", str(cache_csv)),
        patch.object(mhpl_utils, "LINK_TRACKER", str(link_file)),
        patch("mhpl_utils.discover_latest_ndoh_prod_list_link", new=AsyncMock(side_effect=RuntimeError("network down"))),
    ):
        with pytest.raises(RuntimeError, match="network down"):
            await mhpl_utils.get_latest_ndoh_prod_list_df()


@pytest.mark.asyncio
async def test_get_df_drops_rows_with_null_description(tmp_path):
    """Rows where Description is NaN must be dropped during parsing."""
    import mhpl_utils
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    # 3 skip rows + header
    for _ in range(3):
        ws.append(["skip"])
    ws.append([f"col_{i}" for i in range(32)])

    # Row with a Description
    row_good = [""] * 32
    row_good[3] = "Valid Drug"
    row_good[0] = "C001"
    ws.append(row_good)

    # Row with no Description (will be dropped)
    row_bad = [""] * 32
    row_bad[3] = None
    row_bad[0] = "C002"
    ws.append(row_bad)

    buf = io.BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()

    new_link = "https://example.com/Master-Health-Product-List.xlsx"
    link_file = tmp_path / "ndoh_mhpl_latest_link.txt"
    link_file.write_text("https://old.link")
    cache_csv = tmp_path / "ndoh_mhpl_cache.csv"

    with (
        patch.object(mhpl_utils, "CACHE_FILE", str(cache_csv)),
        patch.object(mhpl_utils, "LINK_TRACKER", str(link_file)),
        patch("mhpl_utils.discover_latest_ndoh_prod_list_link", new=AsyncMock(return_value=new_link)),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _make_response(content=excel_bytes)
        mock_cls.return_value = mock_client

        df = await mhpl_utils.get_latest_ndoh_prod_list_df()

    assert len(df) == 1
    assert df["Description"].iloc[0] == "Valid Drug"
