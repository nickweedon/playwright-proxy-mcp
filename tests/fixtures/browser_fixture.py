"""
Shared browser test fixtures.

This module provides fixtures for browser integration tests that require
a running Playwright browser instance with blob management.

Version 2.0.0: Updated to use pool manager architecture.
"""

import os
import tempfile
from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest
import pytest_asyncio

from playwright_proxy_mcp import server
from playwright_proxy_mcp.playwright import (
    BinaryInterceptionMiddleware,
    PlaywrightBlobManager,
    PoolManager,
    load_pool_manager_config,
)
from playwright_proxy_mcp.playwright.config import BlobConfig
from playwright_proxy_mcp.utils.navigation_cache import NavigationCache


@pytest_asyncio.fixture
async def browser_setup():
    """
    Set up browser components for integration tests using pool manager (v2.0.0).

    This fixture initializes all components needed for browser testing:
    - Temporary directory for blob storage
    - Blob manager with cleanup task
    - Binary interception middleware
    - Pool manager with single 'ISOLATED' pool for testing
    - Navigation cache for pagination

    The fixture temporarily patches the global server components to use
    the test instances, then restores them on teardown.

    Yields:
        tuple: (pool_manager, navigation_cache) for tests to use
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up blob configuration
        blob_config: BlobConfig = {
            "storage_root": tmpdir,
            "max_size_mb": 100,
            "ttl_hours": 24,
            "size_threshold_kb": 50,
            "cleanup_interval_minutes": 60,
        }

        # Set up environment variables for pool configuration
        # Save original env vars to restore later
        original_env = {}
        test_env_vars = {
            # Global configuration
            "PW_MCP_PROXY_BROWSER": "chrome",
            "PW_MCP_PROXY_HEADLESS": "true",
            "PW_MCP_PROXY_TIMEOUT_ACTION": "15000",
            "PW_MCP_PROXY_TIMEOUT_NAVIGATION": "5000",
            "PW_MCP_PROXY_CAPS": "vision,pdf",
            "PW_MCP_PROXY_IMAGE_RESPONSES": "allow",
            "PW_MCP_PROXY_VIEWPORT_SIZE": "1920x1080",
            # Pool configuration - single instance for testing
            "PW_MCP_PROXY__ISOLATED_INSTANCES": "1",
            "PW_MCP_PROXY__ISOLATED_IS_DEFAULT": "true",
            "PW_MCP_PROXY__ISOLATED_DESCRIPTION": "Test pool for integration tests",
            "PW_MCP_PROXY__ISOLATED_OUTPUT_DIR": f"{tmpdir}/playwright-output",
        }

        # Apply test environment variables
        for key, value in test_env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Save original server globals before starting
        original_pool_manager = server.pool_manager
        original_cache = server.navigation_cache
        original_blob_manager = server.blob_manager
        original_middleware = server.middleware

        pool_manager = None
        blob_manager = None

        try:
            # Load pool manager configuration from environment
            pool_manager_config = load_pool_manager_config()

            # Initialize components
            blob_manager = PlaywrightBlobManager(blob_config)
            middleware = BinaryInterceptionMiddleware(blob_manager, blob_config["size_threshold_kb"])
            navigation_cache = NavigationCache(default_ttl=300)

            # Initialize pool manager
            pool_manager = PoolManager(pool_manager_config, blob_manager, middleware)

            # Start blob cleanup and pool manager
            await blob_manager.start_cleanup_task()
            await pool_manager.initialize()

            # Temporarily patch global server components
            server.pool_manager = pool_manager
            server.navigation_cache = navigation_cache
            server.blob_manager = blob_manager
            server.middleware = middleware

            yield pool_manager, navigation_cache

        finally:
            # Restore original server globals
            server.pool_manager = original_pool_manager
            server.navigation_cache = original_cache
            server.blob_manager = original_blob_manager
            server.middleware = original_middleware

            # Clean up pool manager (stops all instances)
            if pool_manager:
                for pool in pool_manager.pools.values():
                    await pool.stop()

            # Stop blob cleanup
            if blob_manager:
                await blob_manager.stop_cleanup_task()

            # Restore original environment variables
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value
