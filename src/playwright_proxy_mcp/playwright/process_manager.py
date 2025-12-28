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
from .config import PlaywrightConfig

logger = get_logger(__name__)


class PlaywrightProcessManager:
    """Manages the playwright-mcp subprocess lifecycle"""

    def __init__(self) -> None:
        self.process: Process | None = None
        self._shutdown_event = asyncio.Event()

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

        # Check if npx is available
        npx_path = shutil.which("npx")
        if not npx_path:
            logger.error("npx not found in PATH")
            raise RuntimeError(
                "npx not found. Please ensure Node.js is installed and npx is in PATH."
            )
        logger.info(f"npx found at: {npx_path}")

        # Build command
        command = await self._build_command(config)

        logger.info("Playwright MCP command configuration:")
        logger.info(f"  Command: {' '.join(command)}")
        logger.info(f"  Working directory: {os.getcwd()}")

        # Log configuration (redacting sensitive values)
        logger.info("Playwright configuration:")
        log_dict(logger, "Configuration parameters:", dict(config))

        try:
            # Prepare environment variables for subprocess
            env = os.environ.copy()

            # Track custom env vars
            custom_env_vars = {}

            # Pass through extension token if configured
            if "extension_token" in config and config["extension_token"]:
                env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = config["extension_token"]
                custom_env_vars["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = "***REDACTED***"

            # Log environment variables (redact sensitive values)
            if custom_env_vars:
                logger.info("Custom environment variables:")
                for key, value in custom_env_vars.items():
                    logger.info(f"  {key}: {value}")
            else:
                logger.info("No custom environment variables set")

            logger.info("Launching playwright-mcp subprocess...")

            # Start subprocess with stdio pipes
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            logger.info(f"Process created with PID: {self.process.pid}")

            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Check if it's still running
            if self.process.returncode is not None:
                logger.error(f"Process exited immediately with code: {self.process.returncode}")

                # Collect stderr and stdout
                stderr_data = await self.process.stderr.read() if self.process.stderr else b""
                stdout_data = await self.process.stdout.read() if self.process.stdout else b""

                stderr_msg = stderr_data.decode("utf-8", errors="ignore").strip()
                stdout_msg = stdout_data.decode("utf-8", errors="ignore").strip()

                logger.error("Process output:")
                if stdout_msg:
                    logger.error(f"  STDOUT:\n{stdout_msg}")
                else:
                    logger.error("  STDOUT: (empty)")

                if stderr_msg:
                    logger.error(f"  STDERR:\n{stderr_msg}")
                else:
                    logger.error("  STDERR: (empty)")

                error_detail = stderr_msg or stdout_msg or "No output captured"
                raise RuntimeError(
                    f"playwright-mcp failed to start (exit code {self.process.returncode}): {error_detail}"
                )

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

    def is_healthy(self) -> bool:
        """
        Check if the playwright-mcp process is healthy.

        Returns:
            True if process is running, False otherwise
        """
        if self.process is None:
            return False

        # Check if process is still running
        return self.process.returncode is None

    async def _build_command(self, config: PlaywrightConfig) -> list[str]:
        """
        Build the npx command with arguments from config.

        Args:
            config: Playwright configuration

        Returns:
            List of command and arguments
        """
        # Use npx to run @playwright/mcp
        # npx will use the globally installed version since we installed it with npm install -g
        command = ["npx", "@playwright/mcp"]

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

    async def get_stderr_output(self) -> str:
        """
        Get any stderr output from the process (non-blocking).

        Returns:
            Stderr output as string
        """
        if self.process is None or self.process.stderr is None:
            return ""

        try:
            # Try to read available data without blocking
            data = b""
            while True:
                try:
                    chunk = self.process.stderr.read(1024)
                    if asyncio.iscoroutine(chunk):
                        chunk = await asyncio.wait_for(chunk, timeout=0.1)
                    if not chunk:
                        break
                    data += chunk
                except asyncio.TimeoutError:
                    break

            return data.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Error reading stderr: {e}")
            return ""
