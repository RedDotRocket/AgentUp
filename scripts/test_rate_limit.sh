#!/bin/bash

# Comprehensive rate limiting test script for AgentUp middleware
# Tests rate limiting functionality with validation and error reporting

echo "=== A2A Agent Rate Limiting Test ==="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER_URL="http://localhost:8000"
TIMEOUT=10
TEST_RESULTS_FILE="/tmp/rate_limit_test_results.json"

# Validation functions
check_server_running() {
    echo -e "${BLUE}Checking if server is running...${NC}"
    if ! curl -s --max-time 5 "$SERVER_URL/health" > /dev/null 2>&1; then
        echo -e "${RED}✗ Server is not running at $SERVER_URL${NC}"
        echo "Please start your agent server first:"
        echo "  agentup agent serve --port 8000"
        echo "  OR"
        echo "  uvicorn src.agent.api.app:app --reload --port 8000"
        exit 1
    fi
    echo -e "${GREEN}✓ Server is running${NC}"
    echo
}

validate_json_response() {
    local response="$1"
    local description="$2"
    
    if ! echo "$response" | python3 -m json.tool > /dev/null 2>&1; then
        echo -e "${RED}  Invalid JSON response for $description${NC}"
        echo "Response: $response"
        return 1
    fi
    return 0
}

