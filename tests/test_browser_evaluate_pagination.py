"""
Tests for browser_evaluate pagination functionality.
"""

from unittest.mock import AsyncMock, patch

import pytest

from playwright_proxy_mcp.utils.navigation_cache import NavigationCache


@pytest.fixture
def mock_proxy_client():
    """Mock proxy client for testing."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_navigation_cache():
    """Mock navigation cache for testing."""
    return NavigationCache(default_ttl=300)


@pytest.mark.asyncio
async def test_browser_evaluate_array_pagination(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate with array result pagination."""
    from playwright_proxy_mcp import server

    # Mock: JavaScript returns array of 100 numbers
    mock_proxy_client.call_tool.return_value = {"result": list(range(100))}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        # First call with limit=20
        result = await server.browser_evaluate.fn(
            function="() => Array.from({length: 100}, (_, i) => i)", limit=20
        )

        assert result["success"] is True
        assert result["total_items"] == 100
        assert result["offset"] == 0
        assert result["limit"] == 20
        assert result["has_more"] is True
        assert len(result["result"]) == 20
        assert result["result"] == list(range(20))
        assert result["error"] is None

        cache_key = result["cache_key"]

        # Next page
        result2 = await server.browser_evaluate.fn(
            function="() => Array.from({length: 100}, (_, i) => i)",
            cache_key=cache_key,
            offset=20,
            limit=20,
        )

        assert result2["success"] is True
        assert result2["total_items"] == 100
        assert result2["offset"] == 20
        assert result2["limit"] == 20
        assert result2["has_more"] is True
        assert len(result2["result"]) == 20
        assert result2["result"] == list(range(20, 40))


