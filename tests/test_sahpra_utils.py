"""
Tests for sahpra_utils.py – nonce fetching and in-memory caching logic.
"""
import time
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

import sahpra_utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(text: str, status_code: int = 200) -> MagicMock:
    """Return a minimal mock that quacks like an httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


HTML_WITH_NONCE = """
<script>
var ninja_tables_public = {
    "ninja_table_public_nonce": "abc123def4"
};
</script>
"""

HTML_WITHOUT_NONCE = "<html><body>No nonce here.</body></html>"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_nonce_cache():
    """Reset the module-level nonce cache before every test."""
    sahpra_utils._nonce_cache["value"] = None
    sahpra_utils._nonce_cache["timestamp"] = 0
    yield
    sahpra_utils._nonce_cache["value"] = None
    sahpra_utils._nonce_cache["timestamp"] = 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_sahpra_nonce_fetches_and_caches():
    """First call should hit the network and store the nonce in the cache."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(HTML_WITH_NONCE)

    nonce = await sahpra_utils.get_sahpra_nonce(mock_client)

    assert nonce == "abc123def4"
    mock_client.get.assert_called_once()
    assert sahpra_utils._nonce_cache["value"] == "abc123def4"
    assert sahpra_utils._nonce_cache["timestamp"] > 0


@pytest.mark.asyncio
async def test_get_sahpra_nonce_uses_cache_on_second_call():
    """Second call within the cache lifetime should NOT hit the network."""
    # Pre-populate the cache with a valid nonce.
    sahpra_utils._nonce_cache["value"] = "cached_nonce"
    sahpra_utils._nonce_cache["timestamp"] = time.time()

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    nonce = await sahpra_utils.get_sahpra_nonce(mock_client)

    assert nonce == "cached_nonce"
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_sahpra_nonce_refreshes_expired_cache():
    """When the cache is older than CACHE_LIFETIME, a fresh fetch is made."""
    sahpra_utils._nonce_cache["value"] = "old_nonce"
    sahpra_utils._nonce_cache["timestamp"] = time.time() - sahpra_utils.CACHE_LIFETIME - 1

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(HTML_WITH_NONCE)

    nonce = await sahpra_utils.get_sahpra_nonce(mock_client)

    assert nonce == "abc123def4"
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_sahpra_nonce_raises_when_not_found():
    """ValueError must be raised when the page contains no recognisable nonce."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(HTML_WITHOUT_NONCE)

    with pytest.raises(ValueError, match="Nonce not found"):
        await sahpra_utils.get_sahpra_nonce(mock_client)


@pytest.mark.asyncio
async def test_get_sahpra_nonce_propagates_http_error():
    """Network / HTTP errors should bubble up to the caller."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(httpx.ConnectError):
        await sahpra_utils.get_sahpra_nonce(mock_client)


@pytest.mark.asyncio
async def test_get_sahpra_nonce_nonce_value_is_hexadecimal():
    """The regex should only match hex strings in the nonce field."""
    html = """
    <script>
    var obj = {"ninja_table_public_nonce": "deadbeef01"};
    </script>
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _make_response(html)

    nonce = await sahpra_utils.get_sahpra_nonce(mock_client)
    assert nonce == "deadbeef01"
