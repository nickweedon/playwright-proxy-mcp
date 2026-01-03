"""
Playwright MCP Proxy Package

This package provides proxy functionality for Microsoft's playwright-mcp server,
including subprocess management, blob storage for large binary data, and middleware
for response transformation.

Version 2.0.0: Supports browser pools with hierarchical configuration.
"""

from .blob_manager import PlaywrightBlobManager
from .config import (
    BlobConfig,
    PlaywrightConfig,
    PoolManagerConfig,
    load_blob_config,
    load_playwright_config,
    load_pool_manager_config,
)
from .middleware import BinaryInterceptionMiddleware
from .pool_manager import PoolManager
from .process_manager import PlaywrightProcessManager
from .proxy_client import PlaywrightProxyClient

__all__ = [
    "PlaywrightBlobManager",
    "BlobConfig",
    "PlaywrightConfig",
    "PoolManagerConfig",
    "load_blob_config",
    "load_playwright_config",
    "load_pool_manager_config",
    "BinaryInterceptionMiddleware",
    "PoolManager",
    "PlaywrightProcessManager",
    "PlaywrightProxyClient",
]
