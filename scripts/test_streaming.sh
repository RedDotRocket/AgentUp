#!/bin/bash

# A2A Streaming Test Script for AgentUp
# Tests the message/stream endpoint using curl and Server-Sent Events

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
DEFAULT_URL="http://localhost:8000"
DEFAULT_TIMEOUT=30
TEMP_DIR="/tmp/streaming_test_$$"

# Global variables
AUTH_TOKEN=""
SERVER_URL="$DEFAULT_URL"
TIMEOUT="$DEFAULT_TIMEOUT"
SHOW_RAW=false
VERBOSE=false

# Help function
show_help() {
    cat << EOF
A2A Streaming Test Script for AgentUp

USAGE:
    $0 [OPTIONS] [MESSAGE]

OPTIONS:
    -u, --url URL           Server URL (default: $DEFAULT_URL)
    -t, --token TOKEN       Authentication token (Bearer token)
    -T, --timeout SECONDS   Request timeout (default: $DEFAULT_TIMEOUT)
    -r, --raw              Show raw SSE data
    -v, --verbose          Verbose output
    -h, --help             Show this help

EXAMPLES:
    # Basic test
    $0

    # With authentication
    $0 --token gho_xxxx

    # Custom message
    $0 "Tell me a joke"
    
    # With all options
    $0 --url http://localhost:8000 --token gho_xxxx --raw --verbose "Hello streaming"

    # Test multiple scenarios
    $0 --token gho_xxxx && echo "---" && $0 --token gho_xxxx "Count to 5"

DESCRIPTION:
    This script tests the A2A message/stream endpoint using Server-Sent Events (SSE).
    It sends a JSON-RPC request to the streaming endpoint and parses the SSE response
    in real-time, displaying formatted output for each event.

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--url)
                SERVER_URL="$2"
                shift 2
                ;;
            -t|--token)
                AUTH_TOKEN="$2"
                shift 2
                ;;
            -T|--timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            -r|--raw)
                SHOW_RAW=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                # This is the message
                MESSAGE="$1"
                shift
                ;;
        esac
    done
}

# Cleanup function
cleanup() {
    [[ -d "$TEMP_DIR" ]] && rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Setup temp directory
setup_temp_dir() {
    mkdir -p "$TEMP_DIR"
}

# Log functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}$1${NC}"
}

log_warning() {
    echo -e "${YELLOW}  $1${NC}"
}

log_error() {
    echo -e "${RED}  $1${NC}"
}

log_verbose() {
    [[ "$VERBOSE" == "true" ]] && echo -e "${CYAN}🔍 $1${NC}"
}

log_raw() {
    [[ "$SHOW_RAW" == "true" ]] && echo -e "${CYAN}📥 Raw: $1${NC}"
}

# Check if server is running
check_server() {
    log_info "Checking if server is running at $SERVER_URL"
    
    local status_code
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$SERVER_URL/" || echo "000")
    
    if [[ "$status_code" == "000" ]]; then
        log_error "Cannot connect to server at $SERVER_URL"
        echo "Please make sure your AgentUp server is running:"
        echo "  cd /path/to/your/agent"
        echo "  agentup agent serve"
        exit 1
    fi
    
    log_success "Server is reachable (HTTP $status_code)"
}

# Test authentication
test_auth() {
    log_info "Testing authentication"
    
    local auth_headers=""
    if [[ -n "$AUTH_TOKEN" ]]; then
        auth_headers="-H \"Authorization: Bearer $AUTH_TOKEN\""
    fi
    
    local response
    response=$(curl -s -X POST "$SERVER_URL/" \
        -H "Content-Type: application/json" \
        $auth_headers \
        -d '{"jsonrpc":"2.0","method":"status","id":1}' 2>/dev/null || echo '{"error": "connection_failed"}')
    
    log_verbose "Auth test response: $response"
    
    if echo "$response" | grep -q '"error"'; then
        local error_msg
        error_msg=$(echo "$response" | jq -r '.error.message // .detail // "Unknown error"' 2>/dev/null || echo "Parse error")
        
        if [[ "$error_msg" == "Unauthorized" ]]; then
            if [[ -z "$AUTH_TOKEN" ]]; then
                log_warning "Server requires authentication, but no token provided"
                echo "Use: $0 --token YOUR_TOKEN"
                return 1
            else
                log_error "Authentication failed with provided token"
                return 1
            fi
        else
            log_warning "Auth test returned error: $error_msg"
        fi
    else
        if [[ -n "$AUTH_TOKEN" ]]; then
            log_success "Authentication successful"
        else
            log_success "Server allows unauthenticated requests"
        fi
    fi
    
    return 0
}

# Generate JSON-RPC request
generate_request() {
    local message="$1"
    local message_id="msg-$(date +%s%N | cut -b1-13)"
    local request_id="req-$(date +%s%N | cut -b1-13)"
    
    cat << EOF
{
    "jsonrpc": "2.0",
    "method": "message/stream",
    "params": {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "$message"}],
            "message_id": "$message_id",
            "kind": "message"
        }
    },
    "id": "$request_id"
}
EOF
}