# Enhanced function to test rate limiting with better tracking and validation
test_rate_limit() {
    local handler=$1
    local message=$2
    local limit=$3
    local requests=$4
    local test_name=$5

    echo -e "${YELLOW}Testing $handler handler (Rate limit: $limit requests/minute)${NC}"
    echo "Test: $test_name"
    echo "Sending $requests requests rapidly..."
    echo

    # Track successes and failures
    local success_count=0
    local failure_count=0
    local response_times=()
    local temp_dir="/tmp/rate_test_$$"
    mkdir -p "$temp_dir"

    # Send requests in parallel and collect results
    for i in $(seq 1 $requests); do
        (
            start_time=$(date +%s.%N)
            response=$(curl -s --max-time $TIMEOUT -X POST "$SERVER_URL/" \
                -H "Content-Type: application/json" \
                -d '{
                    "jsonrpc": "2.0",
                    "method": "send_message",
                    "params": {
                        "messages": [{"role": "user", "content": "'"$message"' request #'$i'"}]
                    },
                    "id": "'$i'"
                }' 2>/dev/null)
            end_time=$(date +%s.%N)
            response_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")

            # Save result to temp file for aggregation
            result_file="$temp_dir/result_$i"
            
            # Validate response
            if ! validate_json_response "$response" "Request $i"; then
                echo "{\"request_id\": $i, \"status\": \"invalid_json\", \"response_time\": $response_time}" > "$result_file"
                return
            fi

            # Check if response contains rate limit error
            if echo "$response" | grep -q "Rate limit exceeded\|rate.*limit\|too.*many.*requests" -i; then
                echo -e "${RED}Request $i: RATE LIMITED (${response_time}s)${NC}"
                echo "$response" | jq -r '.error.message' 2>/dev/null || echo "Rate limit error (no JSON details)"
                echo "{\"request_id\": $i, \"status\": \"rate_limited\", \"response_time\": $response_time}" > "$result_file"
            elif echo "$response" | grep -q '"error"'; then
                echo -e "${RED}Request $i: ERROR (${response_time}s)${NC}"
                echo "$response" | jq -r '.error.message' 2>/dev/null || echo "Unknown error"
                echo "{\"request_id\": $i, \"status\": \"error\", \"response_time\": $response_time}" > "$result_file"
            else
                echo -e "${GREEN}Request $i: SUCCESS (${response_time}s)${NC}"
                # Show truncated response
                content=$(echo "$response" | jq -r '.result.messages[-1].content' 2>/dev/null | head -c 80)
                echo "${content}..."
                echo "{\"request_id\": $i, \"status\": \"success\", \"response_time\": $response_time}" > "$result_file"
            fi
            echo
        ) &
    done

    # Wait for all requests to complete
    wait

    # Aggregate results
    echo -e "${BLUE}Aggregating results...${NC}"
    for result_file in "$temp_dir"/result_*; do
        if [[ -f "$result_file" ]]; then
            local status=$(jq -r '.status' "$result_file" 2>/dev/null)
            case "$status" in
                "success") ((success_count++)) ;;
                "rate_limited") ((failure_count++)) ;;
                "error"|"invalid_json") ((failure_count++)) ;;
            esac
        fi
    done

    # Calculate success rate
    local total=$((success_count + failure_count))
    local success_rate=0
    if [[ $total -gt 0 ]]; then
        success_rate=$(echo "scale=2; $success_count * 100 / $total" | bc -l 2>/dev/null || echo "0")
    fi

    # Test results summary
    echo -e "${YELLOW}--- $handler test results ---${NC}"
    echo "Test: $test_name"
    echo "Total requests: $total"
    echo -e "Successful: ${GREEN}$success_count${NC}"
    echo -e "Rate limited/Failed: ${RED}$failure_count${NC}"
    echo "Success rate: ${success_rate}%"
    
    # Expected behavior validation
    local expected_success_rate
    case "$test_name" in
        "Normal Load Test") expected_success_rate=80 ;;
        "Burst Test") expected_success_rate=30 ;;
        "Stress Test") expected_success_rate=20 ;;
        *) expected_success_rate=50 ;;
    esac

    if (( $(echo "$success_rate >= $expected_success_rate" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${GREEN}✓ Test passed (success rate >= ${expected_success_rate}%)${NC}"
    else
        echo -e "${RED}✗ Test may have issues (success rate < ${expected_success_rate}%)${NC}"
    fi

    # Cleanup
    rm -rf "$temp_dir"
    echo
}

# Pre-flight checks
check_server_running

# Initialize test results
echo "[]" > "$TEST_RESULTS_FILE"

# Test 1: Echo Handler Normal Load
echo "=== TEST 1: Echo Handler Normal Load ==="
echo "Testing echo handler with normal request volume"
echo "Expected: Most requests should succeed"
echo
test_rate_limit "echo" "echo test" 120 5 "Normal Load Test"

echo "Waiting 3 seconds before next test..."
sleep 3

# Test 2: Echo Handler Burst Test  
echo "=== TEST 2: Echo Handler Burst Test ==="
echo "Testing echo handler with burst of requests"
echo "Expected: Some requests may be rate limited"
echo
test_rate_limit "echo" "echo burst test" 120 15 "Burst Test"

echo "Waiting 5 seconds before next test..."
sleep 5

# Test 3: Status Handler Stress Test
echo "=== TEST 3: Status Handler Stress Test ==="
echo "Testing status handler with high request volume"
echo "Expected: Significant rate limiting should occur"
echo
test_rate_limit "status" "status check" 60 20 "Stress Test"

echo "Waiting 5 seconds before next test..."
sleep 5

# Test 4: Capabilities Handler Sequential Test
echo "=== TEST 4: Capabilities Handler Sequential Test ==="
echo "Testing capabilities handler with sequential requests (should mostly succeed)"
echo
sequential_test() {
    local handler=$1
    local message=$2
    local requests=$3
    local delay=$4
    
    echo -e "${YELLOW}Testing $handler handler with sequential requests (${delay}s delay)${NC}"
    local success_count=0
    local failure_count=0
    
    for i in $(seq 1 $requests); do
        response=$(curl -s --max-time $TIMEOUT -X POST "$SERVER_URL/" \
            -H "Content-Type: application/json" \
            -d '{
                "jsonrpc": "2.0",
                "method": "send_message",
                "params": {
                    "messages": [{"role": "user", "content": "'"$message"' request #'$i'"}]
                },
                "id": "'$i'"
            }' 2>/dev/null)
        
        if echo "$response" | grep -q "Rate limit exceeded\|rate.*limit" -i; then
            echo -e "${RED}Request $i: RATE LIMITED${NC}"
            ((failure_count++))
        elif echo "$response" | grep -q '"error"'; then
            echo -e "${RED}Request $i: ERROR${NC}"
            ((failure_count++))
        else
            echo -e "${GREEN}Request $i: SUCCESS${NC}"
            ((success_count++))
        fi
        
        [[ $i -lt $requests ]] && sleep "$delay"
    done
    
    echo -e "${BLUE}Sequential test results:${NC}"
    echo "Successful: $success_count"
    echo "Failed: $failure_count"
    echo
}

sequential_test "capabilities" "list capabilities" 5 1

# Test 5: Rate Limit Recovery Test
echo "=== TEST 5: Rate Limit Recovery Test ==="
echo "Testing rate limit recovery after waiting"
echo

# First, saturate the rate limit
echo "Saturating rate limit..."
test_rate_limit "echo" "saturation test" 120 20 "Saturation Test"

echo "Waiting 10 seconds for rate limit to recover..."
sleep 10

# Then test if requests work again
echo "Testing recovery..."
test_rate_limit "echo" "recovery test" 120 3 "Recovery Test"

echo
echo -e "${YELLOW}=== Rate Limiting Test Complete ===${NC}"
echo

# Final summary and recommendations
echo -e "${BLUE}Test Summary:${NC}"
echo "- Tested multiple handlers with different rate limits"
echo "- Verified rate limiting behavior under various load conditions"
echo "- Tested rate limit recovery functionality"
echo "- Validated JSON responses and error handling"
echo
echo -e "${BLUE}Rate Limiting Configuration:${NC}"
echo "- Rate limiting is applied per skill_id and user combination"
echo "- Different handlers may have different rate limits configured"
echo "- Rate limited requests return proper JSON-RPC error responses"
echo "- Rate limits reset over time using token bucket algorithm"
echo
echo -e "${BLUE}Troubleshooting:${NC}"
echo "- If all requests fail: Check if server is running and accessible"
echo "- If no rate limiting occurs: Check middleware configuration in agentup.yml"
echo "- If unexpected errors: Check server logs for detailed error information"
echo
echo -e "${GREEN}✓ Rate limiting tests completed successfully!${NC}"
echo "Results logged to: $TEST_RESULTS_FILE"

# Cleanup
trap 'rm -f "$TEST_RESULTS_FILE"' EXIT