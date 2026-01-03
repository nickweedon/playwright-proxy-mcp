"""Tests for pool_manager module."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from playwright_proxy_mcp.playwright.config import InstanceConfig, PoolConfig
from playwright_proxy_mcp.playwright.pool_manager import (
    BrowserInstance,
    BrowserPool,
    PoolManager,
)


class TestBrowserInstance:
    """Tests for BrowserInstance class"""

    @pytest.fixture
    def mock_proxy_client(self):
        client = AsyncMock()
        client.is_healthy = AsyncMock(return_value=True)
        client.stop = AsyncMock()
        return client

    @pytest.fixture
    def mock_process_manager(self):
        manager = Mock()
        return manager

    @pytest.fixture
    def browser_instance(self, mock_proxy_client, mock_process_manager):
        return BrowserInstance(
            instance_id="0",
            alias="test-alias",
            proxy_client=mock_proxy_client,
            process_manager=mock_process_manager,
        )

    def test_init(self, browser_instance, mock_proxy_client, mock_process_manager):
        assert browser_instance.instance_id == "0"
        assert browser_instance.alias == "test-alias"
        assert browser_instance.proxy_client == mock_proxy_client
        assert browser_instance.process_manager == mock_process_manager
        assert browser_instance.lease_started_at is None
        assert browser_instance.last_health_check is None
        assert browser_instance.health_check_error is None

    def test_is_leased_false(self, browser_instance):
        assert not browser_instance.is_leased

    def test_is_leased_true(self, browser_instance):
        browser_instance.mark_leased()
        assert browser_instance.is_leased

    def test_lease_duration_ms_none(self, browser_instance):
        assert browser_instance.lease_duration_ms is None

    def test_lease_duration_ms_value(self, browser_instance):
        browser_instance.mark_leased()
        duration = browser_instance.lease_duration_ms
        assert duration is not None
        assert duration >= 0

    def test_mark_leased(self, browser_instance):
        assert browser_instance.lease_started_at is None
        browser_instance.mark_leased()
        assert browser_instance.lease_started_at is not None
        assert isinstance(browser_instance.lease_started_at, datetime)

    def test_mark_released(self, browser_instance):
        browser_instance.mark_leased()
        assert browser_instance.lease_started_at is not None
        browser_instance.mark_released()
        assert browser_instance.lease_started_at is None

    async def test_check_health_success(self, browser_instance, mock_proxy_client):
        mock_proxy_client.is_healthy.return_value = True
        result = await browser_instance.check_health()
        assert result is True
        assert browser_instance.last_health_check is not None
        assert browser_instance.health_check_error is None
        mock_proxy_client.is_healthy.assert_awaited_once()

    async def test_check_health_failure(self, browser_instance, mock_proxy_client):
        mock_proxy_client.is_healthy.return_value = False
        result = await browser_instance.check_health()
        assert result is False
        assert browser_instance.last_health_check is not None
        assert browser_instance.health_check_error == "Health check returned False"

    async def test_check_health_exception(self, browser_instance, mock_proxy_client):
        mock_proxy_client.is_healthy.side_effect = Exception("Connection error")
        result = await browser_instance.check_health()
        assert result is False
        assert browser_instance.last_health_check is not None
        assert "Connection error" in browser_instance.health_check_error

    async def test_stop(self, browser_instance, mock_proxy_client):
        await browser_instance.stop()
        mock_proxy_client.stop.assert_awaited_once()

    async def test_stop_with_error(self, browser_instance, mock_proxy_client):
        mock_proxy_client.stop.side_effect = Exception("Stop error")
        # Should not raise
        await browser_instance.stop()


class TestBrowserPool:
    """Tests for BrowserPool class"""

    @pytest.fixture
    def pool_config(self):
        return PoolConfig(
            name="TEST_POOL",
            instances=2,
            is_default=True,
            description="Test pool",
            base_config={},
            instance_configs=[
                InstanceConfig(
                    instance_id="0",
                    alias=None,
                    config={},
                ),
                InstanceConfig(
                    instance_id="1",
                    alias="debug",
                    config={},
                ),
            ],
        )

    @pytest.fixture
    def browser_pool(self, pool_config):
        return BrowserPool(pool_config)

    @pytest.fixture
    def mock_blob_manager(self):
        return Mock()

    @pytest.fixture
    def mock_middleware(self):
        return Mock()

    def test_init(self, browser_pool, pool_config):
        assert browser_pool.name == "TEST_POOL"
        assert browser_pool.is_default is True
        assert browser_pool.description == "Test pool"
        assert len(browser_pool.instances) == 0
        assert browser_pool.lease_queue is None

    async def test_initialize(self, browser_pool, mock_blob_manager, mock_middleware):
        with patch.object(browser_pool, "_create_instance", new=AsyncMock()) as mock_create:
            await browser_pool.initialize(mock_blob_manager, mock_middleware)
            assert mock_create.call_count == 2
            assert browser_pool.lease_queue is not None

    async def test_create_instance(self, browser_pool, mock_blob_manager, mock_middleware):
        instance_cfg = InstanceConfig(
            instance_id="0",
            alias=None,
            config={},
        )

        with patch(
            "playwright_proxy_mcp.playwright.pool_manager.PlaywrightProxyClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            await browser_pool._create_instance(instance_cfg, mock_blob_manager, mock_middleware)

            assert "0" in browser_pool.instances
            instance = browser_pool.instances["0"]
            assert instance.instance_id == "0"
            assert instance.alias is None

    async def test_lease_instance_fifo(self, browser_pool, mock_blob_manager, mock_middleware):
        # Create mock instances with proxy_client attribute
        instance0 = Mock(spec=BrowserInstance)
        instance0.mark_leased = Mock()
        instance0.mark_released = Mock()
        instance0.instance_id = "0"
        instance0.alias = None
        instance0.proxy_client = Mock()  # Add proxy_client for yield

        instance1 = Mock(spec=BrowserInstance)
        instance1.mark_leased = Mock()
        instance1.mark_released = Mock()
        instance1.instance_id = "1"
        instance1.alias = None
        instance1.proxy_client = Mock()  # Add proxy_client for yield

        # Mock _create_instance to populate instances dict
        async def mock_create_instance(cfg, bm, mw):
            if cfg["instance_id"] == "0":
                browser_pool.instances["0"] = instance0
            elif cfg["instance_id"] == "1":
                browser_pool.instances["1"] = instance1

        with patch.object(browser_pool, "_create_instance", new=mock_create_instance):
            await browser_pool.initialize(mock_blob_manager, mock_middleware)

        # Lease first instance (FIFO) - should get instance0's proxy_client
        async with browser_pool.lease_instance() as leased:
            assert leased == instance0.proxy_client
            instance0.mark_leased.assert_called_once()

        # Verify instance was released
        instance0.mark_released.assert_called_once()

    async def test_lease_instance_by_key(self, browser_pool, mock_blob_manager, mock_middleware):
        # Create mock instance with alias and proxy_client
        instance1 = Mock(spec=BrowserInstance)
        instance1.mark_leased = Mock()
        instance1.mark_released = Mock()
        instance1.alias = "debug"
        instance1.instance_id = "1"
        instance1.proxy_client = Mock()  # Add proxy_client for yield

        # Mock _create_instance to populate instances dict
        async def mock_create_instance(cfg, bm, mw):
            if cfg["instance_id"] == "1":
                browser_pool.instances["1"] = instance1

        with patch.object(browser_pool, "_create_instance", new=mock_create_instance):
            await browser_pool.initialize(mock_blob_manager, mock_middleware)

        # Lease by alias - should get instance1's proxy_client
        async with browser_pool.lease_instance("debug") as leased:
            assert leased == instance1.proxy_client
            instance1.mark_leased.assert_called_once()

        # Verify release
        instance1.mark_released.assert_called_once()

    async def test_get_status(self, browser_pool):
        # Create mock instance with all required attributes
        instance0 = Mock(spec=BrowserInstance)
        instance0.instance_id = "0"
        instance0.alias = None
        instance0.is_leased = False
        instance0.lease_duration_ms = None
        instance0.lease_started_at = None
        instance0.last_health_check = None
        instance0.health_check_error = None

        # Mock process manager
        mock_process = Mock()
        mock_process.pid = 12345
        instance0.process_manager = Mock()
        instance0.process_manager.process = mock_process

        # Add to pool
        browser_pool.instances["0"] = instance0

        status = await browser_pool.get_status()

        assert status["name"] == "TEST_POOL"
        assert status["is_default"] is True
        assert len(status["instances"]) == 1
        assert status["instances"][0]["id"] == "0"
        assert status["instances"][0]["leased"] is False

    async def test_stop(self, browser_pool):
        instance0 = AsyncMock(spec=BrowserInstance)
        instance1 = AsyncMock(spec=BrowserInstance)

        browser_pool.instances["0"] = instance0
        browser_pool.instances["1"] = instance1

        await browser_pool.stop()

        instance0.stop.assert_awaited_once()
        instance1.stop.assert_awaited_once()


class TestPoolManager:
    """Tests for PoolManager class"""

    @pytest.fixture
    def pool_manager_config(self):
        from playwright_proxy_mcp.playwright.config import PoolManagerConfig

        return PoolManagerConfig(
            global_config={},
            default_pool_name="DEFAULT",
            pools=[
                PoolConfig(
                    name="DEFAULT",
                    instances=1,
                    is_default=True,
                    description="Default pool",
                    base_config={},
                    instance_configs=[
                        InstanceConfig(
                            instance_id="0",
                            alias=None,
                            config={},
                        )
                    ],
                )
            ],
        )

    @pytest.fixture
    def mock_blob_manager(self):
        return Mock()

    @pytest.fixture
    def mock_middleware(self):
        return Mock()

    def test_init(self, pool_manager_config, mock_blob_manager, mock_middleware):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)
        # Pools are created in initialize(), not __init__
        assert len(manager.pools) == 0
        assert manager.default_pool_name == "DEFAULT"
        assert manager.blob_manager == mock_blob_manager
        assert manager.middleware == mock_middleware

    async def test_initialize(self, pool_manager_config, mock_blob_manager, mock_middleware):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Mock BrowserPool to avoid actual subprocess creation
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool_instance = AsyncMock()
            mock_pool_instance.initialize = AsyncMock()
            MockPool.return_value = mock_pool_instance

            await manager.initialize()

            # Verify pool was created and initialized
            assert len(manager.pools) == 1
            assert "DEFAULT" in manager.pools
            MockPool.assert_called_once()
            mock_pool_instance.initialize.assert_awaited_once_with(
                mock_blob_manager, mock_middleware
            )

    async def test_get_pool_default(self, pool_manager_config, mock_blob_manager, mock_middleware):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Initialize to create pools
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool_instance = AsyncMock()
            mock_pool_instance.name = "DEFAULT"
            # Add mock instance with health_check_error
            mock_instance = Mock()
            mock_instance.health_check_error = None  # Healthy instance
            mock_pool_instance.instances = {"0": mock_instance}
            MockPool.return_value = mock_pool_instance
            await manager.initialize()

        pool = manager.get_pool(None)
        assert pool.name == "DEFAULT"

    async def test_get_pool_by_name(self, pool_manager_config, mock_blob_manager, mock_middleware):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Initialize to create pools
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool_instance = AsyncMock()
            mock_pool_instance.name = "DEFAULT"
            # Add mock instance with health_check_error
            mock_instance = Mock()
            mock_instance.health_check_error = None  # Healthy instance
            mock_pool_instance.instances = {"0": mock_instance}
            MockPool.return_value = mock_pool_instance
            await manager.initialize()

        pool = manager.get_pool("DEFAULT")
        assert pool.name == "DEFAULT"

    async def test_get_pool_not_found(self, pool_manager_config, mock_blob_manager, mock_middleware):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Initialize to create pools
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool_instance = AsyncMock()
            MockPool.return_value = mock_pool_instance
            await manager.initialize()

        with pytest.raises(ValueError, match="Pool 'NONEXISTENT' not found"):
            manager.get_pool("NONEXISTENT")

    async def test_get_status_all_pools(
        self, pool_manager_config, mock_blob_manager, mock_middleware
    ):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Initialize and mock pool
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.get_status = AsyncMock(return_value={
                "name": "DEFAULT",
                "total_instances": 1,
                "healthy_instances": 1,
                "leased_instances": 0,
                "available_instances": 1,
            })
            # Add mock instance with health_check_error for health check
            mock_instance = Mock()
            mock_instance.health_check_error = None  # Healthy instance
            mock_pool.instances = {"0": mock_instance}
            MockPool.return_value = mock_pool
            await manager.initialize()

            status = await manager.get_status()
            assert "pools" in status
            assert len(status["pools"]) == 1
            assert status["pools"][0]["name"] == "DEFAULT"

    async def test_get_status_specific_pool(
        self, pool_manager_config, mock_blob_manager, mock_middleware
    ):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Initialize and mock pool
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.get_status = AsyncMock(return_value={
                "name": "DEFAULT",
                "total_instances": 1,
                "healthy_instances": 1,
                "leased_instances": 0,
                "available_instances": 1,
            })
            # Add mock instance with health_check_error for health check
            mock_instance = Mock()
            mock_instance.health_check_error = None  # Healthy instance
            mock_pool.instances = {"0": mock_instance}
            MockPool.return_value = mock_pool
            await manager.initialize()

            status = await manager.get_status("DEFAULT")
            assert "pools" in status
            assert len(status["pools"]) == 1
            assert status["pools"][0]["name"] == "DEFAULT"

    async def test_stop(self, pool_manager_config, mock_blob_manager, mock_middleware):
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        # Initialize to create pools
        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.stop = AsyncMock()
            MockPool.return_value = mock_pool
            await manager.initialize()

            await manager.stop()
            mock_pool.stop.assert_awaited_once()
