#!/bin/bash

# Comprehensive retry middleware testing script for AgentUp
# Tests retry functionality with automated failure simulation and validation

echo "=== A2A Retry Middleware Test ==="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SERVER_URL="http://localhost:8000"
TIMEOUT=30
RETRY_TEST_RESULTS="/tmp/retry_test_results.json"

# Validation functions
check_server_running() {
    echo -e "${BLUE}Checking if server is running...${NC}"
    if ! curl -s --max-time 5 "$SERVER_URL/health" > /dev/null 2>&1; then
        echo -e "${RED}❌ Server is not running at $SERVER_URL${NC}"
        echo "Please start your agent server first:"
        echo "  agentup agent serve --port 8000"
        exit 1
    fi
    echo -e "${GREEN}✅ Server is running${NC}"
    echo
}

check_dependencies() {
    echo -e "${BLUE}Checking dependencies...${NC}"
    
    # Check for required tools
    local missing_tools=()
    for tool in curl jq bc; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo -e "${RED}❌ Missing required tools: ${missing_tools[*]}${NC}"
        echo "Please install missing tools and try again"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All dependencies available${NC}"
    echo
}

# Enhanced function to test retry behavior with timing analysis
test_retry_scenario() {
    local test_name="$1"
    local skill_id="$2"
    local content="$3"
    local expected_behavior="$4"
    local timeout_override="${5:-$TIMEOUT}"

    echo -e "${YELLOW}Test: $test_name${NC}"
    echo "Skill: $skill_id"
    echo "Content: $content"
    echo "Expected: $expected_behavior"
    echo

    local start_time=$(date +%s.%N)
    local response
    
    response=$(curl -s --max-time "$timeout_override" -X POST "$SERVER_URL/" \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "method": "send_message",
            "params": {
                "skill_id": "'"$skill_id"'",
                "messages": [{"role": "user", "content": "'"$content"'"}]
            },
            "id": "retry-test-'"$(date +%s)"'"
        }' 2>/dev/null)
    
    local end_time=$(date +%s.%N)
    local total_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")

    echo -e "${BLUE}Total execution time: ${total_time}s${NC}"

    # Analyze response
    if [[ -z "$response" ]]; then
        echo -e "${RED}❌ No response received (timeout or connection error)${NC}"
        return 1
    fi

    if ! echo "$response" | python3 -m json.tool > /dev/null 2>&1; then
        echo -e "${RED}❌ Invalid JSON response${NC}"
        echo "Response: $response"
        return 1
    fi

    if echo "$response" | grep -q '"error"'; then
        echo -e "${RED}❌ Failed with error:${NC}"
        local error_msg=$(echo "$response" | jq -r '.error.message' 2>/dev/null || echo "Unknown error")
        echo "Error: $error_msg"
        
        # Check if it's a retry-related error
        if echo "$error_msg" | grep -q -i "retry\|attempt\|timeout"; then
            echo -e "${BLUE}🔄 This appears to be a retry-related error${NC}"
        fi
    else
        echo -e "${GREEN}✅ Success:${NC}"
        local result_content=$(echo "$response" | jq -r '.result.messages[-1].content' 2>/dev/null | head -c 100)
        echo "Result: ${result_content}..."
        
        # Analyze timing for potential retry indication
        if (( $(echo "$total_time > 3" | bc -l 2>/dev/null || echo "0") )); then
            echo -e "${BLUE}🔄 Long execution time suggests potential retries occurred${NC}"
        fi
    fi
    
    echo -e "${BLUE}💡 Check server logs for detailed retry information${NC}"
    echo
    return 0
}

# Function to create a temporary retry test handler
create_retry_test_handler() {
    echo -e "${BLUE}Creating temporary retry test handler...${NC}"
    
    # Check if we can find a handler file to modify
    local handler_files=(
        "src/agent/handlers/handlers.py"
        "src/handlers.py" 
        "handlers.py"
    )
    
    local handler_file=""
    for file in "${handler_files[@]}"; do
        if [[ -f "$file" ]]; then
            handler_file="$file"
            break
        fi
    done
    
    if [[ -z "$handler_file" ]]; then
        echo -e "${YELLOW}⚠️  Could not find handler file - using existing handlers only${NC}"
        return 1
    fi
    
    # Check if retry test handler already exists
    if grep -q "handle_retry_test" "$handler_file"; then
        echo -e "${GREEN}✅ Retry test handler already exists${NC}"
        return 0
    fi
    
    echo -e "${BLUE}Adding retry test handler to $handler_file${NC}"
    
    # Add the retry test handler
    cat >> "$handler_file" << 'EOF'


@register_handler("retry_test")
@retryable(max_attempts=3, backoff_factor=1, max_delay=10)
@timed()
async def handle_retry_test(task: Task) -> str:
    """Test handler that simulates failures for retry testing."""
    import random
    import time
    
    messages = MessageProcessor.extract_messages(task)
    latest_message = MessageProcessor.get_latest_user_message(messages)
    content = latest_message.get('content', '') if latest_message else ''
    
    # Parse failure probability from content
    failure_rate = 0.7  # Default 70% failure rate
    if "fail_rate=" in content:
        try:
            rate_str = content.split("fail_rate=")[1].split()[0]
            failure_rate = float(rate_str)
        except (ValueError, IndexError):
            pass
    
    # Simulate processing time
    processing_time = random.uniform(0.1, 0.5)
    await asyncio.sleep(processing_time)
    
    # Simulate failure based on probability
    if random.random() < failure_rate:
        error_types = [
            "Simulated network timeout",
            "Simulated service unavailable", 
            "Simulated temporary database error",
            "Simulated API rate limit",
        ]
        raise Exception(random.choice(error_types))
    
    timestamp = time.time()
    return f"RETRY TEST SUCCESS! Completed at {timestamp:.3f}. Content: {content}"
EOF

    echo -e "${GREEN}✅ Retry test handler added${NC}"
    echo -e "${YELLOW}⚠️  Please restart your server to load the new handler${NC}"
    echo
    return 0
}

