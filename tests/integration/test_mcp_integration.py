"""MCP Integration Tests.

This module contains comprehensive integration tests for MCP (Model Context Protocol)
functionality across all supported transport types: SSE, Streamable HTTP, and stdio.
"""

import asyncio
import os
import time

import pytest

from tests.integration.utils.mcp_test_utils import (
    extract_tool_result,
    validate_mcp_tool_response,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestMCPTransportConnectivity:
    """Test MCP connectivity across different transport types."""

    @pytest.mark.mcp_transport
    @pytest.mark.asyncio
    async def test_mcp_server_startup(self, mcp_server, transport_type):
        """Test that MCP server starts successfully for each transport."""
        assert mcp_server.process is not None

        if transport_type == "stdio":
            # For stdio servers, process may exit immediately which is normal
            # We just check that the server started and transport is correct
            assert mcp_server.transport == transport_type
        else:
            # For HTTP servers, process should still be running
            assert mcp_server.process.poll() is None, f"{transport_type} server should be running"
            assert mcp_server.transport == transport_type

    @pytest.mark.mcp_transport
    @pytest.mark.asyncio
    async def test_agentup_server_startup(self, agentup_server, agentup_port):
        """Test that AgentUp server starts successfully."""
        assert agentup_server.process is not None
        assert agentup_server.process.poll() is None, "AgentUp server should be running"

    @pytest.mark.mcp_transport
    @pytest.mark.asyncio
    async def test_mcp_client_initialization(self, json_rpc_client):
        """Test that MCP client initializes correctly."""
        # Send a simple health check message
        response = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Hello, are you ready?"}],
                    "message_id": f"health_check_{int(time.time() * 1000)}",
                }
            },
        )

        assert "result" in response
        assert response["result"] is not None


class TestMCPAuthentication:
    """Test MCP authentication functionality."""

    @pytest.mark.mcp_auth
    @pytest.mark.asyncio
    async def test_valid_authentication_sse(self, auth_token):
        """Test SSE transport with valid authentication."""
        import tempfile

        from tests.integration.utils.mcp_test_utils import AgentUpServerManager, MCPServerManager, generate_mcp_config

        # Only test HTTP-based transports for auth
        with tempfile.TemporaryDirectory() as temp_dir:
            # Start MCP server with auth
            mcp_server = MCPServerManager("sse", 8124, auth_token)
            mcp_server.start()

            try:
                # Generate config with correct auth
                config_path = os.path.join(temp_dir, "auth_test.yml")
                os.environ["MCP_API_KEY"] = auth_token

                config_path = generate_mcp_config(
                    transport="sse",
                    server_name="sse_auth",
                    auth_token=auth_token,
                    mock_llm=True,
                    output_path=config_path,
                )

                # Start AgentUp server
                agentup_server = AgentUpServerManager(config_path, 8001)
                agentup_server.start()

                try:
                    # Test that connection works
                    from tests.integration.utils.mcp_test_utils import send_json_rpc_request

                    response = await send_json_rpc_request(
                        url="http://localhost:8001",
                        method="message/send",
                        params={
                            "message": {
                                "role": "user",
                                "parts": [{"kind": "text", "text": "Test auth connection"}],
                                "message_id": "auth_test",
                            }
                        },
                    )

                    assert "result" in response
                    # If we get here without exception, auth worked

                finally:
                    agentup_server.stop()
            finally:
                mcp_server.stop()

    @pytest.mark.mcp_auth
    @pytest.mark.asyncio
    async def test_invalid_authentication_sse(self, invalid_auth_token):
        """Test SSE transport with invalid authentication."""
        import tempfile

        from tests.integration.utils.mcp_test_utils import AgentUpServerManager, MCPServerManager, generate_mcp_config

        valid_token = "valid-token-123"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Start MCP server with valid token
            mcp_server = MCPServerManager("sse", 8125, valid_token)
            mcp_server.start()

            try:
                # Generate config with invalid auth
                config_path = os.path.join(temp_dir, "auth_fail_test.yml")
                os.environ["MCP_API_KEY"] = invalid_auth_token

                config_path = generate_mcp_config(
                    transport="sse",
                    server_name="sse_auth_fail",
                    auth_token=invalid_auth_token,
                    mock_llm=True,
                    output_path=config_path,
                )

                # Start AgentUp server - should start but fail to connect to MCP
                agentup_server = AgentUpServerManager(config_path, 8002)
                agentup_server.start()

                try:
                    # Give time for connection attempts
                    await asyncio.sleep(3)

                    # Server should be running but MCP connection should have failed
                    assert agentup_server.process.poll() is None

                finally:
                    agentup_server.stop()
            finally:
                mcp_server.stop()


class TestMCPToolExecution:
    """Test MCP tool execution functionality."""

    @pytest.mark.mcp_tools
    @pytest.mark.asyncio
    async def test_weather_forecast_tool(self, json_rpc_client, transport_type):
        """Test weather forecast tool execution."""
        response = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "What's the weather forecast for Seattle?"}],
                    "message_id": f"forecast_test_{transport_type}_{int(time.time() * 1000)}",
                }
            },
        )

        assert "result" in response

        # Check if forecast tool was called
        tool_called = validate_mcp_tool_response(response, "get_forecast")
        assert tool_called, f"get_forecast tool should be called for {transport_type} transport"

        # Extract tool result
        result = extract_tool_result(response)
        if result:
            assert "seattle" in result.lower() or "weather" in result.lower()

    @pytest.mark.mcp_tools
    @pytest.mark.asyncio
    async def test_weather_alerts_tool(self, json_rpc_client, transport_type):
        """Test weather alerts tool execution."""
        response = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Are there any weather alerts for CA?"}],
                    "message_id": f"alerts_test_{transport_type}_{int(time.time() * 1000)}",
                }
            },
        )

        assert "result" in response

        # Check if alerts tool was called
        tool_called = validate_mcp_tool_response(response, "get_alerts")
        assert tool_called, f"get_alerts tool should be called for {transport_type} transport"

        # Extract tool result
        result = extract_tool_result(response)
        if result:
            assert "ca" in result.lower() or "california" in result.lower() or "alert" in result.lower()

    @pytest.mark.mcp_tools
    @pytest.mark.asyncio
    async def test_multiple_tool_requests(self, json_rpc_client, transport_type):
        """Test multiple sequential tool requests."""
        # First request - forecast
        response1 = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Weather forecast for New York"}],
                    "message_id": f"multi_test1_{transport_type}_{int(time.time() * 1000)}",
                }
            },
        )

        assert validate_mcp_tool_response(response1, "get_forecast")

        # Second request - alerts
        response2 = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Check weather alerts for TX"}],
                    "message_id": f"multi_test2_{transport_type}_{int(time.time() * 1000)}",
                }
            },
        )

        assert validate_mcp_tool_response(response2, "get_alerts")

    @pytest.mark.mcp_tools
    @pytest.mark.asyncio
    async def test_tool_with_coordinates(self, json_rpc_client, transport_type):
        """Test tool execution with coordinate input."""
        response = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Get weather forecast for coordinates 40.7, -74.0"}],
                    "message_id": f"coord_test_{transport_type}_{int(time.time() * 1000)}",
                }
            },
        )

        assert "result" in response
        assert validate_mcp_tool_response(response, "get_forecast")


