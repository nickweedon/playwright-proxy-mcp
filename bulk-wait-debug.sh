#!/bin/bash
# Minimal debug script for browser_wait_for hanging issue
# Tests if browser_wait_for hangs in Docker when called after browser_navigate

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

IMAGE_NAME="playwright-proxy-mcp:latest"
ENV_FILE="container-test.env"

# Check prerequisites
if ! command -v mcptools &> /dev/null; then
    log_error "mcptools not found"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file $ENV_FILE not found"
    exit 1
fi

log_info "Testing browser_wait_for hang issue..."
echo

# Test 1: browser_wait_for standalone (should work)
log_info "Test 1: browser_wait_for standalone (time=3 seconds)"
timeout 15s mcptools call browser_wait_for --params '{"time": 3}' \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 || {
    log_error "browser_wait_for standalone FAILED or HUNG"
    exit 1
}
log_success "browser_wait_for standalone completed"
echo

# Test 2: browser_navigate then browser_wait_for separately (may hang on wait_for)
log_info "Test 2: browser_navigate then browser_wait_for (separate calls)"

# Navigate
log_info "  2a: Navigating to example.com..."
timeout 30s mcptools call browser_navigate --params '{"url": "https://example.com", "silent_mode": true}' \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 > /dev/null || {
    log_error "Navigation failed or timed out"
    exit 1
}
log_success "Navigation completed"

# Wait (THIS MAY HANG)
log_info "  2b: Calling browser_wait_for (time=3)..."
timeout 15s mcptools call browser_wait_for --params '{"time": 3}' \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 || {
    log_error "browser_wait_for HUNG after navigation! This confirms the bug."
    echo
    echo "KEY FINDING:"
    echo "  - browser_wait_for works standalone"
    echo "  - browser_wait_for HANGS after browser_navigate in separate container"
    echo "  - This is because each docker run creates a NEW container with NO browser state!"
    echo
    echo "SOLUTION:"
    echo "  - Use browser_execute_bulk to keep commands in same container/session"
    echo "  - OR use a persistent container (docker run with --name and docker exec)"
    exit 1
}
log_success "browser_wait_for completed (unexpected!)"
echo

# Test 3: browser_execute_bulk (should work)
log_info "Test 3: browser_execute_bulk with navigate + wait_for"
BULK_CMD='{"commands": [{"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}}, {"tool": "browser_wait_for", "args": {"time": 3}}, {"tool": "browser_snapshot", "args": {"limit": 10, "output_format": "json"}, "return_result": true}], "stop_on_error": true}'

timeout 60s mcptools call browser_execute_bulk --params "$BULK_CMD" \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 | tee /tmp/bulk_output.txt || {
    log_error "browser_execute_bulk FAILED or HUNG"
    echo
    echo "Output so far:"
    tail -50 /tmp/bulk_output.txt
    exit 1
}
log_success "browser_execute_bulk completed!"

# Check if it actually succeeded
if grep -q '"success":true' /tmp/bulk_output.txt; then
    log_success "All commands executed successfully"
else
    log_error "Commands executed but reported failure"
    cat /tmp/bulk_output.txt | jq -r '.content[0].text' | head -c 500
fi

echo
log_success "=== Debug Complete ==="
log_info "If Test 2 failed and Test 3 succeeded, the issue is container state isolation"
