"""
Tests for the MCP tool functions defined in server.py.

All HTTP calls are mocked so these tests run entirely offline.
"""
import json
import pytest
import pandas as pd
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(json_data=None, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    return resp


def _licensed_companies_payload():
    """Minimal list of dicts that the SAHPRA Ninja Tables endpoint would return."""
    return [
        {"Name": "Bayer SA", "Licence": "ML001", "Category": "Manufacturers & Packers"},
        {"Name": "Aspen Pharmacare", "Licence": "ML002", "Category": "Manufacturers & Packers"},
    ]


def _sahpra_products_payload(company: str):
    """Minimal response body from the medapps product search endpoint."""
    return {
        "data": [
            {
                "applicantName": company,
                "productName": "Aspirin 100mg",
                "api": "Acetylsalicylic Acid",
                "licence_no": "A12/34/56",
                "application_no": "APP001",
                "reg_date": "2020-01-01",
                "status": "Active",
                "secureId": "xyz",
            }
        ],
        "recordsTotal": 1,
        "recordsFiltered": 1,
    }


def _ndoh_market_dataframe():
    """A small, realistic DataFrame that mimics the MHPL cache."""
    return pd.DataFrame({
        "Contract": ["C001", "C002", "C003"],
        "NSN": ["NSN1", "NSN2", "NSN3"],
        "Description": ["Aspirin 100mg Tab", "Ibuprofen 400mg Tab", "Metformin 500mg Tab"],
        "INN": ["Aspirin", "Ibuprofen", "Metformin"],
        "Supplier": ["Bayer", "Cipla", "Aspen"],
        "Unit_Price": ["2.50", "3.00", "1.50"],
        "Lead_Time_Days": [7, 14, 7],
        "EML_Status": ["EML", "NEL", "EML"],
        "ATC_Code": ["N02BA", "M01AE", "A10BA"],
        "Care_Level": ["PHC", "PHC", "PHC"],
        "Quantity_Awarded": ["1000", "500", "2000"],
        "MOQ": [100, 50, 200],
        "Contract_Expiry": ["2025-12-31", "2025-06-30", "2026-03-31"],
    })


# ---------------------------------------------------------------------------
# Tests – get_licensed_companies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_licensed_companies_valid_category():
    from server import get_licensed_companies

    payload = _licensed_companies_payload()

    with (
        patch("server.get_sahpra_nonce", new=AsyncMock(return_value="testnonce")),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _make_response(json_data=payload)
        mock_cls.return_value = mock_client

        result = await get_licensed_companies("Manufacturers & Packers")

    assert "Bayer SA" in result
    assert "Aspen Pharmacare" in result
    assert "|" in result  # markdown table


@pytest.mark.asyncio
async def test_get_licensed_companies_invalid_category():
    from server import get_licensed_companies

    result = await get_licensed_companies("Unknown Category")

    assert "Error" in result
    assert "Unknown Category" in result


@pytest.mark.asyncio
async def test_get_licensed_companies_empty_response():
    from server import get_licensed_companies

    with (
        patch("server.get_sahpra_nonce", new=AsyncMock(return_value="testnonce")),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _make_response(json_data=[])
        mock_cls.return_value = mock_client

        result = await get_licensed_companies("Bond Stores")

    assert "No records" in result


@pytest.mark.asyncio
async def test_get_licensed_companies_http_error():
    from server import get_licensed_companies

    with (
        patch("server.get_sahpra_nonce", new=AsyncMock(return_value="testnonce")),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("timeout")
        mock_cls.return_value = mock_client

        result = await get_licensed_companies("Manufacturers & Packers")

    assert "Failed to retrieve" in result


@pytest.mark.asyncio
@pytest.mark.parametrize("category", [
    "API Manufacturers",
    "Bond Stores",
    "Cannabis Cultivation Licences",
    "Distribution of Scheduled Substances",
    "Gas Manufacturers",
    "Holders of Certificate of Product Registration",
    "Manufacturers & Packers",
    "Private Only Wholesalers",
    "Provincial Depots",
    "Testing Laboratories",
])
async def test_get_licensed_companies_all_valid_categories(category):
    """Every valid category must resolve to a table ID without an error."""
    from server import get_licensed_companies

    payload = [{"Name": "Test Co", "Licence": "TST001"}]

    with (
        patch("server.get_sahpra_nonce", new=AsyncMock(return_value="testnonce")),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _make_response(json_data=payload)
        mock_cls.return_value = mock_client

        result = await get_licensed_companies(category)

    assert "Error" not in result


@pytest.mark.asyncio
async def test_get_licensed_companies_limits_to_50_rows():
    """Result must contain at most 50 rows even if the API returns more."""
    from server import get_licensed_companies

    payload = [{"Name": f"Co {i}", "Licence": f"LIC{i:03d}"} for i in range(100)]

    with (
        patch("server.get_sahpra_nonce", new=AsyncMock(return_value="testnonce")),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _make_response(json_data=payload)
        mock_cls.return_value = mock_client

        result = await get_licensed_companies("Manufacturers & Packers")

    # Row 50 (0-indexed) should be present; row 51 should not.
    assert "Co 49" in result
    assert "Co 50" not in result


# ---------------------------------------------------------------------------
# Tests – search_sahpra_products
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_sahpra_products_found():
    from server import search_sahpra_products

    with (
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = _make_response(json_data=_sahpra_products_payload("Bayer"))
        mock_cls.return_value = mock_client

        result = await search_sahpra_products("Bayer")

    assert "Bayer" in result
    assert "Aspirin 100mg" in result
    assert "|" in result  # markdown table


@pytest.mark.asyncio
async def test_search_sahpra_products_not_found():
    from server import search_sahpra_products

    empty_payload = {"data": [], "recordsTotal": 0, "recordsFiltered": 0}

    with (
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = _make_response(json_data=empty_payload)
        mock_cls.return_value = mock_client

        result = await search_sahpra_products("NonexistentCompany")

    assert "No products found" in result
    assert "NonexistentCompany" in result


@pytest.mark.asyncio
async def test_search_sahpra_products_http_error():
    from server import search_sahpra_products

    with (
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("timeout")
        mock_cls.return_value = mock_client

        result = await search_sahpra_products("Cipla")

    assert "Search failed" in result


@pytest.mark.asyncio
async def test_search_sahpra_products_display_columns():
    """Only the four display columns should appear in the output."""
    from server import search_sahpra_products

    with (
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = _make_response(
            json_data=_sahpra_products_payload("Aspen")
        )
        mock_cls.return_value = mock_client

        result = await search_sahpra_products("Aspen")

    for col in ("Company", "Product", "Reg No.", "Date"):
        assert col in result

    # Internal API fields should NOT leak into the output.
    for col in ("secureId", "application_no", "status"):
        assert col not in result


# ---------------------------------------------------------------------------
# Tests – analyse_ndoh_market
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ndoh_df():
    """Patch get_latest_ndoh_prod_list_df to return a small in-memory DataFrame."""
    df = _ndoh_market_dataframe()

    async def _fake_get():
        return df.copy()

    return _fake_get


@pytest.mark.asyncio
async def test_analyse_ndoh_market_no_query(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market()

    assert "Granular Contract View" in result
    assert "|" in result  # markdown table


@pytest.mark.asyncio
async def test_analyse_ndoh_market_filter_inn(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(query="Aspirin", filter_type="inn")

    assert "Aspirin" in result
    assert "Ibuprofen" not in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_filter_supplier(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(query="Bayer", filter_type="supplier")

    assert "Bayer" in result
    assert "Cipla" not in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_filter_atc(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(query="N02", filter_type="atc")

    assert "N02BA" in result
    assert "M01AE" not in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_filter_all(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(query="Aspen", filter_type="all")

    assert "Aspen" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_not_found(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(query="Doesnotexist999", filter_type="inn")

    assert "No procurement data found" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_aggregate_by_supplier(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(aggregate_by="Supplier")

    assert "Aggregate Analysis by Supplier" in result
    assert "Contracts" in result
    assert "Total_Value_ZAR" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_aggregate_by_inn(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(aggregate_by="INN")

    assert "Aggregate Analysis by INN" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_aggregate_by_care_level(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(aggregate_by="Care_Level")

    assert "Aggregate Analysis by Care_Level" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_invalid_aggregate_by(mock_ndoh_df):
    """An invalid aggregate_by column should fall through to the granular view."""
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(aggregate_by="NonExistentColumn")

    assert "Granular Contract View" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_top_n_limits_rows(mock_ndoh_df):
    """top_n=1 should return only one data row from the 3-row fixture."""
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(top_n=1)

    # The fixture has 3 rows; with top_n=1 only the first (lowest Unit_Price
    # after ascending sort, i.e. "C003" Metformin @ 1.50) should appear.
    # The other two contracts must be absent.
    contracts_in_result = sum(1 for c in ["C001", "C002", "C003"] if c in result)
    assert contracts_in_result == 1


@pytest.mark.asyncio
async def test_analyse_ndoh_market_sort_by_quantity(mock_ndoh_df):
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(sort_by="Quantity_Awarded")

    assert "Granular Contract View" in result
    assert "|" in result


@pytest.mark.asyncio
async def test_analyse_ndoh_market_numeric_coercion(mock_ndoh_df):
    """
    Unit_Price and Quantity_Awarded are stored as strings in the fixture;
    the tool must coerce them to numerics before computing Award_Value.
    """
    from server import analyse_ndoh_market

    with patch("server.get_latest_ndoh_prod_list_df", new=mock_ndoh_df):
        result = await analyse_ndoh_market(aggregate_by="Supplier")

    # If numeric coercion failed, the aggregation would error or produce NaN.
    assert "nan" not in result.lower()
    assert "Total_Value_ZAR" in result


# ---------------------------------------------------------------------------
# Tests – prompt helpers (smoke tests)
# ---------------------------------------------------------------------------

def test_supplier_integrity_audit_prompt_contains_company():
    from server import supplier_integrity_audit

    result = supplier_integrity_audit("Cipla")
    assert "Cipla" in result


def test_therapeutic_category_assessment_prompt_contains_atc():
    from server import therapeutic_category_assessment

    result = therapeutic_category_assessment("J05")
    assert "J05" in result


def test_market_entry_scouting_prompt_contains_molecule():
    from server import market_entry_scouting

    result = market_entry_scouting("Tenofovir")
    assert "Tenofovir" in result
