"""
Process manager for playwright-mcp subprocess

Handles spawning, lifecycle management, and communication with the
playwright-mcp Node.js server via npx.
"""

import asyncio
import os
import shutil
from asyncio.subprocess import Process

from ..utils.logging_config import get_logger, log_dict
from .config import PLAYWRIGHT_HTTP_HOST, PLAYWRIGHT_HTTP_PORT, PlaywrightConfig

logger = get_logger(__name__)


class PlaywrightProcessManager:
    """Manages the playwright-mcp subprocess lifecycle"""

    def __init__(self) -> None:
        self.process: Process | None = None
        self._shutdown_event = asyncio.Event()
        self._actual_port: int | None = None  # Discovered port from server output

    async def start(self, config: PlaywrightConfig) -> Process:
        """
        Start the playwright-mcp subprocess.

        Args:
            config: Playwright configuration

        Returns:
            The subprocess Process object

        Raises:
            RuntimeError: If npx is not available or process fails to start
        """
        logger.info("=" * 80)
        logger.info("Configuring playwright-mcp subprocess")
        logger.info("=" * 80)

        # Prefer Linux-native Node.js over Windows interop
        # Check for nvm installation first
        home_dir = os.path.expanduser("~")
        nvm_dir = os.path.join(home_dir, ".nvm")
        nvm_node_path = None

        if os.path.isdir(nvm_dir):
            # Find the default or latest node version in nvm
            versions_dir = os.path.join(nvm_dir, "versions", "node")
            if os.path.isdir(versions_dir):
                versions = [d for d in os.listdir(versions_dir) if os.path.isdir(os.path.join(versions_dir, d))]
                if versions:
                    # Sort versions and take the latest
                    versions.sort(reverse=True)
                    latest_version = versions[0]
                    nvm_node_path = os.path.join(versions_dir, latest_version, "bin")
                    logger.info(f"Found nvm Node.js installation: {latest_version} at {nvm_node_path}")

        # Check if npx is available, preferring nvm installation
        npx_path = None
        node_path = None
        if nvm_node_path:
            nvm_npx = os.path.join(nvm_node_path, "npx")
            nvm_node = os.path.join(nvm_node_path, "node")
            if os.path.isfile(nvm_npx) and os.path.isfile(nvm_node):
                npx_path = nvm_npx
                node_path = nvm_node
                logger.info(f"Using nvm npx: {npx_path}")
                logger.info(f"Using nvm node: {node_path}")

        if not npx_path:
            npx_path = shutil.which("npx")
            node_path = shutil.which("node")

        if not npx_path:
            logger.error("npx not found in PATH or nvm installation")
            raise RuntimeError(
                "npx not found. Please ensure Node.js is installed and npx is in PATH."
            )
        logger.info(f"npx found at: {npx_path}")

        # Verify we're using a Linux binary (not Windows .exe via WSL interop)
        if node_path:
            try:
                import subprocess
                result = subprocess.run(
                    ["file", node_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "ELF" in result.stdout:
                    logger.info(f"✓ Verified Linux ELF binary: {node_path}")
                elif "Windows" in result.stdout or ".exe" in result.stdout.lower():
                    logger.warning(
                        f"⚠ Windows binary detected: {node_path}. "
                        "This may cause UNC path issues in WSL. "
                        "Consider installing Linux-native Node.js via nvm."
                    )
                else:
                    logger.info(f"Node binary type: {result.stdout.strip()}")
            except Exception as e:
                logger.debug(f"Could not verify node binary type: {e}")

        # Build command using the resolved npx path
        command = await self._build_command(config, npx_path)

        logger.info("Playwright MCP command configuration:")
        logger.info(f"  Command: {'\n'.join(command)}")
        logger.info(f"  Working directory: {os.getcwd()}")

        # Log configuration (redacting sensitive values)
        logger.info("Playwright configuration:")
        log_dict(logger, "Configuration parameters:", dict(config))

        try:
            # Prepare environment variables for subprocess
            #env = {k: v for k, v in os.environ.items() if k in ["PATH", "NODE_ENV"]}
            env = os.environ.copy()

            # Ensure nvm node binaries are in PATH (if using nvm)
            if nvm_node_path:
                # Prepend nvm path to ensure it takes precedence over Windows Node.js
                current_path = env.get("PATH", "")
                env["PATH"] = f"{nvm_node_path}:{current_path}"
                logger.info(f"Prepended nvm path to PATH: {nvm_node_path}")

            # Pass through extension token if configured
            if "extension_token" in config and config["extension_token"]:
                env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = config["extension_token"]

            # Log subprocess environment variables
            if env:
                logger.info("Subprocess environment variables:")
                for key, value in env.items():
                    logger.info(f"  {key}: {value}")
            else:
                logger.info("No subprocess environment variables set")

            logger.info("Launching playwright-mcp subprocess...")

            # Start subprocess with HTTP mode (no stdin needed, stdout/stderr for logging)
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,  # No stdin needed for HTTP mode
                stdout=asyncio.subprocess.PIPE,  # Keep for logging
                stderr=asyncio.subprocess.PIPE,  # Keep for logging
                env=env,
            )

            logger.info(f"Process created with PID: {self.process.pid}")

            # Start background tasks to log stdout/stderr
            self._stdout_task = asyncio.create_task(self._log_stdout())
            self._stderr_task = asyncio.create_task(self._log_stderr())

            # Wait for HTTP server to be ready
            logger.info("Waiting for HTTP server to be ready...")
            ready = await self._wait_for_http_ready(timeout=10.0)

            if not ready:
                # Process may have crashed - check returncode
                if self.process.returncode is not None:
                    raise RuntimeError(
                        f"playwright-mcp HTTP server failed to start (exit code {self.process.returncode}). "
                        "Check logs for UPSTREAM_MCP [stderr] messages."
                    )
                else:
                    raise RuntimeError(
                        "playwright-mcp HTTP server did not become ready within 10 seconds"
                    )

            logger.info("playwright-mcp HTTP server is ready")

            logger.info(f"playwright-mcp started successfully (PID: {self.process.pid})")
            logger.info("=" * 80)
            return self.process

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"Failed to start playwright-mcp: {e}")
            logger.error("=" * 80)

            # Try to capture any process output if available
            if self.process:
                try:
                    if self.process.returncode is None:
                        # Process is still running, try to get partial output
                        logger.info("Process is still running, attempting to capture output...")
                        self.process.terminate()
                        try:
                            await asyncio.wait_for(self.process.wait(), timeout=2.0)
                        except asyncio.TimeoutError:
                            self.process.kill()
                            await self.process.wait()

                    # Collect any available output
                    if self.process.stderr:
                        stderr_data = await self.process.stderr.read()
                        if stderr_data:
                            logger.error(
                                f"Process STDERR:\n{stderr_data.decode('utf-8', errors='ignore')}"
                            )

                    if self.process.stdout:
                        stdout_data = await self.process.stdout.read()
                        if stdout_data:
                            logger.error(
                                f"Process STDOUT:\n{stdout_data.decode('utf-8', errors='ignore')}"
                            )

                    if self.process.returncode is not None:
                        logger.error(f"Process exit code: {self.process.returncode}")

                except Exception as cleanup_error:
                    logger.error(f"Error during cleanup: {cleanup_error}")

            raise RuntimeError(f"Failed to start playwright-mcp: {e}") from e

    async def stop(self) -> None:
        """Stop the playwright-mcp subprocess gracefully"""
        if self.process is None:
            return

        logger.info("Stopping playwright-mcp subprocess...")

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

        try:
            # Try graceful termination first
            self.process.terminate()

            # Wait up to 5 seconds for graceful shutdown
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
                logger.info("playwright-mcp stopped gracefully")
            except asyncio.TimeoutError:
                # Force kill if it doesn't stop
                logger.warning("playwright-mcp didn't stop gracefully, forcing kill")
                self.process.kill()
                await self.process.wait()
                logger.info("playwright-mcp killed")

        except Exception as e:
            logger.error(f"Error stopping playwright-mcp: {e}")
        finally:
            self.process = None
            self._actual_port = None  # Reset port on stop

    async def restart(self, config: PlaywrightConfig) -> Process:
        """
        Restart the playwright-mcp subprocess.

        Args:
            config: Playwright configuration

        Returns:
            The new subprocess Process object
        """
        logger.info("Restarting playwright-mcp...")
        await self.stop()
        await asyncio.sleep(1.0)  # Brief pause before restart
        return await self.start(config)

    def get_port(self) -> int:
        """
        Get the actual port the server is listening on.

        Returns:
            The actual port number

        Raises:
            RuntimeError: If port hasn't been discovered yet
        """
        if self._actual_port is None:
            raise RuntimeError("Port not discovered yet - server may not have started")
        return self._actual_port

    async def is_healthy(self) -> bool:
        """
        Check if the playwright-mcp HTTP server is healthy.

        Returns:
            True if process is running AND HTTP endpoint is responsive
        """
        if self.process is None or self._actual_port is None:
            return False

        # First check if process is still running
        if self.process.returncode is not None:
            return False

        # Then check if HTTP endpoint is responsive
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{PLAYWRIGHT_HTTP_HOST}:{self._actual_port}/mcp",
                    timeout=aiohttp.ClientTimeout(total=2.0),
                ) as resp:
                    # Accept various status codes - just checking if server responds
                    return resp.status in (200, 400, 405, 500)
        except Exception:
            return False

    async def _wait_for_http_ready(self, timeout: float = 10.0) -> bool:
        """
        Wait for HTTP server to be ready by polling MCP endpoint.
        This method waits for port discovery first, then polls the endpoint.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if server became ready, False otherwise
        """
        import aiohttp

        start_time = asyncio.get_event_loop().time()

        # First wait for port discovery (with half the timeout)
        port_discovery_timeout = timeout / 2
        while (asyncio.get_event_loop().time() - start_time) < port_discovery_timeout:
            if self.process and self.process.returncode is not None:
                # Process crashed
                return False

            if self._actual_port is not None:
                logger.info(f"Port discovered: {self._actual_port}")
                break

            await asyncio.sleep(0.1)

        if self._actual_port is None:
            logger.error("Port not discovered within timeout")
            return False

        # Now poll the endpoint with the discovered port
        url = f"http://{PLAYWRIGHT_HTTP_HOST}:{self._actual_port}/mcp"
        logger.info(f"Polling HTTP endpoint: {url}")

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if self.process and self.process.returncode is not None:
                # Process crashed
                return False

            try:
                async with aiohttp.ClientSession() as session:
                    # Use GET request to check if endpoint exists
                    # MCP servers typically don't support HEAD on /mcp endpoint
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=1.0)
                    ) as resp:
                        # Accept any response (200, 400, 405, etc.) - just checking server is up
                        # The /mcp endpoint may return error for GET without proper request body
                        if resp.status in (200, 400, 405, 500):
                            return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                # Server not ready yet
                pass

            await asyncio.sleep(0.2)

        return False

    async def _log_stdout(self) -> None:
        """
        Background task to read and log stdout from subprocess.
        Uses UPSTREAM_MCP prefix to distinguish from proxy logs.
        """
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
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
        Also extracts the actual port from the "Listening on" message.
        """
        if not self.process or not self.process.stderr:
            return

        try:
            import re
            port_pattern = re.compile(r"Listening on http://[^:]+:(\d+)")

            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break

                # Decode and log stderr output
                stderr_line = line.decode("utf-8", errors="replace").rstrip()
                if stderr_line:
                    logger.warning(f"UPSTREAM_MCP [stderr] {stderr_line}")

                    # Extract port from "Listening on http://localhost:PORT" message
                    if self._actual_port is None:
                        match = port_pattern.search(stderr_line)
                        if match:
                            self._actual_port = int(match.group(1))
                            logger.info(f"Discovered actual port: {self._actual_port}")

        except asyncio.CancelledError:
            logger.debug("Stderr logger task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in stderr logger: {e}")

    async def _build_command(self, config: PlaywrightConfig, npx_path: str) -> list[str]:
        """
        Build the npx command with arguments from config.

        Args:
            config: Playwright configuration
            npx_path: Absolute path to npx executable

        Returns:
            List of command and arguments
        """
        # Use the explicit npx path to ensure we use the correct Node.js installation
        command = [npx_path, "@playwright/mcp@latest"]

        # HTTP transport configuration (REQUIRED for proxy to connect)
        command.extend(["--host", PLAYWRIGHT_HTTP_HOST])
        command.extend(["--port", str(PLAYWRIGHT_HTTP_PORT)])
        command.extend(["--allowed-hosts", "*"])  # Disable DNS rebinding check for localhost

        # Browser
        if "browser" in config:
            command.extend(["--browser", config["browser"]])

        # Headless
        if "headless" in config and config["headless"]:
            command.append("--headless")

        # No sandbox (required for running as root in Docker)
        if "no_sandbox" in config and config["no_sandbox"]:
            command.append("--no-sandbox")

        # Device emulation
        if "device" in config and config["device"]:
            command.extend(["--device", config["device"]])

        # Viewport size
        if "viewport_size" in config and config["viewport_size"]:
            command.extend(["--viewport-size", config["viewport_size"]])

        # Isolated mode
        if "isolated" in config and config["isolated"]:
            command.append("--isolated")

        # User data directory
        if "user_data_dir" in config and config["user_data_dir"]:
            command.extend(["--user-data-dir", config["user_data_dir"]])

        # Storage state
        if "storage_state" in config and config["storage_state"]:
            command.extend(["--storage-state", config["storage_state"]])

        # Network filtering
        if "allowed_origins" in config and config["allowed_origins"]:
            command.extend(["--allowed-origins", config["allowed_origins"]])

        if "blocked_origins" in config and config["blocked_origins"]:
            command.extend(["--blocked-origins", config["blocked_origins"]])

        # Proxy server
        if "proxy_server" in config and config["proxy_server"]:
            command.extend(["--proxy-server", config["proxy_server"]])

        # Capabilities
        if "caps" in config and config["caps"]:
            command.extend(["--caps", config["caps"]])

        # Save session
        if "save_session" in config and config["save_session"]:
            command.append("--save-session")

        # Save trace
        if "save_trace" in config and config["save_trace"]:
            command.append("--save-trace")

        # Save video
        if "save_video" in config and config["save_video"]:
            command.extend(["--save-video", config["save_video"]])

        # Output directory
        if "output_dir" in config:
            command.extend(["--output-dir", config["output_dir"]])

        # Timeouts
        if "timeout_action" in config:
            command.extend(["--timeout-action", str(config["timeout_action"])])

        if "timeout_navigation" in config:
            command.extend(["--timeout-navigation", str(config["timeout_navigation"])])

        # Image responses
        if "image_responses" in config:
            command.extend(["--image-responses", config["image_responses"]])

        # Stealth settings
        if "user_agent" in config and config["user_agent"]:
            command.extend(["--user-agent", config["user_agent"]])

        if "init_script" in config and config["init_script"]:
            command.extend(["--init-script", config["init_script"]])

        if "ignore_https_errors" in config and config["ignore_https_errors"]:
            command.append("--ignore-https-errors")

        # Extension support
        if "extension" in config and config["extension"]:
            command.append("--extension")

        return command
