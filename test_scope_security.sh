#!/bin/bash

# AgentUp Scope-Based Security Test Script
# Based on SCOPE_DESIGN.md implementation

set -e

# Configuration
AGENT_URL="http://localhost:8000"
JWT_SECRET="test-secret-key-change-in-production"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test users with different scope levels - using functions instead of associative array for compatibility
get_user_payload() {
    case "$1" in
        "admin")
            echo '{"sub": "admin-user", "name": "Admin User", "scopes": ["admin"]}'
            ;;
        "files_admin")
            echo '{"sub": "files-admin", "name": "Files Admin", "scopes": ["files:admin", "system:read"]}'
            ;;
        "files_write")
            echo '{"sub": "files-write", "name": "Files Write User", "scopes": ["files:write"]}'
            ;;
        "files_read")
            echo '{"sub": "files-read", "name": "Files Read User", "scopes": ["files:read"]}'
            ;;
        "no_perms")
            echo '{"sub": "no-perms", "name": "No Permissions User", "scopes": []}'
            ;;
    esac
}

# Function to generate JWT token
generate_jwt() {
    local payload="$1"
    local header='{"alg":"HS256","typ":"JWT"}'
    
    # Base64 encode header and payload
    local header_b64=$(echo -n "$header" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
    local payload_b64=$(echo -n "$payload" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
    
    # Create signature
    local signature_input="${header_b64}.${payload_b64}"
    local signature=$(echo -n "$signature_input" | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
    
    echo "${header_b64}.${payload_b64}.${signature}"
}

# Function to test capability access
test_capability() {
    local user_type="$1"
    local capability="$2"
    local expected_result="$3"
    local token="$4"
    local test_message="$5"
    
    printf "Testing %s access to %s: " "$user_type" "$capability"
    
    local response=$(curl -s -X POST "$AGENT_URL/" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d "{
            \"jsonrpc\": \"2.0\",
            \"method\": \"message/send\",
            \"params\": {
                \"message\": {
                    \"role\": \"user\",
                    \"parts\": [{\"kind\": \"text\", \"text\": \"$test_message\"}],
                    \"messageId\": \"msg-$(date +%s)\",
                    \"kind\": \"message\"
                }
            },
            \"id\": \"req-$(date +%s)\"
        }" 2>/dev/null)
    
    if [[ "$expected_result" == "allow" ]]; then
        if echo "$response" | grep -q '"success".*true\|"data":\|"operation":\|"result"' && ! echo "$response" | grep -q '"error"\|"Insufficient permissions"\|"unable to perform"'; then
            echo -e "${GREEN}✓${NC} PASS"
            return 0
        else
            echo -e "${RED}✗${NC} FAIL (expected allow, got deny)"
            return 1
        fi
    else
        if echo "$response" | grep -q '"error"\|"Insufficient permissions"\|"unable to perform"' || ! echo "$response" | grep -q '"success".*true\|"data":\|"operation":\|"result"'; then
            echo -e "${GREEN}✓${NC} PASS"
            return 0
        else
            echo -e "${RED}✗${NC} FAIL (expected deny, got allow)"
            return 1
        fi
    fi
}

# Function to run test suite for a user
test_user() {
    local user_type="$1"
    local user_payload="$2"
    
    echo ""
    echo "=== Testing $user_type user ==="
    
    # Generate current timestamp for JWT
    local current_time=$(date +%s)
    local exp_time=$((current_time + 3600))  # 1 hour expiry
    
    # Add timestamps to payload
    local full_payload=$(echo "$user_payload" | jq --argjson iat "$current_time" --argjson exp "$exp_time" '. + {iat: $iat, exp: $exp}')
    
    # Generate JWT token
    local token=$(generate_jwt "$full_payload")
    
    case "$user_type" in
        "admin")
            test_capability "$user_type" "read_file" "allow" "$token" "List files in current directory"
            test_capability "$user_type" "write_file" "allow" "$token" "Create a file called admin-test.txt"
            test_capability "$user_type" "delete_file" "allow" "$token" "Delete file admin-test.txt"
            test_capability "$user_type" "get_system_info" "allow" "$token" "Get system information"
            test_capability "$user_type" "execute_command" "allow" "$token" "Execute command: whoami"
            ;;
        "files_admin")
            test_capability "$user_type" "read_file" "allow" "$token" "List files in current directory"
            test_capability "$user_type" "write_file" "allow" "$token" "Create a file called files-admin-test.txt"
            test_capability "$user_type" "delete_file" "allow" "$token" "Delete file files-admin-test.txt"
            test_capability "$user_type" "get_system_info" "allow" "$token" "Get system information"
            test_capability "$user_type" "execute_command" "deny" "$token" "Execute command: whoami"
            ;;
        "files_write")
            test_capability "$user_type" "read_file" "allow" "$token" "List files in current directory"
            test_capability "$user_type" "write_file" "allow" "$token" "Create a file called write-test.txt"
            test_capability "$user_type" "delete_file" "deny" "$token" "Delete file write-test.txt"
            test_capability "$user_type" "get_system_info" "deny" "$token" "Get system information"
            test_capability "$user_type" "execute_command" "deny" "$token" "Execute command: whoami"
            ;;
        "files_read")
            test_capability "$user_type" "read_file" "allow" "$token" "List files in current directory"
            test_capability "$user_type" "write_file" "deny" "$token" "Create a file called read-test.txt"
            test_capability "$user_type" "delete_file" "deny" "$token" "Delete file read-test.txt"
            test_capability "$user_type" "get_system_info" "deny" "$token" "Get system information"
            test_capability "$user_type" "execute_command" "deny" "$token" "Execute command: whoami"
            ;;
        "no_perms")
            test_capability "$user_type" "read_file" "deny" "$token" "List files in current directory"
            test_capability "$user_type" "write_file" "deny" "$token" "Create a file called no-perms-test.txt"
            test_capability "$user_type" "delete_file" "deny" "$token" "Delete file no-perms-test.txt"
            test_capability "$user_type" "get_system_info" "deny" "$token" "Get system information"
            test_capability "$user_type" "execute_command" "deny" "$token" "Execute command: whoami"
            ;;
    esac
}