@pytest.mark.asyncio
async def test_browser_evaluate_non_array_wrapping(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate wraps non-array results."""
    from playwright_proxy_mcp import server

    # Mock: JavaScript returns single object
    mock_proxy_client.call_tool.return_value = {"result": {"name": "John", "age": 30}}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        result = await server.browser_evaluate.fn(
            function="() => ({name: 'John', age: 30})", limit=10  # Trigger pagination mode
        )

        assert result["success"] is True
        assert result["total_items"] == 1
        assert result["has_more"] is False
        assert result["result"] == [{"name": "John", "age": 30}]


@pytest.mark.asyncio
async def test_browser_evaluate_backward_compatibility(mock_proxy_client):
    """Test browser_evaluate without pagination returns original format."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"result": 42}

    with patch.object(server, "proxy_client", mock_proxy_client):
        # No pagination parameters
        result = await server.browser_evaluate.fn(function="() => 42")

        # Should return original dict format
        assert result == {"result": 42}
        assert "cache_key" not in result
        assert "total_items" not in result


@pytest.mark.asyncio
async def test_browser_evaluate_offset_beyond_bounds(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate with offset beyond array length."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"result": [1, 2, 3]}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        result = await server.browser_evaluate.fn(
            function="() => [1, 2, 3]",
            offset=10,  # Beyond array length
            limit=5,
        )

        assert result["success"] is True
        assert result["total_items"] == 3
        assert result["result"] == []  # Empty page
        assert result["has_more"] is False


@pytest.mark.asyncio
async def test_browser_evaluate_validation_negative_offset(mock_navigation_cache):
    """Test browser_evaluate with negative offset."""
    from playwright_proxy_mcp import server

    with patch.object(server, "navigation_cache", mock_navigation_cache):
        result = await server.browser_evaluate.fn(
            function="() => [1, 2, 3]", offset=-5, limit=10
        )

        assert result["success"] is False
        assert "offset must be non-negative" in result["error"]


@pytest.mark.asyncio
async def test_browser_evaluate_validation_invalid_limit_high(mock_navigation_cache):
    """Test browser_evaluate with limit too high."""
    from playwright_proxy_mcp import server

    with patch.object(server, "navigation_cache", mock_navigation_cache):
        result = await server.browser_evaluate.fn(function="() => [1, 2, 3]", limit=20000)

        assert result["success"] is False
        assert "limit must be between 1 and 10000" in result["error"]


@pytest.mark.asyncio
async def test_browser_evaluate_validation_invalid_limit_low(mock_navigation_cache):
    """Test browser_evaluate with limit too low."""
    from playwright_proxy_mcp import server

    with patch.object(server, "navigation_cache", mock_navigation_cache):
        result = await server.browser_evaluate.fn(function="() => [1, 2, 3]", limit=0)

        assert result["success"] is False
        assert "limit must be between 1 and 10000" in result["error"]


@pytest.mark.asyncio
async def test_browser_evaluate_cache_miss(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate with expired/missing cache."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"result": [1, 2, 3]}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        # First call
        result = await server.browser_evaluate.fn(function="() => [1, 2, 3]", limit=2)

        cache_key = result["cache_key"]

        # Simulate cache expiration
        mock_navigation_cache.delete(cache_key)

        # Next call with expired cache should fetch fresh
        result2 = await server.browser_evaluate.fn(
            function="() => [1, 2, 3]",
            cache_key=cache_key,  # This key no longer exists
            offset=2,
            limit=2,
        )

        # Should re-evaluate and create new cache
        assert result2["success"] is True
        assert result2["cache_key"] != cache_key  # New cache key
        assert result2["total_items"] == 3


@pytest.mark.asyncio
async def test_browser_evaluate_pagination_with_element(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate pagination with element parameter."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "result": ["option1", "option2", "option3"]
    }

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        result = await server.browser_evaluate.fn(
            function="(el) => Array.from(el.options).map(o => o.value)",
            element="Dropdown menu",
            ref="e5",
            limit=2,
        )

        assert result["success"] is True
        assert result["total_items"] == 3
        assert result["limit"] == 2
        assert len(result["result"]) == 2
        assert result["result"] == ["option1", "option2"]

        # Verify the proxy client was called with correct args
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_evaluate",
            {
                "function": "(el) => Array.from(el.options).map(o => o.value)",
                "element": "Dropdown menu",
                "ref": "e5",
            },
        )


@pytest.mark.asyncio
async def test_browser_evaluate_single_value_wrapping(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate wraps primitive values."""
    from playwright_proxy_mcp import server

    # Test with string
    mock_proxy_client.call_tool.return_value = {"result": "hello"}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        result = await server.browser_evaluate.fn(function="() => 'hello'", limit=10)

        assert result["success"] is True
        assert result["total_items"] == 1
        assert result["result"] == ["hello"]
        assert result["has_more"] is False


@pytest.mark.asyncio
async def test_browser_evaluate_offset_beyond_single_value(
    mock_proxy_client, mock_navigation_cache
):
    """Test browser_evaluate with offset beyond single value."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"result": 42}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        result = await server.browser_evaluate.fn(function="() => 42", offset=1, limit=10)

        assert result["success"] is True
        assert result["total_items"] == 1
        assert result["result"] == []  # Empty - offset beyond single item
        assert result["has_more"] is False


@pytest.mark.asyncio
async def test_browser_evaluate_last_page(mock_proxy_client, mock_navigation_cache):
    """Test browser_evaluate on last page."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"result": list(range(25))}

    with patch.object(server, "proxy_client", mock_proxy_client), patch.object(
        server, "navigation_cache", mock_navigation_cache
    ):
        # First call
        result = await server.browser_evaluate.fn(function="() => [...Array(25).keys()]", limit=20)

        cache_key = result["cache_key"]
        assert result["has_more"] is True

        # Last page
        result2 = await server.browser_evaluate.fn(
            function="() => [...Array(25).keys()]", cache_key=cache_key, offset=20, limit=20
        )

        assert result2["success"] is True
        assert result2["total_items"] == 25
        assert result2["offset"] == 20
        assert len(result2["result"]) == 5  # Only 5 items left
        assert result2["result"] == list(range(20, 25))
        assert result2["has_more"] is False  # No more items
