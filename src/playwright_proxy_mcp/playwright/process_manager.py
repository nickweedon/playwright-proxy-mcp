"""
Process manager for playwright-mcp subprocess

Simplified helper for managing the playwright-mcp subprocess lifecycle
when using stdio transport. The actual subprocess creation is handled
by StdioTransport, but this class provides logging and monitoring.
"""

import asyncio
import logging
from asyncio.subprocess import Process

logger = logging.getLogger(__name__)


class PlaywrightProcessManager:
    """Manages playwright-mcp subprocess logging and monitoring"""

    def __init__(self) -> None:
        self.process: Process | None = None
        self._shutdown_event = asyncio.Event()

    async def is_healthy(self) -> bool:
        """
        Check if subprocess is running.

        Returns:
            True if process exists and is still running
        """
        if self.process is None:
            return False
        return self.process.returncode is None

    async def set_process(self, process: Process) -> None:
        """
        Set the subprocess for monitoring.

        This is called by proxy_client after StdioTransport creates the subprocess.

        Args:
            process: The subprocess to monitor
        """
        self.process = process
        logger.info(f"Process monitoring started (PID: {process.pid})")

        # Start background tasks to log stdout/stderr with prefix
        self._stdout_task = asyncio.create_task(self._log_stdout())
        self._stderr_task = asyncio.create_task(self._log_stderr())

    async def stop(self) -> None:
        """Stop monitoring and cleanup logging tasks"""
        if self.process is None:
            return

        logger.info("Stopping process monitoring...")

        # Cancel stdout/stderr logging tasks
        if hasattr(self, "_stdout_task") and self._stdout_task:
            self._stdout_task.cancel()
            try:
                await self._stdout_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, "_stderr_task") and self._stderr_task:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass

        self.process = None
        logger.info("Process monitoring stopped")

    async def _log_stdout(self) -> None:
        """
        Background task to read and log stdout from subprocess.
        Uses UPSTREAM_MCP prefix to distinguish from proxy logs.
        """
        if not self.process or not self.process.stdout:
            logger.error("No stdout to log from subprocess")
            return

        logger.debug("Logging stdout from subprocess")

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    logger.debug("No more stdout output from subprocess")
                    break

                # Decode and log stdout output
                stdout_line = line.decode("utf-8", errors="replace").rstrip()
                if stdout_line:
                    logger.info(f"UPSTREAM_MCP [stdout] {stdout_line}")

        except asyncio.CancelledError:
            logger.debug("Stdout logger task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in stdout logger: {e}")

    async def _log_stderr(self) -> None:
        """
        Background task to read and log stderr from subprocess.
        Uses UPSTREAM_MCP prefix to distinguish from proxy logs.
        """
        if not self.process or not self.process.stderr:
            logger.error("No stderr to log from subprocess")
            return

        logger.debug("Logging stderr from subprocess")

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    logger.debug("No more stderr output from subprocess")
                    break

                # Decode and log stderr output
                stderr_line = line.decode("utf-8", errors="replace").rstrip()
                if stderr_line:
                    logger.warning(f"UPSTREAM_MCP [stderr] {stderr_line}")

        except asyncio.CancelledError:
            logger.debug("Stderr logger task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in stderr logger: {e}")
