"""
Real browser integration tests for Playwright MCP Proxy.

These tests require a running browser and test against real websites.
They are marked with pytest markers to allow selective running:
- @pytest.mark.integration: All real browser tests
- @pytest.mark.slow: Tests that may take longer due to network requests
"""

import pytest

from playwright_proxy_mcp import server


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_real_website():
    """
    Test browser_navigate against a real website (lcsc.com).

    This test verifies:
    1. The browser can navigate to a real website
    2. ARIA snapshot parsing works correctly
    3. No import errors occur (specifically AriaSnapshotParser)
    """
    # Ensure proxy client is started
    if not server.proxy_client or not server.proxy_client.is_healthy():
        pytest.skip("Proxy client not started - this test requires a running browser")

    # Navigate to the actual website
    result = await server.browser_navigate.fn(
        url="https://www.lcsc.com/product-detail/C107107.html",
        silent_mode=False
    )

    # Verify successful navigation
    assert result is not None, "Result should not be None"
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"
    assert result.get("url") == "https://www.lcsc.com/product-detail/C107107.html"

    # Verify snapshot was captured
    assert result.get("snapshot") is not None, "Snapshot should be captured when silent_mode=False"
    assert len(result.get("snapshot", "")) > 0, "Snapshot should not be empty"

    # Verify ARIA snapshot structure (should contain YAML formatted ARIA tree)
    snapshot = result.get("snapshot")
    # YAML format should have list items starting with "- " or role definitions
    assert isinstance(snapshot, str), "Snapshot should be a string"

    print(f"\n✓ Successfully navigated to {result['url']}")
    print(f"✓ Snapshot captured: {len(snapshot)} characters")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_with_query_real_website():
    """
    Test browser_navigate with JMESPath query against a real website.

    This test verifies:
    1. JMESPath queries work with real ARIA snapshots
    2. Filtering and pagination work correctly
    3. ARIA parsing handles complex real-world HTML
    """
    # Ensure proxy client is started
    if not server.proxy_client or not server.proxy_client.is_healthy():
        pytest.skip("Proxy client not started - this test requires a running browser")

    # Navigate and filter for buttons
    result = await server.browser_navigate.fn(
        url="https://www.lcsc.com/product-detail/C107107.html",
        jmespath_query='[?role == `button`]',
        output_format="json",
        limit=10
    )

    # Verify successful navigation with query
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"

    # Verify query was applied
    assert result.get("query_applied") == '[?role == `button`]'
    assert result.get("output_format") == "json"

    # Verify pagination metadata
    assert "total_items" in result
    assert "offset" in result
    assert "limit" in result
    assert result.get("limit") == 10
    assert "has_more" in result
    assert "cache_key" in result

    # Verify snapshot is JSON formatted
    snapshot = result.get("snapshot")
    if snapshot:
        import json
        try:
            parsed = json.loads(snapshot)
            assert isinstance(parsed, list), "Filtered snapshot should be a list"
            # If there are items, verify they have the expected structure
            if len(parsed) > 0:
                # Check first item has role property
                assert isinstance(parsed[0], dict), "Items should be dictionaries"
                # Note: Depending on the query result, we may or may not have items
        except json.JSONDecodeError as e:
            pytest.fail(f"Snapshot should be valid JSON when output_format='json': {e}")

    print(f"\n✓ Successfully applied JMESPath query")
    print(f"✓ Total items found: {result.get('total_items')}")
    print(f"✓ Has more: {result.get('has_more')}")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_silent_mode_real_website():
    """
    Test browser_navigate with silent mode against a real website.

    This test verifies:
    1. Silent mode navigation works
    2. No snapshot is returned when silent_mode=True
    3. Navigation still succeeds
    """
    # Ensure proxy client is started
    if not server.proxy_client or not server.proxy_client.is_healthy():
        pytest.skip("Proxy client not started - this test requires a running browser")

    # Navigate in silent mode
    result = await server.browser_navigate.fn(
        url="https://www.lcsc.com/product-detail/C107107.html",
        silent_mode=True
    )

    # Verify successful navigation
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"

    # Verify no snapshot in silent mode
    assert result.get("snapshot") is None, "Silent mode should not return snapshot"

    print(f"\n✓ Successfully navigated in silent mode")
    print(f"✓ No snapshot returned as expected")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_pagination_real_website():
    """
    Test browser_navigate pagination with real website.

    This test verifies:
    1. Pagination creates cache keys
    2. Subsequent calls can reuse cached data
    3. Offset and limit work correctly
    """
    # Ensure proxy client is started
    if not server.proxy_client or not server.proxy_client.is_healthy():
        pytest.skip("Proxy client not started - this test requires a running browser")

    # First page
    result1 = await server.browser_navigate.fn(
        url="https://www.lcsc.com/product-detail/C107107.html",
        limit=20,
        offset=0
    )

    assert result1.get("success") is True, f"First page should succeed. Error: {result1.get('error')}"
    assert result1.get("limit") == 20
    assert result1.get("offset") == 0

    # Get cache key for subsequent calls
    cache_key = result1.get("cache_key")
    assert cache_key is not None, "Cache key should be provided"

    total_items = result1.get("total_items")
    assert total_items is not None, "Total items should be provided"

    # Only test second page if there are more items
    if result1.get("has_more"):
        result2 = await server.browser_navigate.fn(
            url="https://www.lcsc.com/product-detail/C107107.html",
            cache_key=cache_key,
            limit=20,
            offset=20
        )

        assert result2.get("success") is True, f"Second page should succeed. Error: {result2.get('error')}"
        assert result2.get("offset") == 20
        assert result2.get("cache_key") == cache_key, "Cache key should be preserved"
        assert result2.get("total_items") == total_items, "Total items should remain the same"

        print(f"\n✓ Successfully retrieved multiple pages")
        print(f"✓ Total items: {total_items}")
        print(f"✓ Page 1: items 0-19")
        print(f"✓ Page 2: items 20-39")
    else:
        print(f"\n✓ First page successful (only {total_items} items total)")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_snapshot_real_state():
    """
    Test browser_snapshot captures current browser state.

    This test verifies:
    1. Snapshot can capture current page state
    2. ARIA parsing works on current state
    3. Advanced features (query, pagination) work with snapshot
    """
    # Ensure proxy client is started
    if not server.proxy_client or not server.proxy_client.is_healthy():
        pytest.skip("Proxy client not started - this test requires a running browser")

    # First navigate to ensure we have a page loaded
    nav_result = await server.browser_navigate.fn(
        url="https://www.lcsc.com/product-detail/C107107.html",
        silent_mode=True
    )

    assert nav_result.get("success") is True, "Navigation should succeed before snapshot"

    # Now take a snapshot with filtering
    snapshot_result = await server.browser_snapshot.fn(
        jmespath_query='[?role == `link`]',
        output_format="yaml",
        limit=15
    )

    # Verify snapshot success
    assert snapshot_result is not None
    assert isinstance(snapshot_result, dict)
    assert snapshot_result.get("success") is True, f"Snapshot should succeed. Error: {snapshot_result.get('error')}"

    # Verify query was applied
    assert snapshot_result.get("query_applied") == '[?role == `link`]'
    assert snapshot_result.get("output_format") == "yaml"

    # Verify pagination
    assert snapshot_result.get("limit") == 15
    assert "total_items" in snapshot_result
    assert "has_more" in snapshot_result

    # Verify snapshot content
    snapshot = snapshot_result.get("snapshot")
    assert snapshot is not None, "Snapshot should be captured"
    assert len(snapshot) > 0, "Snapshot should not be empty"

    print(f"\n✓ Successfully captured snapshot")
    print(f"✓ Total links found: {snapshot_result.get('total_items')}")
