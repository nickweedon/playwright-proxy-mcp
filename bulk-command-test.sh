#!/bin/bash
# Debug script for browser_execute_bulk command in Docker
# Tests the failing Amazon search with bulk commands

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

IMAGE_NAME="playwright-proxy-mcp:latest"
ENV_FILE="container-test.env"

# Check prerequisites
log_info "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    log_error "docker not found"
    exit 1
fi
if ! command -v mcptools &> /dev/null; then
    log_error "mcptools not found"
    exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file $ENV_FILE not found"
    exit 1
fi
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    log_error "Docker image $IMAGE_NAME not found. Build it first."
    exit 1
fi
log_success "Prerequisites OK"
echo

# Test 1: Simple bulk command (known good URL)
log_info "Test 1: Simple bulk command with example.com..."
SIMPLE_BULK_CMD='{"commands": [{"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}}, {"tool": "browser_snapshot", "args": {"flatten": true, "limit": 50, "output_format": "json"}, "return_result": true}], "stop_on_error": true, "return_all_results": false}'

echo "Command: $SIMPLE_BULK_CMD" | head -c 200
echo "..."
echo

if ! output=$(mcptools call browser_execute_bulk --params "$SIMPLE_BULK_CMD" docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1); then
    log_error "Failed to execute simple bulk command"
    echo "$output"
    exit 1
fi

if echo "$output" | grep -q '"success"'; then
    log_success "Simple bulk command returned valid response"
    echo "Output preview:"
    echo "$output" | jq -r '.content[0].text' 2>/dev/null | head -c 500 || echo "$output" | head -c 500
    echo
else
    log_error "Invalid response from simple bulk command"
    echo "$output"
    exit 1
fi
echo

# Test 2: Amazon bulk command (the failing one)
log_info "Test 2: Amazon bulk command with wait..."
AMAZON_BULK_CMD='{"commands": [{"tool": "browser_navigate", "args": {"url": "https://www.amazon.com/s?k=gloves", "silent_mode": true}}, {"tool": "browser_wait_for", "args": {"time": 3}}, {"tool": "browser_snapshot", "args": {"flatten": true, "limit": 200, "output_format": "json"}, "return_result": true}], "stop_on_error": true, "return_all_results": false}'

echo "Command: $AMAZON_BULK_CMD" | head -c 200
echo "..."
echo

if ! output=$(mcptools call browser_execute_bulk --params "$AMAZON_BULK_CMD" docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1); then
    log_error "Failed to execute Amazon bulk command"
    echo "Full error output:"
    echo "$output"
    echo

    # Check for specific error patterns
    if echo "$output" | grep -qi "timeout"; then
        log_warn "Detected timeout error"
    fi
    if echo "$output" | grep -qi "connection"; then
        log_warn "Detected connection error"
    fi
    if echo "$output" | grep -qi "browser"; then
        log_warn "Detected browser error"
    fi
    exit 1
fi

if echo "$output" | grep -q '"success"'; then
    log_success "Amazon bulk command returned valid response"

    # Extract and analyze response
    response=$(echo "$output" | jq -r '.content[0].text' 2>/dev/null || echo "$output")

    # Check for success field in the actual response
    if echo "$response" | grep -q '"success":true'; then
        log_success "Amazon navigation and snapshot succeeded!"
        echo "Response structure:"
        echo "$response" | jq -r '{success, executed_count, total_count, has_errors: (.errors | map(select(. != null)) | length > 0)}' 2>/dev/null || echo "$response" | head -c 500
    else
        log_warn "Command executed but reported failure"
        echo "Response preview:"
        echo "$response" | jq -r '{success, executed_count, total_count, errors}' 2>/dev/null || echo "$response" | head -c 1000
    fi
else
    log_error "Invalid response from Amazon bulk command"
    echo "$output"
    exit 1
fi
echo

# Test 3: Individual commands (debug approach)
log_info "Test 3: Testing individual commands separately..."

log_info "  3a: browser_navigate to Amazon..."
if ! nav_output=$(mcptools call browser_navigate --params '{"url": "https://www.amazon.com/s?k=gloves", "silent_mode": true}' docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1); then
    log_error "Failed browser_navigate"
    echo "$nav_output"
else
    if echo "$nav_output" | grep -q '"success":true'; then
        log_success "Navigation succeeded"
    else
        log_warn "Navigation failed or timed out"
        echo "$nav_output" | head -c 500
    fi
fi
echo

log_info "  3b: browser_wait_for..."
if ! wait_output=$(mcptools call browser_wait_for --params '{"time": 3}' docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1); then
    log_error "Failed browser_wait_for"
    echo "$wait_output"
else
    log_success "Wait succeeded"
fi
echo

log_info "  3c: browser_snapshot with flatten..."
if ! snap_output=$(mcptools call browser_snapshot --params '{"flatten": true, "limit": 200, "output_format": "json"}' docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1); then
    log_error "Failed browser_snapshot"
    echo "$snap_output"
else
    if echo "$snap_output" | grep -q '"success"'; then
        log_success "Snapshot succeeded"
        echo "$snap_output" | jq -r '.content[0].text' 2>/dev/null | jq -r '{success, total_items, has_more}' 2>/dev/null || echo "Response OK"
    else
        log_warn "Snapshot returned unexpected format"
        echo "$snap_output" | head -c 500
    fi
fi
echo

log_success "=== Debug Tests Complete ==="
log_info "Check output above for specific failure points"