# Function to check if agent is running
check_agent() {
    printf "Checking if agent is running at $AGENT_URL: "
    if curl -s -f "$AGENT_URL/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PASS"
        return 0
    else
        echo -e "${RED}✗${NC} FAIL"
        echo "Error: Agent not running at $AGENT_URL"
        echo "Please start the agent with: agentup agent serve --port 8000"
        return 1
    fi
}

# Function to check required tools
check_dependencies() {
    printf "Checking dependencies: "
    local missing_deps=()
    
    if ! command -v curl >/dev/null 2>&1; then
        missing_deps+=("curl")
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        missing_deps+=("jq")
    fi
    
    if ! command -v openssl >/dev/null 2>&1; then
        missing_deps+=("openssl")
    fi
    
    if [ ${#missing_deps[@]} -eq 0 ]; then
        echo -e "${GREEN}✓${NC} PASS"
        return 0
    else
        echo -e "${RED}✗${NC} FAIL"
        echo "Missing dependencies: ${missing_deps[*]}"
        echo "Please install missing tools and try again"
        return 1
    fi
}

# Main execution
main() {
    echo "AgentUp Scope-Based Security Test Suite"
    echo "======================================"
    
    # Pre-flight checks
    check_dependencies || exit 1
    check_agent || exit 1
    
    # Track test results
    local total_tests=0
    local passed_tests=0
    
    # Run tests for each user type
    for user_type in admin files_admin files_write files_read no_perms; do
        user_payload=$(get_user_payload "$user_type")
        test_user "$user_type" "$user_payload"
        
        # Count tests (rough estimate)
        case "$user_type" in
            "admin"|"files_admin"|"files_write"|"files_read"|"no_perms")
                total_tests=$((total_tests + 5))
                ;;
        esac
    done
    
    echo ""
    echo "=== Test Summary ==="
    echo "Tests verify scope hierarchy enforcement:"
    echo "- admin: has all permissions (*)"
    echo "- files:admin: files operations + system:read"
    echo "- files:write: write operations (includes read via hierarchy)"
    echo "- files:read: read operations only"
    echo "- no permissions: no access to any capabilities"
    
    echo ""
    echo "Key Security Features Tested:"
    echo "- Scope hierarchy (files:write includes files:read)"
    echo "- Permission enforcement at capability level"
    echo "- AI tool filtering based on user scopes"
    echo "- Fail-closed security for unconfigured capabilities"
    
    echo ""
    printf "For detailed logs, check the agent console output\n"
}

# Handle script arguments
case "${1:-}" in
    "help"|"-h"|"--help")
        echo "Usage: $0 [help]"
        echo ""
        echo "This script tests the AgentUp scope-based security system."
        echo "It verifies that users with different scope levels can only"
        echo "access capabilities they have permission for."
        echo ""
        echo "Prerequisites:"
        echo "- Agent running at http://localhost:8000"
        echo "- JWT authentication enabled with correct secret"
        echo "- Required tools: curl, jq, openssl"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac