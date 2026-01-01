#!/bin/bash
# Test script to confirm the 5-second ping timeout hypothesis
# Tests browser_wait_for with different durations to find the threshold

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_test() { echo -e "${CYAN}[TEST]${NC} $1"; }

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

echo "========================================================================"
echo "  PING TIMEOUT HYPOTHESIS TEST"
echo "========================================================================"
echo
log_info "Testing browser_wait_for with different durations"
log_info "Hypothesis: Wait times >= 5 seconds will fail due to MCP ping timeout"
log_info "Expected: 2s and 4s should work, 6s and 8s should fail/hang"
echo

# Test function
run_wait_test() {
    local wait_time=$1
    local iteration=$2
    local test_name="wait_${wait_time}s_iter${iteration}"

    log_test "Running: browser_wait_for with time=${wait_time}s (iteration $iteration)"

    # Create the bulk command
    local cmd="{\"commands\": [{\"tool\": \"browser_navigate\", \"args\": {\"url\": \"https://example.com\", \"silent_mode\": true}}, {\"tool\": \"browser_wait_for\", \"args\": {\"time\": ${wait_time}}}, {\"tool\": \"browser_snapshot\", \"args\": {\"limit\": 5, \"output_format\": \"json\"}, \"return_result\": true}], \"stop_on_error\": true}"

    # Run with timeout (wait_time + 20 second buffer)
    local timeout_duration=$((wait_time + 20))
    local start_time=$(date +%s)

    if timeout ${timeout_duration}s mcptools call browser_execute_bulk --params "$cmd" \
        docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp \
        > "/tmp/${test_name}.txt" 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))

        if grep -q '"success":true' "/tmp/${test_name}.txt"; then
            log_success "PASSED (${duration}s total) - wait_for ${wait_time}s completed successfully"
            echo "  ✓ Result: success=true"
            return 0
        else
            log_error "FAILED (${duration}s total) - command executed but reported error"
            echo "  Response preview:"
            cat "/tmp/${test_name}.txt" | jq -r '.content[0].text' 2>/dev/null | head -c 300 || cat "/tmp/${test_name}.txt" | head -c 300
            echo
            return 1
        fi
    else
        local exit_code=$?
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))

        if [ $exit_code -eq 124 ]; then
            log_error "TIMEOUT (${duration}s) - Command exceeded ${timeout_duration}s timeout"
            echo "  ✗ This suggests the operation hung or took too long"
            return 2
        else
            log_error "FAILED (${duration}s) - Command failed with exit code $exit_code"
            cat "/tmp/${test_name}.txt" | head -c 300
            echo
            return 1
        fi
    fi
}

# Track results
declare -A results
ITERATIONS=2

echo "========================================================================"
echo "  TEST BATTERY: Multiple Iterations"
echo "========================================================================"
echo

# Test 1: 2 seconds (well under threshold) - 2 iterations
log_info "Test Group 1: browser_wait_for with 2 seconds (expected: SUCCESS)"
echo "---"
for i in $(seq 1 $ITERATIONS); do
    if run_wait_test 2 $i; then
        results["2s_iter${i}"]="PASS"
    else
        results["2s_iter${i}"]="FAIL"
    fi
    echo
    sleep 2  # Brief pause between tests
done

# Test 2: 4 seconds (just under threshold) - 2 iterations
log_info "Test Group 2: browser_wait_for with 4 seconds (expected: SUCCESS)"
echo "---"
for i in $(seq 1 $ITERATIONS); do
    if run_wait_test 4 $i; then
        results["4s_iter${i}"]="PASS"
    else
        results["4s_iter${i}"]="FAIL"
    fi
    echo
    sleep 2
done

# Test 3: 6 seconds (above threshold) - 2 iterations
log_info "Test Group 3: browser_wait_for with 6 seconds (expected: FAIL/HANG)"
echo "---"
for i in $(seq 1 $ITERATIONS); do
    if run_wait_test 6 $i; then
        results["6s_iter${i}"]="PASS"
    else
        results["6s_iter${i}"]="FAIL"
    fi
    echo
    sleep 2
done