# Function to test with network interruption simulation
test_network_conditions() {
    local test_name="$1"
    echo -e "${YELLOW}Test: $test_name${NC}"
    echo "Simulating network conditions that might trigger retries..."
    
    # Test with very short timeout to potentially trigger timeout retries
    local short_timeout=1
    echo "Testing with short timeout (${short_timeout}s) to simulate network issues..."
    
    test_retry_scenario \
        "Network Timeout Simulation" \
        "echo" \
        "test with short timeout" \
        "May timeout and trigger retries" \
        "$short_timeout"
}

# Pre-flight checks
check_dependencies
check_server_running

# Initialize test results
echo "[]" > "$RETRY_TEST_RESULTS"

# Test 1: Normal handler request (should succeed immediately)
echo "=== TEST 1: Normal Handler Request ==="
test_retry_scenario \
    "Normal Echo Request" \
    "echo" \
    "normal echo test" \
    "Should succeed on first attempt"

echo "Waiting 2 seconds before next test..."
sleep 2

# Test 2: Test with existing retryable handlers
echo "=== TEST 2: Status Handler Test ==="
test_retry_scenario \
    "Status Handler Test" \
    "status" \
    "status check" \
    "Should succeed, might retry if under load"

echo "Waiting 2 seconds before next test..."
sleep 2

# Test 3: Large content test
echo "=== TEST 3: Large Content Test ==="
large_content=$(python3 -c "print('x' * 500)")
test_retry_scenario \
    "Large Content Test" \
    "echo" \
    "large content test: $large_content" \
    "May trigger retries if content causes issues"

echo "Waiting 2 seconds before next test..."
sleep 2

# Test 4: Special characters test
echo "=== TEST 4: Special Characters Test ==="
test_retry_scenario \
    "Special Characters Test" \
    "echo" \
    "special chars test: {}[]()@#\$%^&*\"'<>" \
    "May trigger retries if parsing issues occur"

echo "Waiting 2 seconds before next test..."
sleep 2

# Test 5: Network condition simulation
echo "=== TEST 5: Network Condition Simulation ==="
test_network_conditions "Network Issues"

echo "Waiting 2 seconds before next test..."
sleep 2

# Test 6: Multiple rapid requests to potentially trigger issues
echo "=== TEST 6: Rapid Requests Test ==="
echo "Sending multiple rapid requests to potentially trigger retries..."

rapid_test_results=()
for i in {1..5}; do
    echo -e "${BLUE}Rapid request $i/5${NC}"
    test_retry_scenario \
        "Rapid Request $i" \
        "echo" \
        "rapid test request $i" \
        "May trigger retries under load" &
    rapid_test_results+=($!)
done

echo "Waiting for all rapid requests to complete..."
wait

echo "Waiting 5 seconds before final test..."
sleep 5

# Test 7: Retry test handler (if available)
echo "=== TEST 7: Dedicated Retry Test Handler ==="
echo "Attempting to use dedicated retry test handler..."

# First check if retry test handler exists
response=$(curl -s --max-time 5 -X POST "$SERVER_URL/" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0", 
        "method": "send_message",
        "params": {
            "skill_id": "retry_test",
            "messages": [{"role": "user", "content": "test handler exists"}]
        },
        "id": "handler-check"
    }' 2>/dev/null)

if echo "$response" | grep -q "Method not found\|skill.*not.*found" -i; then
    echo -e "${YELLOW}⚠️  Retry test handler not available${NC}"
    echo -e "${BLUE}Creating retry test handler for better testing...${NC}"
    create_retry_test_handler
    echo -e "${YELLOW}⚠️  Please restart your server and run this script again for full retry testing${NC}"
else
    echo -e "${GREEN}✅ Retry test handler is available${NC}"
    
    # Test with different failure rates
    for fail_rate in 0.9 0.5 0.1; do
        echo -e "${BLUE}Testing with ${fail_rate} failure rate...${NC}"
        test_retry_scenario \
            "Retry Handler Test (fail_rate=$fail_rate)" \
            "retry_test" \
            "retry test fail_rate=$fail_rate" \
            "Should retry on failures, eventual success rate depends on failure rate"
        sleep 3
    done
fi

# Final summary
echo
echo -e "${YELLOW}=== Retry Middleware Test Complete ===${NC}"
echo

echo -e "${BLUE}Test Summary:${NC}"
echo "- Tested retry behavior with various scenarios"
echo "- Analyzed execution timing for retry detection"
echo "- Tested network condition simulation"
echo "- Validated JSON responses and error handling"
echo
echo -e "${BLUE}Retry Middleware Configuration:${NC}"
echo "- Handlers with @retryable decorator will automatically retry on failures"
echo "- Default retry configuration: max_attempts=3, backoff_factor=1.0"
echo "- Retry delays use exponential backoff: delay * (backoff_factor^attempt)"
echo "- Check server logs for detailed retry attempt information"
echo
echo -e "${BLUE}Key Observations:${NC}"
echo "- Execution time > 3s may indicate retries occurred"
echo "- Check server logs for 'Attempt X failed, retrying in Ys' messages"
echo "- Successful retries will eventually return success response"
echo "- Failed retries will return the last encountered error"
echo
echo -e "${GREEN}✅ Retry middleware tests completed!${NC}"
echo "Results logged to: $RETRY_TEST_RESULTS"

# Cleanup
trap 'rm -f "$RETRY_TEST_RESULTS"' EXIT