"""
Integration tests for key workflows
"""

import base64
import re
import tempfile
from unittest.mock import Mock, patch

import pytest

from playwright_proxy_mcp.playwright.blob_manager import PlaywrightBlobManager
from playwright_proxy_mcp.playwright.config import load_playwright_config
from playwright_proxy_mcp.playwright.middleware import BinaryInterceptionMiddleware
from playwright_proxy_mcp.playwright.process_manager import PlaywrightProcessManager
from playwright_proxy_mcp.playwright.proxy_client import PlaywrightProxyClient


class TestIntegrationWorkflows:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_blob_manager_workflow(self):
        """Test complete blob storage workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "storage_root": tmpdir,
                "max_size_mb": 10,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            manager = PlaywrightBlobManager(config)

            # Test storage
            test_data = b"Test binary data for integration"
            base64_data = base64.b64encode(test_data).decode("utf-8")

            with patch.object(manager.storage, "upload_blob") as mock_upload:
                mock_upload.return_value = {
                    "blob_id": "blob_test",
                    "created_at": "2024-01-01T00:00:00Z",
                }

                result = await manager.store_base64_data(base64_data, "test.bin")

                assert "blob_id" in result
                assert result["size_bytes"] == len(test_data)

    @pytest.mark.asyncio
    async def test_middleware_integration(self):
        """Test middleware with blob manager integration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "storage_root": tmpdir,
                "max_size_mb": 10,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            blob_manager = PlaywrightBlobManager(config)
            middleware = BinaryInterceptionMiddleware(blob_manager, 50)

            # Small data should not be intercepted
            small_data = b"x" * 100
            base64_small = base64.b64encode(small_data).decode("utf-8")
            response = {"data": base64_small}

            result = await middleware.intercept_response("non_binary_tool", response)
            assert result == response

    @pytest.mark.asyncio
    async def test_middleware_edge_cases(self):
        """Test middleware with various edge cases."""
        mock_blob_manager = Mock()
        middleware = BinaryInterceptionMiddleware(mock_blob_manager, 50)

        # Empty response
        result = await middleware.intercept_response("tool", {})
        assert result == {}

        # Response with None values
        response_with_none = {"data": None, "status": "ok"}
        result = await middleware.intercept_response("tool", response_with_none)
        assert result == response_with_none

    @pytest.mark.asyncio
    async def test_config_integration(self):
        """Test configuration loading integration."""
        from playwright_proxy_mcp.playwright.config import (
            load_blob_config,
            load_playwright_config,
        )

        # Test that configs load without errors
        pw_config = load_playwright_config()
        blob_config = load_blob_config()

        # Verify required keys exist
        assert "browser" in pw_config
        assert "headless" in pw_config
        assert "storage_root" in blob_config
        assert "max_size_mb" in blob_config

    @pytest.mark.asyncio
    async def test_real_mcp_server_amazon_screenshot(self):
        """
        Integration test: Start real MCP server, navigate to Amazon, and take a screenshot.

        This test verifies:
        1. The MCP server starts successfully
        2. Navigation to Amazon works
        3. Screenshot tool returns ONLY a blob:// URI (not blob data)
        4. Blob is actually stored in the blob manager
        5. Blob URI follows the expected format
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up configuration
            blob_config = {
                "storage_root": tmpdir,
                "max_size_mb": 100,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            playwright_config = load_playwright_config()
            # Ensure headless mode for testing
            playwright_config["headless"] = True
            # Override output_dir to use temp directory instead of /app
            playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

            # Initialize components (mimicking server.py global components)
            blob_manager = PlaywrightBlobManager(blob_config)
            process_manager = PlaywrightProcessManager()
            middleware = BinaryInterceptionMiddleware(blob_manager, blob_config["size_threshold_kb"])
            proxy_client = PlaywrightProxyClient(process_manager, middleware)

            # Patch the server's global components to use our test instances
            import playwright_proxy_mcp.server as server_module

            original_proxy_client = server_module.proxy_client
            original_blob_manager = server_module.blob_manager
            original_middleware = server_module.middleware

            server_module.proxy_client = proxy_client
            server_module.blob_manager = blob_manager
            server_module.middleware = middleware

            try:
                # Start the proxy client and playwright-mcp subprocess
                await proxy_client.start(playwright_config)

                # Start blob cleanup task
                await blob_manager.start_cleanup_task()

                # Verify the proxy client is healthy
                assert proxy_client.is_healthy(), "Proxy client should be healthy after starting"

                # Navigate to Amazon using the MCP server tool's underlying function
                navigate_result = await server_module.playwright_navigate.fn("https://www.amazon.com")

                # Verify navigation succeeded
                assert navigate_result is not None, "Navigation result should not be None"

                # Take a screenshot using the MCP server tool's underlying function (not proxy client directly!)
                blob_uri = await server_module.playwright_screenshot.fn(name="amazon_homepage", full_page=False)

                # CRITICAL VERIFICATION: Result should be ONLY a blob URI string, not blob data
                assert isinstance(blob_uri, str), (
                    f"Expected screenshot to return a string (blob URI), got {type(blob_uri)}: {blob_uri}"
                )

                # Verify it's a blob URI, not base64 data
                assert blob_uri.startswith("blob://"), (
                    f"Expected blob:// URI, got: {blob_uri[:100]}"
                )

                # Verify blob URI format: blob://TIMESTAMP-HASH.EXTENSION
                blob_uri_pattern = r"^blob://\d+-[a-f0-9]+\.\w+$"
                assert re.match(blob_uri_pattern, blob_uri), (
                    f"Blob URI '{blob_uri}' does not match expected pattern '{blob_uri_pattern}'"
                )

                # Verify the blob was actually stored in the blob manager
                # Extract the blob ID (everything after blob://)
                blob_id = blob_uri.replace("blob://", "")

                # Verify by checking the blob manager's storage
                metadata = blob_manager.storage.get_metadata(blob_id)
                assert metadata is not None, f"Blob {blob_id} should exist in storage"
                assert metadata["size_bytes"] > 0, "Blob should have non-zero size"

            finally:
                # Restore original server components
                server_module.proxy_client = original_proxy_client
                server_module.blob_manager = original_blob_manager
                server_module.middleware = original_middleware

                # Clean up
                await blob_manager.stop_cleanup_task()
                await proxy_client.stop()

                # Verify cleanup
                assert not proxy_client.is_healthy(), "Proxy client should not be healthy after stopping"
