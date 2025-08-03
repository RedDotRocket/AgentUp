"""Pytest configuration and fixtures for MCP integration tests.

This module provides shared fixtures and configuration for MCP integration
testing including server management, authentication, and test utilities.
"""

import asyncio
import os
import tempfile
from typing import Any

import pytest
import pytest_asyncio

from tests.integration.utils.mcp_test_utils import (
    AgentUpServerManager,
    MCPServerManager,
    generate_mcp_config,
    send_json_rpc_request,
)

# Mark all tests in this module as integration tests
pytest.mark.integration  # noqa: B018


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def temp_config_dir():
    """Create a temporary directory for configuration files."""
    with tempfile.TemporaryDirectory(prefix="mcp_test_configs_") as temp_dir:
        yield temp_dir


@pytest.fixture(params=["sse", "streamable_http", "stdio"])
def transport_type(request):
    """Parametrized fixture for different MCP transport types."""
    return request.param


@pytest.fixture
def auth_token():
    """Authentication token for MCP servers."""
    return "test-token-123"


@pytest.fixture
def invalid_auth_token():
    """Invalid authentication token for testing auth failures."""
    return "wrong-token-456"


@pytest.fixture
def server_port():
    """Port for MCP weather server."""
    return 8123


@pytest.fixture
def agentup_port():
    """Port for AgentUp server."""
    return 8000


@pytest_asyncio.fixture
async def mcp_server(transport_type, server_port, auth_token):
    """Start and manage MCP weather server for testing.

    Args:
        transport_type: MCP transport type
        server_port: Server port
        auth_token: Authentication token

    Yields:
        MCPServerManager instance
    """
    # Only use auth token for HTTP transports
    token = auth_token if transport_type in ["sse", "streamable_http"] else None

    server = MCPServerManager(transport_type, server_port, token)
    server.start()

    try:
        yield server
    finally:
        server.stop()


@pytest_asyncio.fixture
async def agentup_config(transport_type, temp_config_dir, auth_token):
    """Generate AgentUp configuration for testing.

    Args:
        transport_type: MCP transport type
        temp_config_dir: Temporary directory for configs
        auth_token: Authentication token

    Returns:
        Path to the generated configuration file
    """
    config_path = os.path.join(temp_config_dir, f"agentup_{transport_type}.yml")

    # Set environment variable for auth token if needed
    if transport_type in ["sse", "streamable_http"]:
        os.environ["MCP_API_KEY"] = auth_token

    return generate_mcp_config(
        transport=transport_type,
        server_name=transport_type,
        auth_token=auth_token,
        mock_llm=True,
        output_path=config_path,
    )


@pytest_asyncio.fixture
async def agentup_server(agentup_config, agentup_port):
    """Start and manage AgentUp server for testing.

    Args:
        agentup_config: Path to AgentUp configuration file
        agentup_port: Server port

    Yields:
        AgentUpServerManager instance
    """
    server = AgentUpServerManager(agentup_config, agentup_port)
    server.start()

    try:
        yield server
    finally:
        server.stop()


@pytest_asyncio.fixture
async def full_test_setup(mcp_server, agentup_server, agentup_port):
    """Complete test setup with both MCP and AgentUp servers running.

    Args:
        mcp_server: MCP server manager
        agentup_server: AgentUp server manager
        agentup_port: AgentUp server port

    Yields:
        Dictionary with server info and test client
    """
    base_url = f"http://localhost:{agentup_port}"

    yield {"mcp_server": mcp_server, "agentup_server": agentup_server, "base_url": base_url, "api_key": "test-api-key"}


@pytest_asyncio.fixture
async def json_rpc_client(full_test_setup):
    """JSON-RPC client for sending requests to AgentUp server.

    Args:
        full_test_setup: Full test setup with servers

    Returns:
        Function for sending JSON-RPC requests
    """
    setup = full_test_setup

    async def send_request(method: str, params: dict[str, Any], api_key: str | None = None) -> dict[str, Any]:
        return await send_json_rpc_request(
            url=setup["base_url"], method=method, params=params, api_key=api_key or setup["api_key"]
        )

    return send_request


@pytest.fixture
def weather_test_cases():
    """Test cases for weather tool testing."""
    return [
        {
            "name": "forecast_seattle",
            "input": "What's the weather forecast for Seattle?",
            "expected_tool": "get_forecast",
            "expected_location": "Seattle, WA",
        },
        {
            "name": "alerts_california",
            "input": "Are there any weather alerts for CA?",
            "expected_tool": "get_alerts",
            "expected_state": "CA",
        },
        {
            "name": "forecast_coordinates",
            "input": "Get weather for coordinates 40.7, -74.0",
            "expected_tool": "get_forecast",
            "expected_coords": (40.7, -74.0),
        },
        {
            "name": "alerts_texas",
            "input": "Check storm warnings in TX",
            "expected_tool": "get_alerts",
            "expected_state": "TX",
        },
    ]


@pytest.fixture
def auth_test_config(temp_config_dir, invalid_auth_token):
    """Configuration for authentication failure testing.

    Args:
        temp_config_dir: Temporary directory for configs
        invalid_auth_token: Invalid authentication token

    Returns:
        Path to configuration with invalid auth
    """
    config_path = os.path.join(temp_config_dir, "agentup_auth_fail.yml")

    # Set invalid auth token
    os.environ["MCP_API_KEY"] = invalid_auth_token

    return generate_mcp_config(
        transport="sse", server_name="sse_fail", auth_token=invalid_auth_token, mock_llm=True, output_path=config_path
    )


@pytest.fixture(scope="session", autouse=True)
def cleanup_environment():
    """Clean up environment variables after tests."""
    yield

    # Clean up environment variables
    env_vars_to_clean = ["MCP_API_KEY", "AGENT_CONFIG_PATH", "SERVER_PORT"]
    for var in env_vars_to_clean:
        if var in os.environ:
            del os.environ[var]


# Skip markers for different scenarios
def skip_if_no_server(reason="MCP server not available"):
    """Skip test if MCP server is not available."""
    return pytest.mark.skipif(os.environ.get("RUN_MCP_TESTS", "").lower() not in ["1", "true", "yes"], reason=reason)


def skip_transport(transport, reason="Transport not supported"):
    """Skip test for specific transport type."""

    def decorator(func):
        return pytest.mark.skipif(
            lambda request: request.getfixturevalue("transport_type") == transport, reason=reason
        )(func)

    return decorator


# Custom markers for test organization
pytest.mark.mcp_integration = pytest.mark.integration
pytest.mark.mcp_auth = pytest.mark.integration
pytest.mark.mcp_tools = pytest.mark.integration
pytest.mark.mcp_transport = pytest.mark.integration