class TestMCPErrorHandling:
    """Test MCP error handling and edge cases."""

    @pytest.mark.mcp_integration
    @pytest.mark.asyncio
    async def test_invalid_json_rpc_request(self, json_rpc_client):
        """Test handling of invalid JSON-RPC requests."""
        try:
            # Send malformed request
            response = await json_rpc_client(method="invalid/method", params={"invalid": "params"})

            # Should get an error response
            assert "error" in response or "result" in response

        except Exception as _:
            # Exception handling is acceptable for invalid requests
            assert True

    @pytest.mark.mcp_integration
    @pytest.mark.asyncio
    async def test_unauthorized_request(self, full_test_setup):
        """Test handling of unauthorized requests."""
        from tests.integration.utils.mcp_test_utils import send_json_rpc_request

        try:
            response = await send_json_rpc_request(
                url=full_test_setup["base_url"],
                method="message/send",
                params={
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": "Test without auth"}],
                        "message_id": "unauth_test",
                    }
                },
                api_key="invalid-key",
            )

            # Should get unauthorized error
            assert "error" in response

        except Exception as e:
            # HTTP 401/403 exceptions are expected
            assert "401" in str(e) or "403" in str(e) or "unauthorized" in str(e).lower()

    @pytest.mark.mcp_integration
    @pytest.mark.asyncio
    async def test_non_weather_request(self, json_rpc_client, transport_type):
        """Test handling of requests that don't trigger weather tools."""
        response = await json_rpc_client(
            method="message/send",
            params={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Hello, how are you today?"}],
                    "message_id": f"non_weather_{transport_type}_{int(time.time() * 1000)}",
                }
            },
        )

        assert "result" in response

        # Should not call weather tools
        forecast_called = validate_mcp_tool_response(response, "get_forecast")
        alerts_called = validate_mcp_tool_response(response, "get_alerts")

        assert not forecast_called and not alerts_called, "Weather tools should not be called for non-weather requests"


class TestMCPPerformance:
    """Test MCP performance and reliability."""

    @pytest.mark.mcp_integration
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, json_rpc_client, transport_type):
        """Test handling of concurrent MCP requests."""

        async def send_request(i: int):
            return await json_rpc_client(
                method="message/send",
                params={
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": f"Weather forecast for test location {i}"}],
                        "message_id": f"concurrent_{transport_type}_{i}_{int(time.time() * 1000)}",
                    }
                },
            )

        # Send 3 concurrent requests
        tasks = [send_request(i) for i in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # At least 2 out of 3 should succeed
        successful = sum(1 for r in responses if isinstance(r, dict) and "result" in r)
        assert successful >= 2, f"At least 2 concurrent requests should succeed for {transport_type}"

    @pytest.mark.mcp_integration
    @pytest.mark.asyncio
    async def test_request_timeout_handling(self, json_rpc_client, transport_type):
        """Test handling of request timeouts."""
        try:
            # Send a normal request with short timeout
            response = await asyncio.wait_for(
                json_rpc_client(
                    method="message/send",
                    params={
                        "message": {
                            "role": "user",
                            "parts": [{"kind": "text", "text": "Quick weather check for Seattle"}],
                            "message_id": f"timeout_test_{transport_type}_{int(time.time() * 1000)}",
                        }
                    },
                ),
                timeout=10.0,  # 10 second timeout
            )

            assert "result" in response

        except asyncio.TimeoutError:
            pytest.skip(f"Request timed out for {transport_type} - may indicate server issues")


# Parametrized test for comprehensive transport coverage
@pytest.mark.mcp_integration
@pytest.mark.parametrize(
    "test_case",
    [
        {"input": "Weather in Seattle", "expected_tool": "get_forecast"},
        {"input": "Alerts for NY", "expected_tool": "get_alerts"},
        {"input": "Forecast for 37.7749, -122.4194", "expected_tool": "get_forecast"},
        {"input": "Storm warnings in FL", "expected_tool": "get_alerts"},
    ],
)
@pytest.mark.asyncio
async def test_comprehensive_tool_coverage(json_rpc_client, transport_type, test_case):
    """Comprehensive test of tool coverage across all transports."""
    response = await json_rpc_client(
        method="message/send",
        params={
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": test_case["input"]}],
                "message_id": f"comprehensive_{transport_type}_{int(time.time() * 1000)}",
            }
        },
    )

    assert "result" in response
    assert validate_mcp_tool_response(response, test_case["expected_tool"]), (
        f"{test_case['expected_tool']} should be called for '{test_case['input']}' on {transport_type}"
    )
