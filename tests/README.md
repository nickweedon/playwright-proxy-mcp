# Test Suite Documentation

This directory contains the test suite for the Playwright MCP Proxy server.

## Test Categories

### Unit Tests
Most tests in this directory are unit tests that use mocked responses. They test:
- Individual component functionality
- Tool parameter handling
- Response transformation
- Error handling

Run unit tests:
```bash
uv run pytest -v
```

### Integration Tests
Integration tests are marked with `@pytest.mark.integration` and require:
- A running Playwright browser instance
- Internet connectivity (tests against real websites)
- More time to execute

Run integration tests:
```bash
# Run all integration tests
uv run pytest -m integration -v

# Run integration tests against a specific module
uv run pytest tests/test_browser_integration.py -v

# Skip integration tests (run only unit tests)
uv run pytest -m "not integration" -v
```

### Slow Tests
Some tests are marked as slow (`@pytest.mark.slow`). These typically:
- Make network requests
- Test against real websites
- May take several seconds to complete

Run excluding slow tests:
```bash
uv run pytest -m "not slow" -v
```

## Test Files

- `test_browser_integration.py` - Real browser tests against actual websites
- `test_tool_integration.py` - Tool method integration tests with mocked responses
- `test_integration.py` - General integration workflow tests
- `test_server.py` - Server initialization and configuration tests
- `test_proxy_client.py` - Proxy client tests
- `test_middleware.py` - Binary interception middleware tests
- `test_blob_manager.py` - Blob storage tests
- `test_process_manager.py` - Process lifecycle management tests
- Other test files cover specific components

## Running Specific Tests

Run a specific test file:
```bash
uv run pytest tests/test_browser_integration.py -v
```

Run a specific test function:
```bash
uv run pytest tests/test_browser_integration.py::test_browser_navigate_real_website -v
```

Run tests matching a pattern:
```bash
uv run pytest -k "navigate" -v
```

## Integration Test Requirements

The integration tests in `test_browser_integration.py` require:

1. **Running Server**: The Playwright proxy server must be running with a browser instance
2. **Network Access**: Tests navigate to real websites (e.g., lcsc.com)
3. **Import Dependencies**: All required packages must be installed, including `aria-snapshot-parser`

To run integration tests locally:

```bash
# Start the server in one terminal
uv run playwright-proxy-mcp

# Run integration tests in another terminal
uv run pytest -m integration -v
```

## Known Issues and Fixes

### AriaSnapshotParser Import Error

If you encounter:
```
Error calling tool 'browser_navigate': cannot import name 'AriaSnapshotParser' from 'aria_snapshot_parser'
```

This means the `aria-snapshot-parser` package is not properly installed. The fix:

1. The package is defined as a local path dependency in `pyproject.toml`:
   ```toml
   [tool.uv.sources]
   aria-snapshot-parser = { path = "src/aria_snapshot_parser", editable = true }
   ```

2. Run `uv sync` to ensure it's installed:
   ```bash
   uv sync
   ```

3. For Docker builds, the Dockerfile installs it before the main package:
   ```dockerfile
   RUN if [ -d "/workspace/src/aria_snapshot_parser" ]; then \
           cd /workspace/src/aria_snapshot_parser && uv pip install --system .; \
       fi
   ```

## Test Markers

The test suite uses pytest markers to categorize tests:

- `@pytest.mark.integration` - Tests requiring running browser
- `@pytest.mark.slow` - Tests that may take longer to execute
- `@pytest.mark.asyncio` - Async tests (automatically handled)

View all markers:
```bash
uv run pytest --markers
```

## Writing New Tests

### Unit Tests
Use mocks for external dependencies:

```python
from unittest.mock import Mock, patch
import pytest

@pytest.mark.asyncio
async def test_my_feature(mock_proxy_client):
    mock_proxy_client.call_tool.return_value = {"result": "success"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.my_tool.fn(param="value")
        assert result["result"] == "success"
```

### Integration Tests
Mark with appropriate decorators and include skip conditions:

```python
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_real_browser_interaction():
    if not server.proxy_client or not server.proxy_client.is_healthy():
        pytest.skip("Proxy client not started - this test requires a running browser")

    result = await server.browser_navigate.fn(url="https://example.com")
    assert result["success"] is True
```

## Continuous Integration

For CI/CD pipelines:

```bash
# Run only fast unit tests
uv run pytest -m "not slow and not integration" -v

# Run all tests (if browser is available)
uv run pytest -v
```

## Coverage

Generate coverage report:

```bash
uv run pytest --cov=playwright_proxy_mcp --cov-report=html --cov-report=term
```

View HTML coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```
