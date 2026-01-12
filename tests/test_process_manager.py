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

    @pytest.mark.asyncio
    async def test_log_stdout_reads_lines(self, process_manager, caplog):
        """Test that _log_stdout reads and logs stdout lines."""
        import logging

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = None

        # Return lines then empty
        lines = [b"Line 1\n", b"Line 2\n", b""]
        line_iter = iter(lines)

        mock_stdout = Mock()
        mock_stdout.readline = AsyncMock(side_effect=lambda: next(line_iter))
        mock_process.stdout = mock_stdout

        mock_stderr = Mock()
        mock_stderr.readline = AsyncMock(return_value=b"")
        mock_process.stderr = mock_stderr

        process_manager.process = mock_process

        with caplog.at_level(logging.INFO):
            await process_manager._log_stdout()

        assert "UPSTREAM_MCP [stdout] Line 1" in caplog.text
        assert "UPSTREAM_MCP [stdout] Line 2" in caplog.text

    @pytest.mark.asyncio
    async def test_log_stderr_reads_lines(self, process_manager, caplog):
        """Test that _log_stderr reads and logs stderr lines."""
        import logging

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = None

        mock_stdout = Mock()
        mock_stdout.readline = AsyncMock(return_value=b"")
        mock_process.stdout = mock_stdout

        # Return lines then empty
        lines = [b"Error 1\n", b"Error 2\n", b""]
        line_iter = iter(lines)

        mock_stderr = Mock()
        mock_stderr.readline = AsyncMock(side_effect=lambda: next(line_iter))
        mock_process.stderr = mock_stderr

        process_manager.process = mock_process

        with caplog.at_level(logging.WARNING):
            await process_manager._log_stderr()

        assert "UPSTREAM_MCP [stderr] Error 1" in caplog.text
        assert "UPSTREAM_MCP [stderr] Error 2" in caplog.text

    @pytest.mark.asyncio
    async def test_log_stdout_no_stdout(self, process_manager, caplog):
        """Test _log_stdout when process has no stdout."""
        import logging

        process_manager.process = None

        with caplog.at_level(logging.ERROR):
            await process_manager._log_stdout()

        assert "No stdout to log from subprocess" in caplog.text

    @pytest.mark.asyncio
    async def test_log_stderr_no_stderr(self, process_manager, caplog):
        """Test _log_stderr when process has no stderr."""
        import logging

        process_manager.process = None

        with caplog.at_level(logging.ERROR):
            await process_manager._log_stderr()

        assert "No stderr to log from subprocess" in caplog.text

    @pytest.mark.asyncio
    async def test_log_stdout_handles_exception(self, process_manager, caplog):
        """Test _log_stdout handles exceptions gracefully."""
        import logging

        mock_process = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline = AsyncMock(side_effect=RuntimeError("Read error"))

        process_manager.process = mock_process

        with caplog.at_level(logging.ERROR):
            await process_manager._log_stdout()

        assert "Error in stdout logger" in caplog.text

    @pytest.mark.asyncio
    async def test_log_stderr_handles_exception(self, process_manager, caplog):
        """Test _log_stderr handles exceptions gracefully."""
        import logging

        mock_process = Mock()
        mock_process.stderr = Mock()
        mock_process.stderr.readline = AsyncMock(side_effect=RuntimeError("Read error"))

        process_manager.process = mock_process

        with caplog.at_level(logging.ERROR):
            await process_manager._log_stderr()

        assert "Error in stderr logger" in caplog.text

    @pytest.mark.asyncio
    async def test_log_stdout_cancelled(self, process_manager):
        """Test _log_stdout re-raises CancelledError."""
        import logging

        mock_process = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline = AsyncMock(side_effect=asyncio.CancelledError())

        process_manager.process = mock_process

        with pytest.raises(asyncio.CancelledError):
            await process_manager._log_stdout()

    @pytest.mark.asyncio
    async def test_log_stderr_cancelled(self, process_manager):
        """Test _log_stderr re-raises CancelledError."""
        import logging

        mock_process = Mock()
        mock_process.stderr = Mock()
        mock_process.stderr.readline = AsyncMock(side_effect=asyncio.CancelledError())

        process_manager.process = mock_process

        with pytest.raises(asyncio.CancelledError):
            await process_manager._log_stderr()

    @pytest.mark.asyncio
    async def test_log_stdout_empty_line_ignored(self, process_manager, caplog):
        """Test that empty lines are not logged."""
        import logging

        mock_process = Mock()
        mock_process.pid = 12345

        # Return empty line (whitespace only) then done
        lines = [b"   \n", b""]
        line_iter = iter(lines)

        mock_stdout = Mock()
        mock_stdout.readline = AsyncMock(side_effect=lambda: next(line_iter))
        mock_process.stdout = mock_stdout

        process_manager.process = mock_process

        with caplog.at_level(logging.INFO):
            await process_manager._log_stdout()

        # Empty lines should not be logged
        assert "UPSTREAM_MCP [stdout]    " not in caplog.text

    @pytest.mark.asyncio
    async def test_log_stderr_empty_line_ignored(self, process_manager, caplog):
        """Test that empty stderr lines are not logged."""
        import logging

        mock_process = Mock()
        mock_process.pid = 12345

        # Return empty line (whitespace only) then done
        lines = [b"   \n", b""]
        line_iter = iter(lines)

        mock_stderr = Mock()
        mock_stderr.readline = AsyncMock(side_effect=lambda: next(line_iter))
        mock_process.stderr = mock_stderr

        process_manager.process = mock_process

        with caplog.at_level(logging.WARNING):
            await process_manager._log_stderr()

        # Empty lines should not be logged
        assert "UPSTREAM_MCP [stderr]    " not in caplog.text

    @pytest.mark.asyncio
    async def test_set_process_logs_pid(self, process_manager, mock_subprocess, caplog):
        """Test that set_process logs the PID."""
        import logging

        with caplog.at_level(logging.INFO):
            await process_manager.set_process(mock_subprocess)

        assert "Process monitoring started (PID: 12345)" in caplog.text

        # Clean up
        await process_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_logs_messages(self, process_manager, mock_subprocess, caplog):
        """Test that stop logs appropriate messages."""
        import logging

        await process_manager.set_process(mock_subprocess)

        with caplog.at_level(logging.INFO):
            await process_manager.stop()

        assert "Stopping process monitoring" in caplog.text
        assert "Process monitoring stopped" in caplog.text

    @pytest.mark.asyncio
    async def test_stop_cleans_up_tasks_without_attributes(self, process_manager, mock_subprocess):
        """Test stop handles case where tasks don't exist."""
        await process_manager.set_process(mock_subprocess)

        # Remove the task attributes
        delattr(process_manager, "_stdout_task")
        delattr(process_manager, "_stderr_task")

        # Should not raise
        await process_manager.stop()
        assert process_manager.process is None

    @pytest.mark.asyncio
    async def test_is_healthy_with_running_process(self, process_manager, mock_subprocess):
        """Test is_healthy returns True for process with None returncode."""
        mock_subprocess.returncode = None
        await process_manager.set_process(mock_subprocess)

        result = await process_manager.is_healthy()
        assert result is True

        # Clean up
        await process_manager.stop()

    @pytest.mark.asyncio
    async def test_is_healthy_with_exited_process_nonzero(self, process_manager, mock_subprocess):
        """Test is_healthy returns False for process with non-zero returncode."""
        mock_subprocess.returncode = 1
        await process_manager.set_process(mock_subprocess)

        result = await process_manager.is_healthy()
        assert result is False

        # Clean up
        await process_manager.stop()

    @pytest.mark.asyncio
    async def test_set_process_starts_monitoring_tasks(self, process_manager, mock_subprocess):
        """Test set_process starts both stdout and stderr monitoring tasks."""
        await process_manager.set_process(mock_subprocess)

        # Both tasks should exist and be running
        assert hasattr(process_manager, "_stdout_task")
        assert hasattr(process_manager, "_stderr_task")
        assert not process_manager._stdout_task.done()
        assert not process_manager._stderr_task.done()

        # Clean up
        await process_manager.stop()

    @pytest.mark.asyncio
    async def test_shutdown_event_exists(self, process_manager, mock_subprocess):
        """Test that shutdown event is created."""
        await process_manager.set_process(mock_subprocess)

        # Shutdown event should exist
        assert hasattr(process_manager, "_shutdown_event")
        assert process_manager._shutdown_event is not None

        # Clean up
        await process_manager.stop()

    @pytest.mark.asyncio
    async def test_multiple_stop_calls(self, process_manager, mock_subprocess):
        """Test that multiple stop calls are safe."""
        await process_manager.set_process(mock_subprocess)

        # First stop
        await process_manager.stop()
        assert process_manager.process is None

        # Second stop should be safe
        await process_manager.stop()
        assert process_manager.process is None

    @pytest.mark.asyncio
    async def test_stop_with_task_already_done(self, process_manager, mock_subprocess):
        """Test stop handles tasks that have already completed."""
        await process_manager.set_process(mock_subprocess)

        # Cancel tasks manually to simulate them being done
        process_manager._stdout_task.cancel()
        process_manager._stderr_task.cancel()

        # Wait for cancellation
        try:
            await process_manager._stdout_task
        except asyncio.CancelledError:
            pass
        try:
            await process_manager._stderr_task
        except asyncio.CancelledError:
            pass

        # Stop should still work
        await process_manager.stop()
        assert process_manager.process is None
