"""
Tests for playwright process manager
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from playwright_proxy_mcp.playwright.process_manager import PlaywrightProcessManager


@pytest.fixture
def process_manager():
    """Create a process manager instance."""
    return PlaywrightProcessManager()


@pytest.fixture
def mock_subprocess():
    """Create a mock subprocess with stdout/stderr streams."""
    mock_process = Mock()
    mock_process.pid = 12345
    mock_process.returncode = None

    # Mock stdout stream
    mock_stdout = Mock()
    mock_stdout.readline = AsyncMock(return_value=b"")
    mock_process.stdout = mock_stdout

    # Mock stderr stream
    mock_stderr = Mock()
    mock_stderr.readline = AsyncMock(return_value=b"")
    mock_process.stderr = mock_stderr

    return mock_process


class TestPlaywrightProcessManager:
    """Tests for PlaywrightProcessManager."""

    def test_init(self, process_manager):
        """Test process manager initialization."""
        assert process_manager.process is None
        assert not process_manager._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_is_healthy_no_process(self, process_manager):
        """Test is_healthy returns False when no process."""
        assert await process_manager.is_healthy() is False

    @pytest.mark.asyncio
    async def test_is_healthy_process_running(self, process_manager, mock_subprocess):
        """Test is_healthy returns True when process is running."""
        await process_manager.set_process(mock_subprocess)
        assert await process_manager.is_healthy() is True

    @pytest.mark.asyncio
    async def test_is_healthy_process_exited(self, process_manager, mock_subprocess):
        """Test is_healthy returns False when process has exited."""
        mock_subprocess.returncode = 0
        await process_manager.set_process(mock_subprocess)
        assert await process_manager.is_healthy() is False

    @pytest.mark.asyncio
    async def test_set_process(self, process_manager, mock_subprocess):
        """Test set_process starts logging tasks."""
        await process_manager.set_process(mock_subprocess)

        assert process_manager.process == mock_subprocess
        assert hasattr(process_manager, "_stdout_task")
        assert hasattr(process_manager, "_stderr_task")

        # Clean up tasks
        process_manager._stdout_task.cancel()
        process_manager._stderr_task.cancel()
        try:
            await process_manager._stdout_task
        except asyncio.CancelledError:
            pass
        try:
            await process_manager._stderr_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop(self, process_manager, mock_subprocess):
        """Test stop cancels logging tasks."""
        await process_manager.set_process(mock_subprocess)

        # Stop should cancel tasks
        await process_manager.stop()

        assert process_manager.process is None

    @pytest.mark.asyncio
    async def test_stop_no_process(self, process_manager):
        """Test stop when no process is set."""
        # Should not raise
        await process_manager.stop()
        assert process_manager.process is None