# Parse SSE event
parse_sse_event() {
    local json_data="$1"
    local event_num="$2"
    
    echo -e "${BLUE}📨 Event $event_num:${NC}"
    
    log_raw "$json_data"
    
    # Check if it's an error
    if echo "$json_data" | jq -e '.error' > /dev/null 2>&1; then
        local error_msg
        error_msg=$(echo "$json_data" | jq -r '.error.message // "Unknown error"' 2>/dev/null)
        log_error "Error: $error_msg"
        return
    fi
    
    # Check if it's a result
    if echo "$json_data" | jq -e '.result' > /dev/null 2>&1; then
        local task_id state
        task_id=$(echo "$json_data" | jq -r '.result.id // "unknown"' 2>/dev/null)
        state=$(echo "$json_data" | jq -r '.result.status.state // "unknown"' 2>/dev/null)
        
        echo "   🆔 Task ID: $task_id"
        echo "   📊 Status: $state"
        
        # Check for artifacts
        local artifact_count
        artifact_count=$(echo "$json_data" | jq '.result.artifacts | length' 2>/dev/null || echo "0")
        
        if [[ "$artifact_count" -gt 0 ]]; then
            echo "   📄 Artifacts ($artifact_count):"
            
            # Extract and display text from artifacts
            local artifact_text
            artifact_text=$(echo "$json_data" | jq -r '.result.artifacts[]?.parts[]? | select(.kind == "text") | .text' 2>/dev/null || echo "")
            
            if [[ -n "$artifact_text" ]]; then
                # Truncate long text and add proper indentation
                echo "$artifact_text" | head -c 300 | sed 's/^/      💬 /'
                if [[ ${#artifact_text} -gt 300 ]]; then
                    echo "      ..."
                fi
            fi
        fi
        
        # Check for history
        local history_count
        history_count=$(echo "$json_data" | jq '.result.history | length' 2>/dev/null || echo "0")
        
        if [[ "$history_count" -gt 0 ]]; then
            echo "   📚 History ($history_count messages)"
            
            # Show last few messages from history
            echo "$json_data" | jq -r '.result.history[-3:][]? | "      👤 " + .role + ": " + (.parts[]? | select(.kind == "text") | .text)' 2>/dev/null | head -c 200 | cut -c1-100
        fi
    fi
    
    echo
}

# Stream test function
test_streaming() {
    local message="$1"
    local request_file="$TEMP_DIR/request.json"
    local response_file="$TEMP_DIR/response.txt"
    
    log_info "Testing streaming endpoint"
    echo "📝 Message: $message"
    echo "🔄 Starting stream..."
    echo
    
    # Generate request
    generate_request "$message" > "$request_file"
    
    if [[ "$SHOW_RAW" == "true" ]]; then
        echo -e "${CYAN}📤 Request JSON:${NC}"
        cat "$request_file" | jq .
        echo
    fi
    
    # Prepare headers
    local headers=("-H" "Content-Type: application/json" "-H" "Accept: text/event-stream" "-H" "Cache-Control: no-cache")
    
    if [[ -n "$AUTH_TOKEN" ]]; then
        headers+=("-H" "Authorization: Bearer $AUTH_TOKEN")
    fi
    
    # Start streaming request
    log_verbose "Starting curl with streaming..."
    
    local event_count=0
    local success=true
    
    # Use curl with --no-buffer for real-time streaming
    curl -s --no-buffer --max-time "$TIMEOUT" \
        "${headers[@]}" \
        -X POST "$SERVER_URL/" \
        -d @"$request_file" | while IFS= read -r line; do
        
        log_raw "Line: $line"
        
        # Parse SSE format: "data: {json}"
        if [[ "$line" =~ ^data:\ (.+)$ ]]; then
            ((event_count++))
            local json_data="${BASH_REMATCH[1]}"
            parse_sse_event "$json_data" "$event_count"
        elif [[ "$line" =~ ^:.*$ ]]; then
            # SSE comment line
            log_verbose "SSE comment: $line"
        elif [[ -z "$line" ]]; then
            # Empty line (end of event)
            continue
        else
            # Unexpected line format
            if [[ "$line" == *"Unauthorized"* ]] || [[ "$line" == *"401"* ]]; then
                log_error "Unauthorized - check your authentication token"
                success=false
                break
            elif [[ "$line" == *"404"* ]] || [[ "$line" == *"Not Found"* ]]; then
                log_error "Endpoint not found - check your server URL and method"
                success=false
                break
            else
                log_warning "Unexpected line: $line"
            fi
        fi
    done
    
    local curl_exit_code=$?
    
    if [[ $curl_exit_code -eq 0 ]]; then
        log_success "Stream completed successfully"
        echo "📊 Total events processed: $event_count"
        return 0
    else
        log_error "Stream failed (curl exit code: $curl_exit_code)"
        
        case $curl_exit_code in
            7) log_error "Failed to connect to server" ;;
            28) log_error "Request timed out" ;;
            22) log_error "HTTP error response" ;;
            *) log_error "Unknown curl error" ;;
        esac
        return 1
    fi
}

# Main function
main() {
    local message="${MESSAGE:-Hello, this is a streaming test from shell script}"
    
    echo -e "${BLUE}🧪 A2A Streaming Test Script${NC}"
    echo "=================================="
    echo
    echo "🎯 Target URL: $SERVER_URL"
    echo "🔑 Auth Token: $([ -n "$AUTH_TOKEN" ] && echo 'Provided' || echo 'None')"
    echo "📝 Message: $message"
    echo "⏱️  Timeout: ${TIMEOUT}s"
    echo "🔍 Raw Mode: $SHOW_RAW"
    echo "📢 Verbose: $VERBOSE"
    echo
    
    setup_temp_dir
    
    # Run tests
    check_server || exit 1
    echo
    
    test_auth || {
        log_error "Authentication test failed"
        exit 1
    }
    echo
    
    test_streaming "$message" || {
        log_error "Streaming test failed"
        exit 1
    }
    
    echo
    log_success "All tests completed!"
}

# Parse arguments and run
parse_args "$@"
main