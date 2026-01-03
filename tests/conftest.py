"""
Pytest Configuration and Fixtures

This module provides shared fixtures for all tests.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest

# Import browser fixtures to make them available to all tests
from tests.fixtures.browser_fixture import browser_setup  # noqa: F401


@pytest.fixture
def sample_item() -> dict:
    """Provide a sample item for testing."""
    return {
        "id": "test-item-1",
        "name": "Test Item",
        "description": "A test item for unit tests",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_items() -> list[dict]:
    """Provide a list of sample items for testing."""
    return [
        {
            "id": "test-item-1",
            "name": "Test Item 1",
            "description": "First test item",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": "test-item-2",
            "name": "Test Item 2",
            "description": "Second test item",
            "created_at": "2024-01-02T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        },
    ]


@pytest.fixture
def mock_proxy_client():
    """
    Create a mock proxy client for unit testing.

    This mocks the PlaywrightProxyClient that would be returned
    from pool.lease_instance() context manager.
    """
    mock_client = Mock()
    mock_client.is_healthy = AsyncMock(return_value=True)
    mock_client.call_tool = AsyncMock()
    return mock_client


@pytest.fixture
def mock_pool_manager(mock_proxy_client):
    """
    Create a mock pool manager for unit testing.

    This fixture mocks the entire pool manager chain:
    - pool_manager.get_pool() returns a mock pool
    - pool.lease_instance() is an async context manager yielding mock proxy client
    """
    # Create mock pool
    mock_pool = Mock()

    @asynccontextmanager
    async def mock_lease_instance(instance_key=None):
        """Async context manager that yields the mock proxy client."""
        yield mock_proxy_client

    mock_pool.lease_instance = mock_lease_instance

    # Create mock pool manager
    mock_pm = Mock()
    mock_pm.get_pool = Mock(return_value=mock_pool)

    return mock_pm


@pytest.fixture
def mock_navigation_cache():
    """Create a mock navigation cache for testing."""
    mock_cache = Mock()
    mock_cache.get = Mock(return_value=None)
    mock_cache.create = Mock(return_value="nav_test123")
    return mock_cache
