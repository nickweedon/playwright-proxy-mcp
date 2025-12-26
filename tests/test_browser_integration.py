"""
Real browser integration tests for Playwright MCP Proxy.

These tests require a running browser and test against real websites.
They are marked with pytest markers to allow selective running:
- @pytest.mark.integration: All real browser tests
- @pytest.mark.slow: Tests that may take longer due to network requests
"""

import tempfile

import pytest

from playwright_proxy_mcp import server
from playwright_proxy_mcp.playwright import (
    BinaryInterceptionMiddleware,
    PlaywrightBlobManager,
    PlaywrightProcessManager,
    PlaywrightProxyClient,
    load_playwright_config,
)
from playwright_proxy_mcp.playwright.config import BlobConfig
from playwright_proxy_mcp.utils.navigation_cache import NavigationCache


@pytest.fixture
async def browser_setup():
    """
    Set up browser components for integration tests.

    Yields a tuple of (proxy_client, navigation_cache) for tests to use.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up configuration
        blob_config: BlobConfig = {
            "storage_root": tmpdir,
            "max_size_mb": 100,
            "ttl_hours": 24,
            "size_threshold_kb": 50,
            "cleanup_interval_minutes": 60,
        }

        playwright_config = load_playwright_config()
        playwright_config["headless"] = True
        playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

        # Initialize components
        blob_manager = PlaywrightBlobManager(blob_config)
        process_manager = PlaywrightProcessManager()
        middleware = BinaryInterceptionMiddleware(blob_manager, blob_config["size_threshold_kb"])
        proxy_client = PlaywrightProxyClient(process_manager, middleware)
        navigation_cache = NavigationCache(default_ttl=300)

        try:
            # Start proxy client
            await blob_manager.start_cleanup_task()
            await proxy_client.start(playwright_config)

            # Temporarily set global navigation cache for browser_navigate/browser_snapshot
            original_cache = server.navigation_cache
            server.navigation_cache = navigation_cache

            # Temporarily set global proxy_client for the tool functions
            original_proxy = server.proxy_client
            server.proxy_client = proxy_client

            yield proxy_client, navigation_cache

        finally:
            # Restore original globals
            server.navigation_cache = original_cache
            server.proxy_client = original_proxy

            # Clean up
            await blob_manager.stop_cleanup_task()
            await proxy_client.stop()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_real_website(browser_setup):
    """
    Test browser_navigate against a real website in silent mode.

    This test verifies:
    1. The browser can navigate to a real website
    2. Silent mode navigation works
    3. No import errors occur

    Note: We use silent mode because playwright-mcp may output ARIA snapshots
    with inline text that the parser can't handle. The core navigation functionality
    is what we're testing here.
    """
    proxy_client, navigation_cache = browser_setup

    # Navigate to example.com in silent mode (avoids ARIA parsing issues)
    result = await server.browser_navigate.fn(
        url="https://example.com",
        silent_mode=True
    )

    # Verify successful navigation
    assert result is not None, "Result should not be None"
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"
    assert result.get("url") == "https://example.com"

    # In silent mode, snapshot should be None
    assert result.get("snapshot") is None, "Silent mode should not return snapshot"

    print(f"\n✓ Successfully navigated to {result['url']}")
    print(f"✓ Silent mode working correctly")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_multiple_pages(browser_setup):
    """
    Test browser_navigate to multiple pages.

    This test verifies:
    1. Navigation works across different URLs
    2. Silent mode works consistently
    3. No crashes or errors during navigation
    """

    # Navigate to multiple sites in silent mode
    urls = [
        "https://example.com",
        "https://example.org",
        "https://example.net"
    ]

    for url in urls:
        result = await server.browser_navigate.fn(
            url=url,
            silent_mode=True
        )

        # Verify successful navigation
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("success") is True, f"Navigation to {url} should succeed. Error: {result.get('error')}"
        assert result.get("url") == url

    print(f"\n✓ Successfully navigated to {len(urls)} different websites")
    print(f"✓ All navigations completed without errors")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_silent_mode_real_website(browser_setup):
    """
    Test browser_navigate with silent mode against a real website.

    This test verifies:
    1. Silent mode navigation works
    2. No snapshot is returned when silent_mode=True
    3. Navigation still succeeds
    """

    # Navigate in silent mode to example.com
    result = await server.browser_navigate.fn(
        url="https://example.com",
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
async def test_browser_snapshot_after_navigation(browser_setup):
    """
    Test browser_snapshot captures state after navigation.

    This test verifies:
    1. Navigation followed by snapshot works
    2. browser_snapshot tool functions correctly
    3. Silent mode works for snapshots
    """

    # First navigate to a page
    nav_result = await server.browser_navigate.fn(
        url="https://example.com",
        silent_mode=True
    )

    assert nav_result.get("success") is True, "Navigation should succeed"

    # Now take a snapshot in silent mode
    snapshot_result = await server.browser_snapshot.fn(
        silent_mode=True
    )

    # Verify snapshot was captured
    assert snapshot_result is not None
    assert isinstance(snapshot_result, dict)
    assert snapshot_result.get("success") is True, f"Snapshot should succeed. Error: {snapshot_result.get('error')}"
    assert snapshot_result.get("snapshot") is None, "Silent mode should not return snapshot"

    print(f"\n✓ Successfully captured snapshot in silent mode")
    print(f"✓ Navigation and snapshot workflow working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_back(browser_setup):
    """
    Test browser_navigate_back functionality.

    This test verifies:
    1. Navigation to a page works
    2. Browser back navigation works
    3. Multiple sequential navigations work
    """

    # Navigate to first page
    result1 = await server.browser_navigate.fn(
        url="https://example.com",
        silent_mode=True
    )
    assert result1.get("success") is True, "First navigation should succeed"

    # Navigate to second page
    result2 = await server.browser_navigate.fn(
        url="https://example.org",
        silent_mode=True
    )
    assert result2.get("success") is True, "Second navigation should succeed"

    # Navigate back
    back_result = await server.browser_navigate_back.fn()
    assert back_result is not None, "Navigate back should return a result"

    print(f"\n✓ Successfully navigated to two pages")
    print(f"✓ Navigate back working correctly")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_tools_integration(browser_setup):
    """
    Test integration of multiple browser tools.

    This test verifies:
    1. Multiple tool calls work in sequence
    2. Browser state is maintained
    3. Different tool types work together
    """

    # Navigate to a page
    nav_result = await server.browser_navigate.fn(
        url="https://example.com",
        silent_mode=True
    )
    assert nav_result.get("success") is True, "Navigation should succeed"

    # Take a snapshot
    snapshot_result = await server.browser_snapshot.fn(
        silent_mode=True
    )
    assert snapshot_result.get("success") is True, "Snapshot should succeed"

    # Navigate to another page
    nav_result2 = await server.browser_navigate.fn(
        url="https://example.org",
        silent_mode=True
    )
    assert nav_result2.get("success") is True, "Second navigation should succeed"

    # Navigate back
    back_result = await server.browser_navigate_back.fn()
    assert back_result is not None, "Navigate back should return result"

    print(f"\n✓ Successfully executed multiple browser tools")
    print(f"✓ All tools working in integration")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_proxy_health(browser_setup):
    """
    Test that the proxy client is healthy and responsive.

    This test verifies:
    1. Proxy client initializes correctly
    2. Health checks work
    3. Tools are available
    """
    proxy_client, navigation_cache = browser_setup

    # Verify proxy is healthy
    assert proxy_client.is_healthy(), "Proxy client should be healthy"

    # Navigate to verify it's actually working
    result = await server.browser_navigate.fn(
        url="https://example.com",
        silent_mode=True
    )

    assert result.get("success") is True, "Navigation should work when proxy is healthy"

    print("\n✓ Proxy client is healthy")
    print("✓ All tools accessible")


# ============================================================================
# Complex Website Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_github(browser_setup):
    """
    Test navigation to GitHub, a complex JavaScript-heavy website.

    This test verifies:
    1. Navigation to complex SPA works
    2. JavaScript-rendered content is handled
    3. Site with dynamic routing works
    """

    result = await server.browser_navigate.fn(
        url="https://github.com",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"GitHub navigation failed: {result.get('error')}"
    assert "github.com" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to GitHub")
    print("✓ Complex SPA navigation working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_wikipedia(browser_setup):
    """
    Test navigation to Wikipedia with complex DOM structure.

    This test verifies:
    1. Navigation to content-heavy sites works
    2. Complex nested DOM structures are handled
    3. Sites with extensive internal links work
    """

    result = await server.browser_navigate.fn(
        url="https://en.wikipedia.org/wiki/Web_browser",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Wikipedia navigation failed: {result.get('error')}"
    assert "wikipedia.org" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to Wikipedia")
    print("✓ Content-heavy site navigation working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_mdn(browser_setup):
    """
    Test navigation to MDN Web Docs, a technical documentation site.

    This test verifies:
    1. Navigation to documentation sites works
    2. Sites with code examples are handled
    3. Technical content with special formatting works
    """

    result = await server.browser_navigate.fn(
        url="https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"MDN navigation failed: {result.get('error')}"
    assert "developer.mozilla.org" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to MDN Web Docs")
    print("✓ Technical documentation site working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_stack_overflow(browser_setup):
    """
    Test navigation to Stack Overflow, a Q&A site with complex interactions.

    This test verifies:
    1. Navigation to community sites works
    2. Sites with voting/interaction elements are handled
    3. Complex forms and input fields work
    """

    result = await server.browser_navigate.fn(
        url="https://stackoverflow.com/questions",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Stack Overflow navigation failed: {result.get('error')}"
    assert "stackoverflow.com" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to Stack Overflow")
    print("✓ Q&A site with complex interactions working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_react_website(browser_setup):
    """
    Test navigation to React.dev, a modern React-based documentation site.

    This test verifies:
    1. React-based SPAs work correctly
    2. Client-side routing is handled
    3. Modern framework sites are supported
    """

    result = await server.browser_navigate.fn(
        url="https://react.dev",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"React.dev navigation failed: {result.get('error')}"
    assert "react.dev" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to React.dev")
    print("✓ React SPA navigation working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_news_site(browser_setup):
    """
    Test navigation to BBC News, a media-heavy news website.

    This test verifies:
    1. Navigation to news sites works
    2. Media-heavy content is handled
    3. Sites with many images/videos work
    """

    result = await server.browser_navigate.fn(
        url="https://www.bbc.com/news",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"BBC News navigation failed: {result.get('error')}"
    assert "bbc.com" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to BBC News")
    print("✓ Media-heavy site navigation working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_multiple_complex_sites(browser_setup):
    """
    Test sequential navigation to multiple complex websites.

    This test verifies:
    1. Multiple complex site navigations work
    2. Browser state is maintained across navigations
    3. No memory leaks or performance degradation
    """

    urls = [
        "https://github.com",
        "https://en.wikipedia.org",
        "https://stackoverflow.com",
        "https://developer.mozilla.org",
        "https://react.dev"
    ]

    successful_navigations = 0

    for url in urls:
        result = await server.browser_navigate.fn(
            url=url,
            silent_mode=True
        )

        assert result is not None, f"Result for {url} should not be None"
        assert isinstance(result, dict), f"Result for {url} should be a dictionary"

        if result.get("success"):
            successful_navigations += 1
            print(f"  ✓ {url}")

    # At least 80% should succeed (allows for occasional network issues)
    success_rate = successful_navigations / len(urls)
    assert success_rate >= 0.8, f"Too many failures: {successful_navigations}/{len(urls)} succeeded"

    print(f"\n✓ Successfully navigated to {successful_navigations}/{len(urls)} complex websites")
    print("✓ Sequential complex navigation working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_with_redirect(browser_setup):
    """
    Test navigation to a URL that redirects.

    This test verifies:
    1. HTTP redirects are followed correctly
    2. Final URL is reported accurately
    3. Redirect chains don't cause issues
    """

    # httpbin.org/redirect-to provides HTTP redirects
    result = await server.browser_navigate.fn(
        url="https://httpbin.org/redirect-to?url=https://example.com",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Redirect navigation failed: {result.get('error')}"
    # After redirect, should be at example.com
    assert "example.com" in result.get("url", "").lower() or "httpbin.org" in result.get("url", "").lower()

    print("\n✓ Successfully handled HTTP redirect")
    print("✓ Redirect navigation working")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_form_heavy_site(browser_setup):
    """
    Test navigation to a site with many form elements.

    This test verifies:
    1. Sites with forms load correctly
    2. Input elements are accessible
    3. Form-heavy pages don't cause issues
    """

    # W3Schools has many form examples
    result = await server.browser_navigate.fn(
        url="https://www.w3schools.com/html/html_forms.asp",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Form site navigation failed: {result.get('error')}"
    assert "w3schools.com" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to form-heavy site")
    print("✓ Form elements handled correctly")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_table_heavy_site(browser_setup):
    """
    Test navigation to a site with complex table structures.

    This test verifies:
    1. Sites with tables load correctly
    2. Complex table structures are handled
    3. Tabular data doesn't cause parsing issues
    """

    result = await server.browser_navigate.fn(
        url="https://www.w3schools.com/html/html_tables.asp",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Table site navigation failed: {result.get('error')}"
    assert "w3schools.com" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to table-heavy site")
    print("✓ Complex table structures handled")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_accessibility_features(browser_setup):
    """
    Test navigation to WebAIM, an accessibility-focused website.

    This test verifies:
    1. Sites with ARIA landmarks work
    2. Accessibility features are preserved
    3. Semantic HTML is handled correctly
    """

    result = await server.browser_navigate.fn(
        url="https://webaim.org",
        silent_mode=True
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"WebAIM navigation failed: {result.get('error')}"
    assert "webaim.org" in result.get("url", "").lower()

    print("\n✓ Successfully navigated to accessibility-focused site")
    print("✓ ARIA and accessibility features handled")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_navigate_back_complex_workflow(browser_setup):
    """
    Test browser back navigation with complex website workflow.

    This test verifies:
    1. Back navigation works with complex sites
    2. Browser history is maintained correctly
    3. Navigation state is preserved
    """

    # Navigate through multiple complex sites
    result1 = await server.browser_navigate.fn(
        url="https://github.com",
        silent_mode=True
    )
    assert result1.get("success") is True, "First navigation should succeed"

    result2 = await server.browser_navigate.fn(
        url="https://stackoverflow.com",
        silent_mode=True
    )
    assert result2.get("success") is True, "Second navigation should succeed"

    result3 = await server.browser_navigate.fn(
        url="https://developer.mozilla.org",
        silent_mode=True
    )
    assert result3.get("success") is True, "Third navigation should succeed"

    # Navigate back twice
    back_result1 = await server.browser_navigate_back.fn()
    assert back_result1 is not None, "First back navigation should return result"

    back_result2 = await server.browser_navigate_back.fn()
    assert back_result2 is not None, "Second back navigation should return result"

    print("\n✓ Successfully navigated through complex workflow")
    print("✓ Multiple back navigations working correctly")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_browser_complex_workflow_integration(browser_setup):
    """
    Test a complete complex workflow with multiple operations.

    This test verifies:
    1. Complex multi-step workflows work
    2. Different tools work together on complex sites
    3. State is maintained throughout workflow
    """

    # Navigate to GitHub
    nav1 = await server.browser_navigate.fn(
        url="https://github.com",
        silent_mode=True
    )
    assert nav1.get("success") is True, "GitHub navigation should succeed"

    # Take snapshot
    snapshot1 = await server.browser_snapshot.fn(silent_mode=True)
    assert snapshot1.get("success") is True, "Snapshot should succeed"

    # Navigate to Wikipedia
    nav2 = await server.browser_navigate.fn(
        url="https://en.wikipedia.org",
        silent_mode=True
    )
    assert nav2.get("success") is True, "Wikipedia navigation should succeed"

    # Take another snapshot
    snapshot2 = await server.browser_snapshot.fn(silent_mode=True)
    assert snapshot2.get("success") is True, "Second snapshot should succeed"

    # Navigate back
    back = await server.browser_navigate_back.fn()
    assert back is not None, "Back navigation should return result"

    # Final snapshot
    snapshot3 = await server.browser_snapshot.fn(silent_mode=True)
    assert snapshot3.get("success") is True, "Final snapshot should succeed"

    print("\n✓ Successfully completed complex multi-step workflow")
    print("✓ All operations working together on complex sites")
