"""
Browser Pool Manager

Manages multiple browser instances organized into logical pools with FIFO leasing.
Implements the RAII pattern via async context managers for automatic resource cleanup.

Version 2.0.0
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncIterator

from leasedkeyq import LeasedKeyQueue

from .config import InstanceConfig, PoolConfig, PoolManagerConfig
from .process_manager import PlaywrightProcessManager
from .proxy_client import PlaywrightProxyClient

if TYPE_CHECKING:
    from .blob_manager import BlobManager  # type: ignore[attr-defined]
    from .middleware import BinaryInterceptMiddleware  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class BrowserInstance:
    """Represents a single browser instance (subprocess + proxy client)"""

    def __init__(
        self,
        instance_id: str,
        alias: str | None,
        proxy_client: PlaywrightProxyClient,
        process_manager: PlaywrightProcessManager,
    ):
        self.instance_id = instance_id
        self.alias = alias
        self.proxy_client = proxy_client
        self.process_manager = process_manager
        self.lease_started_at: datetime | None = None
        self.last_health_check: datetime | None = None
        self.health_check_error: str | None = None

    @property
    def is_leased(self) -> bool:
        """Check if instance is currently leased"""
        return self.lease_started_at is not None

    @property
    def lease_duration_ms(self) -> int | None:
        """Get lease duration in milliseconds"""
        if not self.lease_started_at:
            return None
        delta = datetime.now(timezone.utc) - self.lease_started_at
        return int(delta.total_seconds() * 1000)

    def mark_leased(self) -> None:
        """Mark instance as leased"""
        self.lease_started_at = datetime.now(timezone.utc)

    def mark_released(self) -> None:
        """Mark instance as released"""
        self.lease_started_at = None

    async def check_health(self) -> bool:
        """
        Check instance health by probing subprocess.

        Returns:
            True if healthy, False otherwise
        """
        self.last_health_check = datetime.now(timezone.utc)
        try:
            is_healthy = await self.proxy_client.is_healthy()
            if is_healthy:
                self.health_check_error = None
            else:
                self.health_check_error = "Health check returned False"
            return is_healthy
        except Exception as e:
            self.health_check_error = str(e)
            logger.warning(
                f"Health check failed for instance {self.instance_id}: {e}",
                exc_info=True,
            )
            return False

    async def stop(self) -> None:
        """Stop the browser instance"""
        try:
            await self.proxy_client.stop()
        except Exception as e:
            logger.error(f"Error stopping instance {self.instance_id}: {e}", exc_info=True)


class BrowserPool:
    """Manages a pool of browser instances with FIFO leasing"""

    def __init__(self, config: PoolConfig):
        self.name = config["name"]
        self.is_default = config["is_default"]
        self.description = config["description"]
        self.instances: dict[str, BrowserInstance] = {}
        self.lease_queue: LeasedKeyQueue[str, BrowserInstance] | None = None
        self._config = config

    async def initialize(
        self, blob_manager: "BlobManager", middleware: "BinaryInterceptMiddleware"
    ) -> None:
        """
        Initialize all browser instances in the pool.

        Args:
            blob_manager: Shared blob manager
            middleware: Shared binary intercept middleware
        """
        logger.info(f"Initializing pool '{self.name}' with {len(self._config['instance_configs'])} instances")

        # Create all instances
        for instance_cfg in self._config["instance_configs"]:
            await self._create_instance(instance_cfg, blob_manager, middleware)

        # Create lease queue
        self.lease_queue = LeasedKeyQueue[str, BrowserInstance]()

        # Populate queue with instances (by ID and alias)
        for instance_id, instance in self.instances.items():
            # Add by ID
            await self.lease_queue.put(instance_id, instance)
            # Add by alias if set
            if instance.alias:
                await self.lease_queue.put(instance.alias, instance)

        logger.info(f"Pool '{self.name}' initialized successfully")

    async def _create_instance(
        self,
        instance_cfg: InstanceConfig,
        blob_manager: "BlobManager",
        middleware: "BinaryInterceptMiddleware",
    ) -> None:
        """
        Create a single browser instance.

        Args:
            instance_cfg: Instance configuration
            blob_manager: Shared blob manager
            middleware: Shared binary intercept middleware
        """
        instance_id = instance_cfg["instance_id"]
        alias = instance_cfg["alias"]
        config = instance_cfg["config"]

        logger.info("="*50)
        logger.info(
            f"Creating instance {instance_id} in pool '{self.name}'"
            + (f" (alias: {alias})" if alias else "")
        )
        logger.debug(f"Instance config: browser={config.get('browser', 'N/A')}, "
                    f"headless={config.get('headless', 'N/A')}, "
                    f"wsl_windows={config.get('wsl_windows', False)}")

        try:
            # Create process manager
            logger.debug(f"  [1/4] Creating PlaywrightProcessManager for instance {instance_id}")
            process_manager = PlaywrightProcessManager()

            # Create proxy client
            logger.debug(f"  [2/4] Creating PlaywrightProxyClient for instance {instance_id}")
            proxy_client = PlaywrightProxyClient(process_manager, middleware)

            # Start proxy client (spawns subprocess)
            logger.info(f"  [3/4] Starting proxy client (spawning subprocess) for instance {instance_id}")
            await proxy_client.start(config)
            logger.debug(f"  Proxy client started for instance {instance_id}")

            # Register process with process manager for monitoring
            logger.debug(f"  [4/4] Registering process with process manager for instance {instance_id}")
            if proxy_client._client and hasattr(proxy_client._client, "_transport"):
                transport = proxy_client._client._transport  # type: ignore[attr-defined]
                if hasattr(transport, "_process"):
                    await process_manager.set_process(transport._process)
                    logger.debug(f"  Process registered (PID: {transport._process.pid if hasattr(transport._process, 'pid') else 'unknown'})")
                else:
                    logger.warning(f"  Transport has no _process attribute for instance {instance_id}")
            else:
                logger.warning(f"  Proxy client has no transport for instance {instance_id}")

            # Create instance wrapper
            instance = BrowserInstance(instance_id, alias, proxy_client, process_manager)

            # Store instance
            self.instances[instance_id] = instance

            logger.info(
                f"✓ Instance {instance_id} in pool '{self.name}' created successfully"
            )
            logger.info("="*50)

        except Exception as e:
            logger.error("="*50)
            logger.error(
                f"✗ Failed to create instance {instance_id} in pool '{self.name}': {e}",
                exc_info=True,
            )
            logger.error("="*50)
            raise RuntimeError(
                f"Pool '{self.name}' instance {instance_id} failed to start: {e}"
            ) from e

    @asynccontextmanager
    async def lease_instance(
        self, instance_key: str | None = None
    ) -> AsyncIterator[PlaywrightProxyClient]:
        """
        Lease a browser instance from the pool.

        This implements the RAII pattern via async context manager.
        The lease is automatically released when exiting the context,
        even if an exception occurs.

        Args:
            instance_key: Specific instance ID or alias, or None for any available

        Yields:
            PlaywrightProxyClient for the leased instance

        Raises:
            ValueError: If instance_key is invalid or pool is not initialized
            RuntimeError: If lease acquisition fails

        Examples:
            # Lease any available instance
            async with pool.lease_instance() as client:
                await client.call_tool(...)

            # Lease specific instance by ID
            async with pool.lease_instance("0") as client:
                await client.call_tool(...)

            # Lease specific instance by alias
            async with pool.lease_instance("main_browser") as client:
                await client.call_tool(...)
        """
        if not self.lease_queue:
            raise ValueError(f"Pool '{self.name}' not initialized")

        # Acquire lease from queue
        if instance_key:
            # Lease specific instance (blocks until available)
            try:
                key, instance, lease = await self.lease_queue.take(instance_key)
            except KeyError:
                raise ValueError(
                    f"Pool '{self.name}': Instance '{instance_key}' not found "
                    f"(available IDs: {list(self.instances.keys())})"
                )
        else:
            # Lease first available (FIFO)
            key, instance, lease = await self.lease_queue.get()

        # Mark as leased
        instance.mark_leased()

        logger.debug(
            f"Leased instance {instance.instance_id} from pool '{self.name}'"
            + (f" (requested: {instance_key})" if instance_key else " (any)")
        )

        try:
            # Yield proxy client to caller
            yield instance.proxy_client
        finally:
            # Always release lease, even on exception
            instance.mark_released()

            # Return instance to queue for reuse
            await self.lease_queue.release(lease)

            logger.debug(
                f"Released instance {instance.instance_id} to pool '{self.name}'"
            )

    async def get_status(self) -> dict:
        """
        Get pool status including instance health.

        Returns:
            Dictionary with pool status information
        """
        # Gather instance statuses
        instance_statuses = []

        for instance_id, instance in sorted(self.instances.items()):
            # Get config for this instance
            instance_cfg = next(
                (cfg for cfg in self._config["instance_configs"] if cfg["instance_id"] == instance_id),
                None,
            )

            config = instance_cfg["config"] if instance_cfg else {}

            # Determine status
            if instance.health_check_error:
                status = "failed"
                responsive = False
            else:
                status = "healthy"
                responsive = True

            instance_status = {
                "id": instance_id,
                "alias": instance.alias,
                "status": status,
                "leased": instance.is_leased,
                "lease_duration_ms": instance.lease_duration_ms,
                "lease_started_at": (
                    instance.lease_started_at.isoformat() if instance.lease_started_at else None
                ),
                "browser": config.get("browser", "unknown"),
                "headless": config.get("headless", True),
                "process_id": (
                    instance.process_manager.process.pid
                    if instance.process_manager.process
                    else None
                ),
                "health_check": {
                    "last_check": (
                        instance.last_health_check.isoformat()
                        if instance.last_health_check
                        else None
                    ),
                    "responsive": responsive,
                    "error": instance.health_check_error,
                },
            }

            instance_statuses.append(instance_status)

        # Count instance states
        total_instances = len(self.instances)
        healthy_instances = sum(1 for s in instance_statuses if s["status"] == "healthy")
        leased_instances = sum(1 for s in instance_statuses if s["leased"])
        available_instances = sum(
            1 for s in instance_statuses if s["status"] == "healthy" and not s["leased"]
        )

        return {
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "total_instances": total_instances,
            "healthy_instances": healthy_instances,
            "leased_instances": leased_instances,
            "available_instances": available_instances,
            "instances": instance_statuses,
        }

    async def check_all_health(self) -> None:
        """Check health of all instances (bypasses leasing)"""
        logger.debug(f"Running health checks for pool '{self.name}'")

        # Check all instances concurrently
        tasks = [instance.check_health() for instance in self.instances.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        for instance, result in zip(self.instances.values(), results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Health check exception for instance {instance.instance_id}: {result}"
                )
            elif not result:
                logger.warning(
                    f"Instance {instance.instance_id} is unhealthy: {instance.health_check_error}"
                )

    async def stop(self) -> None:
        """Stop all instances in the pool"""
        logger.info(f"Stopping pool '{self.name}'")

        # Stop all instances concurrently
        tasks = [instance.stop() for instance in self.instances.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Pool '{self.name}' stopped")


class PoolManager:
    """Manages multiple browser pools"""

    def __init__(
        self,
        config: PoolManagerConfig,
        blob_manager: "BlobManager",
        middleware: "BinaryInterceptMiddleware",
    ):
        self.config = config
        self.blob_manager = blob_manager
        self.middleware = middleware
        self.pools: dict[str, BrowserPool] = {}
        self.default_pool_name = config["default_pool_name"]
        self._health_check_task: asyncio.Task | None = None
        self._health_check_interval = 20  # seconds

    async def initialize(self) -> None:
        """Initialize all pools"""
        logger.info(
            f"Initializing pool manager with {len(self.config['pools'])} pools"
        )

        # Create and initialize all pools
        for pool_config in self.config["pools"]:
            pool = BrowserPool(pool_config)
            await pool.initialize(self.blob_manager, self.middleware)
            self.pools[pool_config["name"]] = pool

        logger.info(
            f"Pool manager initialized. Default pool: '{self.default_pool_name}'"
        )

        # Start health check background task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Background task that periodically health checks all instances"""
        logger.info(f"Starting health check loop (interval: {self._health_check_interval}s)")

        try:
            while True:
                await asyncio.sleep(self._health_check_interval)

                # Check all pools
                for pool in self.pools.values():
                    try:
                        await pool.check_all_health()
                    except Exception as e:
                        logger.error(
                            f"Error during health check for pool '{pool.name}': {e}",
                            exc_info=True,
                        )

        except asyncio.CancelledError:
            logger.info("Health check loop cancelled")
            raise

    def get_pool(self, pool_name: str | None = None) -> BrowserPool:
        """
        Get pool by name.

        Args:
            pool_name: Pool name, or None for default pool

        Returns:
            BrowserPool instance

        Raises:
            ValueError: If pool not found or default pool unhealthy
        """
        # Use default pool if not specified
        if not pool_name:
            pool_name = self.default_pool_name

        # Check pool exists
        if pool_name not in self.pools:
            available = ", ".join(self.pools.keys())
            raise ValueError(
                f"Pool '{pool_name}' not found. Available pools: {available}"
            )

        pool = self.pools[pool_name]

        # If this is the default pool and it was requested implicitly,
        # check that it has healthy instances
        if not pool_name or pool_name == self.default_pool_name:
            healthy_count = sum(
                1
                for instance in pool.instances.values()
                if not instance.health_check_error
            )

            if healthy_count == 0:
                raise ValueError(
                    f"Default pool '{pool.name}' has no healthy instances. "
                    f"Specify explicit pool or restart failed instances."
                )

        return pool

    @asynccontextmanager
    async def lease_instance(
        self, pool_name: str | None = None, instance_key: str | None = None
    ) -> AsyncIterator[PlaywrightProxyClient]:
        """
        Convenience method to lease an instance from a pool.

        Args:
            pool_name: Pool name, or None for default pool
            instance_key: Instance ID/alias, or None for any available

        Yields:
            PlaywrightProxyClient for the leased instance
        """
        pool = self.get_pool(pool_name)
        async with pool.lease_instance(instance_key) as client:
            yield client

    async def get_status(self, pool_name: str | None = None) -> dict:
        """
        Get status of all pools or specific pool.

        Args:
            pool_name: Pool name, or None for all pools

        Returns:
            Dictionary with pool status information
        """
        if pool_name:
            # Single pool status
            pool = self.get_pool(pool_name)
            pool_status = await pool.get_status()
            return {
                "pools": [pool_status],
                "summary": {
                    "total_pools": 1,
                    "total_instances": pool_status["total_instances"],
                    "healthy_instances": pool_status["healthy_instances"],
                    "failed_instances": pool_status["total_instances"]
                    - pool_status["healthy_instances"],
                    "leased_instances": pool_status["leased_instances"],
                    "available_instances": pool_status["available_instances"],
                },
            }
        else:
            # All pools status
            pool_statuses = []
            total_instances = 0
            healthy_instances = 0
            failed_instances = 0
            leased_instances = 0
            available_instances = 0

            for pool in self.pools.values():
                status = await pool.get_status()
                pool_statuses.append(status)

                total_instances += status["total_instances"]
                healthy_instances += status["healthy_instances"]
                failed_instances += status["total_instances"] - status["healthy_instances"]
                leased_instances += status["leased_instances"]
                available_instances += status["available_instances"]

            return {
                "pools": pool_statuses,
                "summary": {
                    "total_pools": len(self.pools),
                    "total_instances": total_instances,
                    "healthy_instances": healthy_instances,
                    "failed_instances": failed_instances,
                    "leased_instances": leased_instances,
                    "available_instances": available_instances,
                },
            }

    async def stop(self) -> None:
        """Stop all pools and cleanup"""
        logger.info("Stopping pool manager")

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Stop all pools concurrently
        tasks = [pool.stop() for pool in self.pools.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Pool manager stopped")
