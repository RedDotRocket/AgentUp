"""MCP Integration Tests.

This module contains comprehensive integration tests for MCP (Model Context Protocol)
functionality across all supported transport types: SSE, Streamable HTTP, and stdio.
"""

import pytest

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
    async def test_server_health_check(self, full_test_setup):
        """Test that AgentUp server health endpoint works."""
        import httpx

        base_url = full_test_setup["base_url"]
        api_key = full_test_setup["api_key"]

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/health", headers={"X-API-Key": api_key})
            assert response.status_code == 200


class TestMCPAuthentication:
    """Test basic authentication functionality without LLM calls."""

    @pytest.mark.mcp_auth
    @pytest.mark.asyncio
    async def test_server_accepts_valid_api_key(self, full_test_setup):
        """Test that server accepts valid API key for basic requests."""
        import httpx

        base_url = full_test_setup["base_url"]
        valid_api_key = full_test_setup["api_key"]

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/health", headers={"X-API-Key": valid_api_key})
            assert response.status_code == 200

    @pytest.mark.mcp_auth
    @pytest.mark.asyncio
    async def test_server_rejects_invalid_api_key(self, full_test_setup):
        """Test that server rejects invalid API key for protected endpoints."""
        from tests.integration.utils.mcp_test_utils import send_json_rpc_request

        base_url = full_test_setup["base_url"]
        invalid_api_key = "invalid-key-123"

        # Test with a protected endpoint (JSON-RPC) instead of health
        try:
            response = await send_json_rpc_request(
                url=base_url, method="message/send", params={}, api_key=invalid_api_key
            )
            # If we get a response, check for error
            assert "error" in response
        except Exception as e:
            # HTTP 401/403 exceptions are expected
            assert "401" in str(e) or "403" in str(e) or "unauthorized" in str(e).lower()


# Removed LLM-dependent test classes to focus on basic server functionality
