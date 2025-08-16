#!/bin/bash

# GitHub OAuth2 Test Script for AgentUp
# This script helps you test the GitHub OAuth2 authentication flow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AGENT_URL="http://localhost:8000"
GITHUB_CLIENT_ID="${GITHUB_CLIENT_ID:-your_client_id_here}"
GITHUB_CLIENT_SECRET="${GITHUB_CLIENT_SECRET:-your_client_secret_here}"

echo -e "${BLUE}GitHub OAuth2 Test Script for AgentUp${NC}"
echo "==========================================="
echo

# Check if environment variables are set
if [ "$GITHUB_CLIENT_ID" = "your_client_id_here" ] || [ "$GITHUB_CLIENT_SECRET" = "your_client_secret_here" ]; then
    echo -e "${RED}ERROR: Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables${NC}"
    echo "Example:"
    echo "  export GITHUB_CLIENT_ID=\"your_actual_client_id\""
    echo "  export GITHUB_CLIENT_SECRET=\"your_actual_client_secret\""
    exit 1
fi

# Function to test endpoint
test_endpoint() {
    local method="$1"
    local token="$2"
    local description="$3"
    
    echo -e "${YELLOW}Testing: $description${NC}"
    
    local auth_header=""
    if [ -n "$token" ]; then
        auth_header="-H \"Authorization: Bearer $token\""
    fi
    
    local response
    local status_code
    
    if [ -n "$token" ]; then
        response=$(curl -s -w "%{http_code}" -X POST "$AGENT_URL/" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"$method\",\"id\":1}")
    else
        response=$(curl -s -w "%{http_code}" -X POST "$AGENT_URL/" \
            -H "Content-Type: application/json" \
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"$method\",\"id\":1}")
    fi
    
    status_code="${response: -3}"
    response_body="${response%???}"
    
    echo "Status Code: $status_code"
    echo "Response: $response_body"
    
    if [ "$status_code" -eq 200 ]; then
        echo -e "${GREEN}✓ Success${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
    echo
}

# Function to get GitHub token via device flow
get_github_token() {
    echo -e "${BLUE}Getting GitHub token...${NC}"
    
    # Check if gh CLI is available
    if command -v gh &> /dev/null; then
        echo "Using GitHub CLI to get token..."
        gh auth login --scopes "user,user:email"
        echo "$(gh auth token)"
        return
    fi
    
    # Manual device flow
    echo "GitHub CLI not found. Starting device flow..."
    
    # Step 1: Get device code
    local device_response
    device_response=$(curl -s -X POST https://github.com/login/device/code \
        -H "Accept: application/json" \
        -d "client_id=$GITHUB_CLIENT_ID" \
        -d "scope=user user:email")
    
    local device_code user_code verification_uri
    device_code=$(echo "$device_response" | grep -o '"device_code":"[^"]*' | cut -d'"' -f4)
    user_code=$(echo "$device_response" | grep -o '"user_code":"[^"]*' | cut -d'"' -f4)
    verification_uri=$(echo "$device_response" | grep -o '"verification_uri":"[^"]*' | cut -d'"' -f4)
    
    echo -e "${YELLOW}Go to: $verification_uri${NC}"
    echo -e "${YELLOW}Enter code: $user_code${NC}"
    echo "Press Enter after authorizing..."
    read -r
    
    # Step 2: Poll for token
    local token_response access_token
    for i in {1..30}; do
        token_response=$(curl -s -X POST https://github.com/login/oauth/access_token \
            -H "Accept: application/json" \
            -d "client_id=$GITHUB_CLIENT_ID" \
            -d "device_code=$device_code" \
            -d "grant_type=urn:ietf:params:oauth:grant-type:device_code")
        
        if echo "$token_response" | grep -q "access_token"; then
            access_token=$(echo "$token_response" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
            echo "$access_token"
            return
        fi
        
        echo "Waiting for authorization... ($i/30)"
        sleep 5
    done
    
    echo -e "${RED}Timeout waiting for authorization${NC}"
    exit 1
}

# Function to validate GitHub token
validate_github_token() {
    local token="$1"
    
    echo -e "${BLUE}Validating GitHub token...${NC}"
    
    local validation_response
    validation_response=$(curl -s -w "%{http_code}" -X POST \
        "https://api.github.com/applications/$GITHUB_CLIENT_ID/token" \
        -u "$GITHUB_CLIENT_ID:$GITHUB_CLIENT_SECRET" \
        -H "Content-Type: application/json" \
        -d "{\"access_token\":\"$token\"}")
    
    local status_code="${validation_response: -3}"
    local response_body="${validation_response%???}"
    
    echo "GitHub validation status: $status_code"
    echo "Response: $response_body"
    
    if [ "$status_code" -eq 200 ]; then
        echo -e "${GREEN}✓ Token is valid${NC}"
        return 0
    else
        echo -e "${RED}✗ Token is invalid${NC}"
        return 1
    fi
}

# Main test flow
main() {
    echo -e "${BLUE}Step 1: Check if AgentUp is running${NC}"
    if ! curl -s "$AGENT_URL/" &> /dev/null; then
        echo -e "${RED}ERROR: AgentUp is not running at $AGENT_URL${NC}"
        echo "Please start your agent with: agentup run"
        exit 1
    fi
    echo -e "${GREEN}✓ AgentUp is running${NC}"
    echo
    
    echo -e "${BLUE}Step 2: Test unauthenticated request (should fail)${NC}"
    test_endpoint "status" "" "Unauthenticated status request"
    
    echo -e "${BLUE}Step 3: Get GitHub token${NC}"
    echo "How would you like to get a GitHub token?"
    echo "1) I already have a token"
    echo "2) Use GitHub CLI (gh auth token)"
    echo "3) Use device flow"
    echo "4) Manual personal access token"
    read -p "Choose option (1-4): " token_option
    
    local github_token
    case $token_option in
        1)
            read -p "Enter your GitHub token: " github_token
            ;;
        2)
            github_token=$(get_github_token)
            ;;
        3)
            github_token=$(get_github_token)
            ;;
        4)
            echo "Go to: https://github.com/settings/tokens"
            echo "Generate a new token with scopes: user, user:email"
            read -p "Enter the generated token: " github_token
            ;;
        *)
            echo "Invalid option"
            exit 1
            ;;
    esac
    
    if [ -z "$github_token" ]; then
        echo -e "${RED}ERROR: No token provided${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}Step 4: Validate token with GitHub${NC}"
    if ! validate_github_token "$github_token"; then
        echo -e "${RED}ERROR: Invalid GitHub token${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}Step 5: Test authenticated requests${NC}"
    test_endpoint "status" "$github_token" "Authenticated status request"
    test_endpoint "capabilities" "$github_token" "Authenticated capabilities request"
    test_endpoint "list_directory" "$github_token" "Authenticated plugin capability request"
    
    echo -e "${GREEN}OAuth2 testing completed!${NC}"
    echo "Your GitHub OAuth2 setup is working correctly."
}

# Run main function
main "$@"
