"""Tests for pool_manager module."""

import asyncio
from contextlib import asynccontextmanager
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
        ) as MockClient, patch(
            "playwright_proxy_mcp.playwright.pool_manager.PlaywrightProcessManager"
        ) as MockProcessManager:
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            MockClient.return_value = mock_client

            mock_process = AsyncMock()
            mock_process.set_process = AsyncMock()
            MockProcessManager.return_value = mock_process

            await browser_pool._create_instance(instance_cfg, mock_blob_manager, mock_middleware)

            assert "0" in browser_pool.instances
            instance = browser_pool.instances["0"]
            assert instance.instance_id == "0"
            assert instance.alias is None
            mock_client.start.assert_awaited_once()

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


class TestBrowserInstanceAdditional:
    """Additional tests for BrowserInstance."""

    @pytest.fixture
    def mock_proxy_client(self):
        client = AsyncMock()
        client.is_healthy = AsyncMock(return_value=True)
        client.stop = AsyncMock()
        return client

    @pytest.fixture
    def mock_process_manager(self):
        manager = Mock()
        manager.process = Mock()
        manager.process.pid = 12345
        return manager

    @pytest.fixture
    def instance(self, mock_proxy_client, mock_process_manager):
        return BrowserInstance(
            instance_id="test-instance",
            alias="test-alias",
            proxy_client=mock_proxy_client,
            process_manager=mock_process_manager,
        )

    def test_lease_duration_with_no_lease(self, instance):
        """Test lease_duration_ms returns None when not leased."""
        assert instance.lease_duration_ms is None

    def test_mark_leased_sets_timestamp(self, instance):
        """Test mark_leased sets the lease_started_at timestamp."""
        before = datetime.now(timezone.utc)
        instance.mark_leased()
        after = datetime.now(timezone.utc)

        assert instance.lease_started_at is not None
        assert before <= instance.lease_started_at <= after

    def test_mark_released_clears_timestamp(self, instance):
        """Test mark_released clears the lease_started_at timestamp."""
        instance.mark_leased()
        instance.mark_released()
        assert instance.lease_started_at is None

    async def test_check_health_returns_true_when_healthy(self, instance, mock_proxy_client):
        """Test check_health returns True when proxy client is healthy."""
        mock_proxy_client.is_healthy.return_value = True
        result = await instance.check_health()
        assert result is True
        assert instance.health_check_error is None

    async def test_check_health_returns_false_when_unhealthy(self, instance, mock_proxy_client):
        """Test check_health returns False when proxy client is unhealthy."""
        mock_proxy_client.is_healthy.return_value = False
        result = await instance.check_health()
        assert result is False
        assert instance.health_check_error is not None


class TestBrowserPoolAdditional:
    """Additional tests for BrowserPool."""

    @pytest.fixture
    def pool_config(self):
        return PoolConfig(
            name="EXTRA_POOL",
            instances=3,
            is_default=False,
            description="Extra pool for testing",
            base_config={"browser": "firefox"},
            instance_configs=[
                InstanceConfig(instance_id="0", alias=None, config={}),
                InstanceConfig(instance_id="1", alias="primary", config={}),
                InstanceConfig(instance_id="2", alias="secondary", config={}),
            ],
        )

    @pytest.fixture
    def browser_pool(self, pool_config):
        return BrowserPool(pool_config)

    def test_pool_attributes(self, browser_pool):
        """Test pool attributes are set correctly."""
        assert browser_pool.name == "EXTRA_POOL"
        assert browser_pool.is_default is False
        assert browser_pool.description == "Extra pool for testing"

    async def test_stop_pool(self, browser_pool):
        """Test stop() stops all instances."""
        # Create mock instances
        instance0 = AsyncMock()
        instance1 = AsyncMock()
        browser_pool.instances["0"] = instance0
        browser_pool.instances["1"] = instance1

        await browser_pool.stop()

        instance0.stop.assert_awaited_once()
        instance1.stop.assert_awaited_once()

    async def test_check_all_health(self, browser_pool):
        """Test check_all_health checks all instances."""
        instance0 = AsyncMock()
        instance0.check_health = AsyncMock(return_value=True)
        instance1 = AsyncMock()
        instance1.check_health = AsyncMock(return_value=False)

        browser_pool.instances["0"] = instance0
        browser_pool.instances["1"] = instance1

        await browser_pool.check_all_health()

        instance0.check_health.assert_awaited_once()
        instance1.check_health.assert_awaited_once()


class TestPoolManagerAdditional:
    """Additional tests for PoolManager."""

    @pytest.fixture
    def multi_pool_config(self):
        from playwright_proxy_mcp.playwright.config import PoolManagerConfig

        return PoolManagerConfig(
            global_config={"browser": "chromium"},
            default_pool_name="DEFAULT",
            pools=[
                PoolConfig(
                    name="DEFAULT",
                    instances=1,
                    is_default=True,
                    description="Default pool",
                    base_config={},
                    instance_configs=[
                        InstanceConfig(instance_id="0", alias=None, config={})
                    ],
                ),
                PoolConfig(
                    name="FIREFOX",
                    instances=1,
                    is_default=False,
                    description="Firefox pool",
                    base_config={"browser": "firefox"},
                    instance_configs=[
                        InstanceConfig(instance_id="0", alias=None, config={})
                    ],
                ),
            ],
        )

    @pytest.fixture
    def mock_blob_manager(self):
        return Mock()

    @pytest.fixture
    def mock_middleware(self):
        return Mock()

    async def test_initialize_multiple_pools(
        self, multi_pool_config, mock_blob_manager, mock_middleware
    ):
        """Test initializing pool manager with multiple pools."""
        manager = PoolManager(multi_pool_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.initialize = AsyncMock()
            MockPool.return_value = mock_pool

            await manager.initialize()

            assert len(manager.pools) == 2
            assert "DEFAULT" in manager.pools
            assert "FIREFOX" in manager.pools

    async def test_get_status_summary(
        self, multi_pool_config, mock_blob_manager, mock_middleware
    ):
        """Test get_status returns summary data."""
        manager = PoolManager(multi_pool_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.get_status = AsyncMock(return_value={
                "name": "TEST",
                "total_instances": 1,
                "healthy_instances": 1,
                "leased_instances": 0,
                "available_instances": 1,
            })
            mock_instance = Mock()
            mock_instance.health_check_error = None
            mock_pool.instances = {"0": mock_instance}
            MockPool.return_value = mock_pool

            await manager.initialize()
            status = await manager.get_status()

            assert "summary" in status
            assert "total_pools" in status["summary"]
            assert "total_instances" in status["summary"]

    async def test_get_pool_raises_on_not_found(
        self, multi_pool_config, mock_blob_manager, mock_middleware
    ):
        """Test get_pool raises ValueError for non-existent pool."""
        manager = PoolManager(multi_pool_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            MockPool.return_value = mock_pool
            await manager.initialize()

        with pytest.raises(ValueError, match="not found"):
            manager.get_pool("WEBKIT")

    async def test_stop_multiple_pools(
        self, multi_pool_config, mock_blob_manager, mock_middleware
    ):
        """Test stop stops all pools."""
        manager = PoolManager(multi_pool_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.stop = AsyncMock()
            MockPool.return_value = mock_pool

            await manager.initialize()
            await manager.stop()

            # stop should be called for each pool
            assert mock_pool.stop.await_count == 2


class TestBrowserPoolLeasing:
    """Tests for BrowserPool leasing functionality."""

    @pytest.fixture
    def pool_config(self):
        return PoolConfig(
            name="LEASE_POOL",
            instances=2,
            is_default=True,
            description="Pool for lease testing",
            base_config={},
            instance_configs=[
                InstanceConfig(instance_id="0", alias="first", config={}),
                InstanceConfig(instance_id="1", alias="second", config={}),
            ],
        )

    @pytest.fixture
    def browser_pool(self, pool_config):
        return BrowserPool(pool_config)

    async def test_lease_instance_not_initialized(self, browser_pool):
        """Test lease_instance raises when pool not initialized."""
        with pytest.raises(ValueError, match="not initialized"):
            async with browser_pool.lease_instance():
                pass

    async def test_lease_instance_invalid_key_raises(self, browser_pool):
        """Test lease_instance raises ValueError for non-existent key."""
        # Create mock instances
        instance0 = Mock(spec=BrowserInstance)
        instance0.mark_leased = Mock()
        instance0.mark_released = Mock()
        instance0.instance_id = "0"
        instance0.alias = "first"
        instance0.proxy_client = Mock()

        async def mock_create_instance(cfg, bm, mw):
            if cfg["instance_id"] == "0":
                browser_pool.instances["0"] = instance0

        with patch.object(browser_pool, "_create_instance", new=mock_create_instance):
            await browser_pool.initialize(Mock(), Mock())

        # Attempting to lease a non-existent key should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            async with browser_pool.lease_instance("nonexistent"):
                pass

    async def test_lease_instance_by_id(self, browser_pool):
        """Test leasing specific instance by ID."""
        instance0 = Mock(spec=BrowserInstance)
        instance0.mark_leased = Mock()
        instance0.mark_released = Mock()
        instance0.instance_id = "0"
        instance0.alias = "first"
        instance0.proxy_client = Mock()

        async def mock_create_instance(cfg, bm, mw):
            if cfg["instance_id"] == "0":
                browser_pool.instances["0"] = instance0

        with patch.object(browser_pool, "_create_instance", new=mock_create_instance):
            await browser_pool.initialize(Mock(), Mock())

        async with browser_pool.lease_instance("0") as client:
            assert client == instance0.proxy_client
            instance0.mark_leased.assert_called_once()

    async def test_lease_instance_by_alias(self, browser_pool):
        """Test leasing specific instance by alias."""
        instance0 = Mock(spec=BrowserInstance)
        instance0.mark_leased = Mock()
        instance0.mark_released = Mock()
        instance0.instance_id = "0"
        instance0.alias = "first"
        instance0.proxy_client = Mock()

        async def mock_create_instance(cfg, bm, mw):
            if cfg["instance_id"] == "0":
                browser_pool.instances["0"] = instance0

        with patch.object(browser_pool, "_create_instance", new=mock_create_instance):
            await browser_pool.initialize(Mock(), Mock())

        # Lease by alias should work too
        async with browser_pool.lease_instance("first") as client:
            assert client == instance0.proxy_client
            instance0.mark_leased.assert_called_once()


class TestPoolManagerHealthCheck:
    """Tests for PoolManager health check functionality."""

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
                        InstanceConfig(instance_id="0", alias=None, config={})
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

    async def test_health_check_loop_cancellation(
        self, pool_manager_config, mock_blob_manager, mock_middleware
    ):
        """Test health check loop handles cancellation."""
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.check_all_health = AsyncMock()
            mock_pool.stop = AsyncMock()
            MockPool.return_value = mock_pool

            await manager.initialize()

            # Health check task should be running
            assert manager._health_check_task is not None
            assert not manager._health_check_task.done()

            # Stop should cancel it cleanly
            await manager.stop()

            assert manager._health_check_task.done()

    async def test_get_pool_no_healthy_instances(
        self, pool_manager_config, mock_blob_manager, mock_middleware
    ):
        """Test get_pool raises when default pool has no healthy instances."""
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.name = "DEFAULT"
            # All instances have errors
            mock_instance = Mock()
            mock_instance.health_check_error = "Connection failed"
            mock_pool.instances = {"0": mock_instance}
            MockPool.return_value = mock_pool

            await manager.initialize()

        with pytest.raises(ValueError, match="no healthy instances"):
            manager.get_pool(None)

    async def test_lease_instance_convenience_method(
        self, pool_manager_config, mock_blob_manager, mock_middleware
    ):
        """Test PoolManager.lease_instance convenience method."""
        manager = PoolManager(pool_manager_config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.name = "DEFAULT"
            mock_instance = Mock()
            mock_instance.health_check_error = None
            mock_pool.instances = {"0": mock_instance}

            # Mock lease_instance to return a context manager
            @asynccontextmanager
            async def mock_lease(key=None):
                yield Mock()

            mock_pool.lease_instance = mock_lease
            MockPool.return_value = mock_pool

            await manager.initialize()

            # Use convenience method
            async with manager.lease_instance() as client:
                assert client is not None


class TestBrowserPoolStatus:
    """Tests for BrowserPool status reporting."""

    @pytest.fixture
    def pool_config(self):
        return PoolConfig(
            name="STATUS_POOL",
            instances=2,
            is_default=False,
            description="Status test pool",
            base_config={"browser": "chromium"},
            instance_configs=[
                InstanceConfig(instance_id="0", alias=None, config={}),
                InstanceConfig(instance_id="1", alias="debug", config={"headless": False}),
            ],
        )

    @pytest.fixture
    def browser_pool(self, pool_config):
        return BrowserPool(pool_config)

    async def test_get_status_with_leased_instance(self, browser_pool):
        """Test get_status reports leased instances correctly."""
        # Create mock instances
        instance0 = Mock(spec=BrowserInstance)
        instance0.instance_id = "0"
        instance0.alias = None
        instance0.is_leased = True
        instance0.lease_duration_ms = 5000
        instance0.lease_started_at = datetime.now(timezone.utc)
        instance0.last_health_check = None
        instance0.health_check_error = None
        instance0.process_manager = Mock()
        instance0.process_manager.process = None

        browser_pool.instances["0"] = instance0

        status = await browser_pool.get_status()

        assert status["leased_instances"] == 1
        assert status["instances"][0]["leased"] is True

    async def test_get_status_with_failed_instance(self, browser_pool):
        """Test get_status reports failed instances correctly."""
        instance0 = Mock(spec=BrowserInstance)
        instance0.instance_id = "0"
        instance0.alias = None
        instance0.is_leased = False
        instance0.lease_duration_ms = None
        instance0.lease_started_at = None
        instance0.last_health_check = datetime.now(timezone.utc)
        instance0.health_check_error = "Connection refused"
        instance0.process_manager = Mock()
        instance0.process_manager.process = None

        browser_pool.instances["0"] = instance0

        status = await browser_pool.get_status()

        assert status["healthy_instances"] == 0
        assert status["instances"][0]["status"] == "failed"
        assert status["instances"][0]["health_check"]["error"] == "Connection refused"


class TestBrowserInstanceProperties:
    """Tests for BrowserInstance property methods."""

    @pytest.fixture
    def mock_proxy_client(self):
        client = AsyncMock()
        client.is_healthy = AsyncMock(return_value=True)
        client.stop = AsyncMock()
        return client

    @pytest.fixture
    def mock_process_manager(self):
        manager = Mock()
        manager.process = Mock()
        manager.process.pid = 54321
        return manager

    def test_lease_duration_ms_calculation(self, mock_proxy_client, mock_process_manager):
        """Test lease_duration_ms calculates correct duration."""
        import time

        instance = BrowserInstance(
            instance_id="0",
            alias=None,
            proxy_client=mock_proxy_client,
            process_manager=mock_process_manager,
        )

        instance.mark_leased()
        time.sleep(0.1)  # 100ms
        duration = instance.lease_duration_ms

        assert duration is not None
        assert duration >= 100  # At least 100ms

    def test_is_leased_after_mark_and_release(self, mock_proxy_client, mock_process_manager):
        """Test is_leased property after mark and release cycle."""
        instance = BrowserInstance(
            instance_id="0",
            alias=None,
            proxy_client=mock_proxy_client,
            process_manager=mock_process_manager,
        )

        assert not instance.is_leased
        instance.mark_leased()
        assert instance.is_leased
        instance.mark_released()
        assert not instance.is_leased


class TestPoolManagerConfiguration:
    """Tests for PoolManager configuration handling."""

    @pytest.fixture
    def mock_blob_manager(self):
        return Mock()

    @pytest.fixture
    def mock_middleware(self):
        return Mock()

    def test_health_check_interval_default(self, mock_blob_manager, mock_middleware):
        """Test default health check interval is set."""
        from playwright_proxy_mcp.playwright.config import PoolManagerConfig

        config = PoolManagerConfig(
            global_config={},
            default_pool_name="DEFAULT",
            pools=[
                PoolConfig(
                    name="DEFAULT",
                    instances=1,
                    is_default=True,
                    description="",
                    base_config={},
                    instance_configs=[
                        InstanceConfig(instance_id="0", alias=None, config={})
                    ],
                )
            ],
        )

        manager = PoolManager(config, mock_blob_manager, mock_middleware)
        assert manager._health_check_interval == 20

    async def test_initialize_starts_health_check_task(
        self, mock_blob_manager, mock_middleware
    ):
        """Test initialize starts health check background task."""
        from playwright_proxy_mcp.playwright.config import PoolManagerConfig

        config = PoolManagerConfig(
            global_config={},
            default_pool_name="DEFAULT",
            pools=[
                PoolConfig(
                    name="DEFAULT",
                    instances=1,
                    is_default=True,
                    description="",
                    base_config={},
                    instance_configs=[
                        InstanceConfig(instance_id="0", alias=None, config={})
                    ],
                )
            ],
        )

        manager = PoolManager(config, mock_blob_manager, mock_middleware)

        with patch("playwright_proxy_mcp.playwright.pool_manager.BrowserPool") as MockPool:
            mock_pool = AsyncMock()
            mock_pool.initialize = AsyncMock()
            mock_pool.stop = AsyncMock()
            MockPool.return_value = mock_pool

            await manager.initialize()

            assert manager._health_check_task is not None
            assert not manager._health_check_task.done()

            await manager.stop()