# Test 4: 8 seconds (well above threshold) - 2 iterations
log_info "Test Group 4: browser_wait_for with 8 seconds (expected: FAIL/HANG)"
echo "---"
for i in $(seq 1 $ITERATIONS); do
    if run_wait_test 8 $i; then
        results["8s_iter${i}"]="PASS"
    else
        results["8s_iter${i}"]="FAIL"
    fi
    echo
    sleep 2
done

echo "========================================================================"
echo "  RESULTS SUMMARY"
echo "========================================================================"
echo

# Analyze results
echo "Test Results:"
echo "-------------"
for key in "${!results[@]}"; do
    if [[ "${results[$key]}" == "PASS" ]]; then
        echo -e "  ✓ ${key}: ${GREEN}PASS${NC}"
    else
        echo -e "  ✗ ${key}: ${RED}FAIL${NC}"
    fi
done | sort

echo
echo "Pattern Analysis:"
echo "-----------------"

# Count passes/fails per duration
count_results() {
    local duration=$1
    local pass_count=0
    local fail_count=0

    for i in $(seq 1 $ITERATIONS); do
        if [[ "${results[${duration}_iter${i}]}" == "PASS" ]]; then
            ((pass_count++))
        else
            ((fail_count++))
        fi
    done

    echo "  ${duration}: ${pass_count}/${ITERATIONS} passed, ${fail_count}/${ITERATIONS} failed"

    if [ $pass_count -eq $ITERATIONS ]; then
        echo "    → Consistent SUCCESS"
        return 0
    elif [ $fail_count -eq $ITERATIONS ]; then
        echo "    → Consistent FAILURE"
        return 1
    else
        echo "    → INCONSISTENT (non-deterministic behavior detected)"
        return 2
    fi
}

echo
count_results "2s"
two_sec_result=$?
count_results "4s"
four_sec_result=$?
count_results "6s"
six_sec_result=$?
count_results "8s"
eight_sec_result=$?

echo
echo "========================================================================"
echo "  HYPOTHESIS VALIDATION"
echo "========================================================================"
echo

if [ $two_sec_result -eq 0 ] && [ $four_sec_result -eq 0 ] && \
   [ $six_sec_result -eq 1 ] && [ $eight_sec_result -eq 1 ]; then
    echo -e "${GREEN}✓ HYPOTHESIS CONFIRMED${NC}"
    echo
    echo "Clear threshold detected between 4-6 seconds:"
    echo "  • Wait times < 5s: Consistently SUCCEED"
    echo "  • Wait times ≥ 5s: Consistently FAIL"
    echo
    echo "This confirms the 5-second MCP ping timeout issue:"
    echo "  1. Upstream playwright-mcp has hardcoded 5s ping timeout"
    echo "  2. Operations taking longer than 5s trigger disconnection"
    echo "  3. The proxy cannot respond to pings during blocking call_tool()"
    echo
    echo "Recommendation: Implement async ping responder or split operations"
else
    echo -e "${YELLOW}⚠ HYPOTHESIS INCONCLUSIVE${NC}"
    echo
    echo "Results don't show a clear 5-second threshold."
    echo
    if [ $two_sec_result -ne 0 ] || [ $four_sec_result -ne 0 ]; then
        echo "Even short waits are failing - possible other issues:"
        echo "  • Network instability"
        echo "  • Docker resource constraints"
        echo "  • Upstream server issues"
    fi
    if [ $six_sec_result -eq 0 ] || [ $eight_sec_result -eq 0 ]; then
        echo "Long waits are succeeding - ping timeout may not be the issue:"
        echo "  • The 90s proxy timeout is giving enough time"
        echo "  • Upstream may have been fixed/configured differently"
        echo "  • Non-deterministic network behavior"
    fi
    if [ $two_sec_result -eq 2 ] || [ $four_sec_result -eq 2 ] || \
       [ $six_sec_result -eq 2 ] || [ $eight_sec_result -eq 2 ]; then
        echo "Inconsistent results detected:"
        echo "  • Non-deterministic behavior (race conditions?)"
        echo "  • Network variability"
        echo "  • Need more iterations to establish pattern"
    fi
fi

echo
echo "Test logs saved to /tmp/wait_*s_iter*.txt"
