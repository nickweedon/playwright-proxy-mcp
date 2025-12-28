# Logging Improvements

This document describes the logging improvements made to the playwright-proxy-mcp codebase.

## Overview

The logging configuration has been extracted into a reusable utility module, and comprehensive logging has been added around the Playwright MCP server configuration and launch process.

## Changes Made

### 1. New Logging Configuration Module

**File**: [src/playwright_proxy_mcp/utils/logging_config.py](../src/playwright_proxy_mcp/utils/logging_config.py)

A new centralized logging configuration module provides:

- `setup_file_logging()`: Configure file-only logging (prevents MCP protocol corruption)
- `get_logger()`: Get a logger instance for a specific module
- `log_dict()`: Log dictionaries with automatic sensitive data redaction

**Key Features**:
- File-only logging (no stdout/stderr to avoid MCP protocol corruption)
- Automatic redaction of sensitive values (tokens, passwords, secrets, keys)
- Configurable log levels and formats
- Creates log directories automatically

**Example Usage**:
```python
from playwright_proxy_mcp.utils.logging_config import setup_file_logging, get_logger, log_dict

# Setup logging at application startup
setup_file_logging(log_file="logs/app.log")

# Get logger for your module
logger = get_logger(__name__)

# Log messages
logger.info("Application started")

# Log configuration with automatic redaction
config = {"browser": "chromium", "api_token": "secret123"}
log_dict(logger, "Configuration:", config)
# Output:
#   Configuration:
#     browser: chromium
#     api_token: ***REDACTED***
```

### 2. Enhanced Process Manager Logging

**File**: [src/playwright_proxy_mcp/playwright/process_manager.py](../src/playwright_proxy_mcp/playwright/process_manager.py)

The `PlaywrightProcessManager.start()` method now includes comprehensive logging:

#### Startup Logging:
- npx binary location
- Full command line with all arguments
- Working directory
- Configuration parameters (with sensitive data redacted)
- Custom environment variables (with sensitive data redacted)
- Process PID
- Launch status

#### Error Logging:
When the process fails to start, the following is captured and logged:
- Exit code
- Complete stdout output
- Complete stderr output
- Error context and cleanup attempts

**Example Log Output**:
```
2025-12-28 09:33:10,109 - process_manager - INFO - ================================================================================
2025-12-28 09:33:10,109 - process_manager - INFO - Configuring playwright-mcp subprocess
2025-12-28 09:33:10,109 - process_manager - INFO - ================================================================================
2025-12-28 09:33:10,141 - process_manager - INFO - npx found at: /mnt/c/nvm4w/nodejs/npx
2025-12-28 09:33:10,141 - process_manager - INFO - Playwright MCP command configuration:
2025-12-28 09:33:10,141 - process_manager - INFO -   Command: npx @playwright/mcp --browser chromium --headless --no-sandbox
2025-12-28 09:33:10,141 - process_manager - INFO -   Working directory: /opt/src/mcp/playwright-proxy-mcp
2025-12-28 09:33:10,141 - process_manager - INFO - Playwright configuration:
2025-12-28 09:33:10,141 - process_manager - INFO - Configuration parameters:
2025-12-28 09:33:10,141 - process_manager - INFO -   browser: chromium
2025-12-28 09:33:10,141 - process_manager - INFO -   headless: True
2025-12-28 09:33:10,141 - process_manager - INFO -   no_sandbox: True
2025-12-28 09:33:10,141 - process_manager - INFO - No custom environment variables set
2025-12-28 09:33:10,141 - process_manager - INFO - Launching playwright-mcp subprocess...
2025-12-28 09:33:10,215 - process_manager - INFO - Process created with PID: 1137607
2025-12-28 09:33:10,716 - process_manager - INFO - playwright-mcp started successfully (PID: 1137607)
2025-12-28 09:33:10,716 - process_manager - INFO - ================================================================================
```

**Error Log Example**:
```
2025-12-28 09:33:10,101 - process_manager - ERROR - Process exited immediately with code: 1
2025-12-28 09:33:10,110 - process_manager - ERROR - Process output:
2025-12-28 09:33:10,110 - process_manager - ERROR -   STDOUT: (empty)
2025-12-28 09:33:10,110 - process_manager - ERROR -   STDERR:
Error: Browser executable not found at /path/to/browser
2025-12-28 09:33:10,131 - process_manager - ERROR - ================================================================================
2025-12-28 09:33:10,132 - process_manager - ERROR - Failed to start playwright-mcp: playwright-mcp failed to start (exit code 1): Error: Browser executable not found
2025-12-28 09:33:10,133 - process_manager - ERROR - ================================================================================
```

### 3. Updated Server Module

**File**: [src/playwright_proxy_mcp/server.py](../src/playwright_proxy_mcp/server.py)

- Replaced inline logging configuration with centralized utility
- Removed duplicate logging setup code
- Uses `get_logger(__name__)` pattern

### 4. Updated Utils Package

**File**: [src/playwright_proxy_mcp/utils/__init__.py](../src/playwright_proxy_mcp/utils/__init__.py)

Exports logging utilities for easy importing:
```python
from playwright_proxy_mcp.utils import get_logger, log_dict, setup_file_logging
```

## Benefits

1. **Reusable Configuration**: Logging setup can be used across the codebase
2. **Security**: Automatic redaction of sensitive values in logs
3. **Debugging**: Comprehensive process startup logging helps diagnose issues
4. **Error Diagnosis**: Full stdout/stderr/exit code capture on failures
5. **Consistency**: Centralized configuration ensures uniform logging behavior
6. **MCP Protocol Safety**: File-only logging prevents stdout corruption

## Migration Guide

To use the new logging utilities in other parts of the codebase:

```python
# Old way
import logging
logger = logging.getLogger(__name__)

# New way
from playwright_proxy_mcp.utils.logging_config import get_logger
logger = get_logger(__name__)

# For logging dictionaries with redaction
from playwright_proxy_mcp.utils.logging_config import log_dict
log_dict(logger, "Config:", my_config_dict)
```

## Testing

All existing tests pass with the new logging infrastructure. The test suite was updated to properly mock the new logging behavior in [tests/test_process_manager.py](../tests/test_process_manager.py).

To verify logging works:
```bash
# Run tests
uv run pytest tests/test_server.py tests/test_process_manager.py -v

# Check log output
tail -f logs/playwright-proxy-mcp.log
```

## Future Enhancements

Potential improvements for the logging system:

1. **Log Rotation**: Implement automatic log rotation by size or date
2. **Log Levels**: Add environment variable to control log level
3. **Structured Logging**: Consider JSON-formatted logs for machine parsing
4. **Performance Monitoring**: Add timing information to critical operations
5. **Log Aggregation**: Integration with external logging services
