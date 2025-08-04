#!/bin/bash

# MCP Integration Test Runner
# This script orchestrates the execution of MCP integration tests across all transport types

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'  
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_RESULTS_DIR="$PROJECT_ROOT/test_results/mcp_integration"
LOG_FILE="$TEST_RESULTS_DIR/mcp_test.log"

# Test configuration
MCP_SERVER_PORT=8123
AGENTUP_SERVER_PORT=8000
AUTH_TOKEN="test-token-123"
INVALID_AUTH_TOKEN="wrong-token-456"

# Cleanup tracking
CLEANUP_PIDS=()
CLEANUP_DIRS=()

# Ensure log directory exists
mkdir -p "$TEST_RESULTS_DIR"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Cleanup function
cleanup() {
    log_info "Starting cleanup..."
    
    # Kill any background processes
    for pid in "${CLEANUP_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping process $pid"
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    
    # Remove temporary directories
    for dir in "${CLEANUP_DIRS[@]}"; do
        if [[ -d "$dir" ]]; then
            log_info "Removing temporary directory $dir"
            rm -rf "$dir"
        fi
    done
    
    # Clean up environment variables
    unset MCP_API_KEY AGENT_CONFIG_PATH SERVER_PORT
    
    # Kill any remaining MCP or AgentUp processes on test ports
    lsof -ti:$MCP_SERVER_PORT | xargs kill -9 2>/dev/null || true
    lsof -ti:$AGENTUP_SERVER_PORT | xargs kill -9 2>/dev/null || true
    
    log_info "Cleanup completed"
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

# Setup function
setup() {
    log_info "Setting up MCP integration test environment..."
    
    # Clear log file
    > "$LOG_FILE"
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Check dependencies
    log_info "Checking dependencies..."
    
    if ! command -v uv &> /dev/null; then
        log_error "uv is required but not installed"
        exit 1
    fi
    
    if ! command -v python &> /dev/null; then
        log_error "python is required but not installed"
        exit 1
    fi
    
    # Install dependencies
    log_info "Installing dependencies..."
    uv sync --all-extras --dev
    
    # Verify MCP weather server exists
    if [[ ! -f "$PROJECT_ROOT/scripts/mcp/weather_server.py" ]]; then
        log_error "MCP weather server not found at scripts/mcp/weather_server.py"
        exit 1
    fi
    
    # Set environment variables
    export RUN_MCP_TESTS=1
    export MCP_API_KEY="$AUTH_TOKEN"
    
    log_success "Setup completed"
}

# Test individual transport
test_transport() {
    local transport="$1"
    log_info "Testing MCP transport: $transport"
    
    # Run pytest for specific transport
    local test_cmd="uv run pytest tests/integration/test_mcp_integration.py -v -s \
        --tb=short \
        --transport_type=$transport \
        --junit-xml=$TEST_RESULTS_DIR/junit_${transport}.xml \
        --log-cli-level=INFO \
        --log-file=$TEST_RESULTS_DIR/${transport}_test.log"
    
    if $test_cmd; then
        log_success "Transport $transport tests passed"
        return 0
    else
        log_error "Transport $transport tests failed"
        return 1
    fi
}

# Test authentication
test_authentication() {
    log_info "Testing MCP authentication..."
    
    local auth_test_cmd="uv run pytest tests/integration/test_mcp_integration.py::TestMCPAuthentication -v -s \
        --tb=short \
        --junit-xml=$TEST_RESULTS_DIR/junit_auth.xml \
        --log-cli-level=INFO \
        --log-file=$TEST_RESULTS_DIR/auth_test.log"
    
    if $auth_test_cmd; then
        log_success "Authentication tests passed"
        return 0
    else
        log_error "Authentication tests failed"
        return 1
    fi
}

# Run all tests
run_all_tests() {
    log_info "Running comprehensive MCP integration tests..."
    
    local all_tests_cmd="uv run pytest tests/integration/test_mcp_integration.py -v -s \
        --tb=short \
        --junit-xml=$TEST_RESULTS_DIR/junit_all.xml \
        --log-cli-level=INFO \
        --log-file=$TEST_RESULTS_DIR/all_tests.log \
        --cov=src/agent/mcp_support \
        --cov-report=html:$TEST_RESULTS_DIR/coverage_html \
        --cov-report=xml:$TEST_RESULTS_DIR/coverage.xml"
    
    if $all_tests_cmd; then
        log_success "All MCP integration tests passed"
        return 0
    else
        log_error "Some MCP integration tests failed"
        return 1
    fi
}

# Health check
health_check() {
    log_info "Running MCP integration health check..."
    
    # Test mock LLM provider
    log_info "Testing mock LLM provider..."
    if uv run python tests/integration/mocks/mock_llm_provider.py; then
        log_success "Mock LLM provider test passed"
    else
        log_error "Mock LLM provider test failed"
        return 1
    fi
    
    # Test MCP weather server startup
    log_info "Testing MCP weather server startup..."
    local temp_dir=$(mktemp -d)
    CLEANUP_DIRS+=("$temp_dir")
    
    # Test stdio transport (simple startup test)
    log_info "Testing stdio transport server startup..."
    # For stdio, we just test that the server can be imported and starts without immediate errors
    if uv run python -c "
import sys
sys.path.insert(0, 'scripts/mcp')
try:
    from weather_server import main
    print('Stdio server imports successfully')
except Exception as e:
    print(f'Import error: {e}')
    sys.exit(1)
" > "$temp_dir/stdio_test.log" 2>&1; then
        log_success "Stdio transport server imports successfully"
    else
        log_error "Stdio transport server failed to import"
        cat "$temp_dir/stdio_test.log"
        return 1
    fi
    
    # Test HTTP transport
    uv run python scripts/mcp/weather_server.py --transport sse --port $((MCP_SERVER_PORT + 1)) \
        --auth-token "$AUTH_TOKEN" > "$temp_dir/sse_test.log" 2>&1 &
    local sse_pid=$!
    CLEANUP_PIDS+=("$sse_pid")
    
    sleep 3
    
    if kill -0 "$sse_pid" 2>/dev/null; then
        log_success "SSE transport server started successfully"
        kill "$sse_pid" 2>/dev/null || true
    else
        log_error "SSE transport server failed to start"
        cat "$temp_dir/sse_test.log"
        return 1
    fi
    
    log_success "Health check completed"
}

# Generate test report
generate_report() {
    log_info "Generating test report..."
    
    local report_file="$TEST_RESULTS_DIR/test_report.md"
    
    cat > "$report_file" << EOF
# MCP Integration Test Report

Generated: $(date)

## Test Environment
- Project Root: $PROJECT_ROOT
- MCP Server Port: $MCP_SERVER_PORT
- AgentUp Server Port: $AGENTUP_SERVER_PORT
- Auth Token: [REDACTED]

## Test Results

EOF
    
    # Add JUnit results if available
    if [[ -f "$TEST_RESULTS_DIR/junit_all.xml" ]]; then
        local total_tests=$(grep -o 'tests="[0-9]*"' "$TEST_RESULTS_DIR/junit_all.xml" | head -1 | grep -o '[0-9]*')
        local failed_tests=$(grep -o 'failures="[0-9]*"' "$TEST_RESULTS_DIR/junit_all.xml" | head -1 | grep -o '[0-9]*')
        local error_tests=$(grep -o 'errors="[0-9]*"' "$TEST_RESULTS_DIR/junit_all.xml" | head -1 | grep -o '[0-9]*')
        
        cat >> "$report_file" << EOF
### Summary
- Total Tests: ${total_tests:-0}
- Failed Tests: ${failed_tests:-0}
- Error Tests: ${error_tests:-0}
- Success Rate: $(( (total_tests - failed_tests - error_tests) * 100 / total_tests ))%

EOF
    fi
    
    # Add log files
    echo "### Log Files" >> "$report_file"
    for log in "$TEST_RESULTS_DIR"/*.log; do
        if [[ -f "$log" ]]; then
            echo "- $(basename "$log")" >> "$report_file"
        fi
    done
    
    log_success "Test report generated: $report_file"
}

# Main function
main() {
    local command="${1:-all}"
    
    case "$command" in
        setup)
            setup
            ;;
        health)
            setup
            health_check
            ;;
        auth)
            setup
            test_authentication
            ;;
        transport)
            local transport="${2:-sse}"
            setup
            test_transport "$transport"
            ;;
        all)
            setup
            health_check
            run_all_tests
            generate_report
            ;;
        clean)
            cleanup
            ;;
        *)
            echo "Usage: $0 {setup|health|auth|transport [sse|streamable_http|stdio]|all|clean}"
            echo ""
            echo "Commands:"
            echo "  setup     - Set up test environment"
            echo "  health    - Run health checks"
            echo "  auth      - Test authentication"
            echo "  transport - Test specific transport type"
            echo "  all       - Run all tests (default)"
            echo "  clean     - Clean up test environment"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"