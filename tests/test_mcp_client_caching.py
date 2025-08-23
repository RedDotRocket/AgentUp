"""Test MCP client function call caching functionality."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from src.agent.mcp_support.mcp_client import MCPClientService


class TestMCPClientCaching:
    """Test MCP client function call caching."""

    def test_generate_cache_key(self):
        """Test cache key generation is deterministic."""
        client = MCPClientService("test", {})

        # Same tool and args should produce same key
        key1 = client._generate_cache_key("get_weather", {"city": "London", "country": "UK"})
        key2 = client._generate_cache_key("get_weather", {"city": "London", "country": "UK"})
        assert key1 == key2

        # Different order of args should produce same key (due to sorting)
        key3 = client._generate_cache_key("get_weather", {"country": "UK", "city": "London"})
        assert key1 == key3

        # Different args should produce different key
        key4 = client._generate_cache_key("get_weather", {"city": "Paris", "country": "France"})
        assert key1 != key4

        # Different tool should produce different key
        key5 = client._generate_cache_key("get_forecast", {"city": "London", "country": "UK"})
        assert key1 != key5

    def test_cleanup_expired_cache(self):
        """Test expired cache entries are cleaned up."""
        client = MCPClientService("test", {})
        current_time = time.time()

        # Add some cache entries with different ages
        client._function_call_cache = {
            "key1": ("result1", current_time - 30),  # 30 seconds old
            "key2": ("result2", current_time - 70),  # 70 seconds old (expired)
            "key3": ("result3", current_time - 10),  # 10 seconds old
        }

        # Clean up expired entries (TTL is 60 seconds)
        client._cleanup_expired_cache()

        # Only key2 should be removed
        assert "key1" in client._function_call_cache
        assert "key2" not in client._function_call_cache
        assert "key3" in client._function_call_cache

    @pytest.mark.asyncio
    async def test_call_tool_caching_hit(self):
        """Test that cached results are returned without making actual calls."""
        client = MCPClientService("test", {})

        # Setup mock server and tools
        client._available_tools = {
            "get_weather": {
                "server": "test_server",
                "name": "get_weather",
                "description": "Get weather",
                "inputSchema": {},
            }
        }
        client._servers = {
            "test_server": {
                "config": {"transport": "stdio", "command": "test"},
                "transport": "stdio",
                "connected": True,
            }
        }

        # Pre-populate cache
        cache_key = client._generate_cache_key("get_weather", {"city": "London"})
        client._function_call_cache[cache_key] = ("Sunny, 22°C", time.time())

        # Mock the transport creation to ensure it's not called
        with patch.object(client, "_create_transport_client") as mock_transport:
            result = await client.call_tool("get_weather", {"city": "London"})

            # Should return cached result without calling transport
            assert result == "Sunny, 22°C"
            mock_transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_call_tool_caching_miss(self):
        """Test that uncached calls make actual requests and cache the result."""
        client = MCPClientService("test", {})

        # Setup mock server and tools
        client._available_tools = {
            "get_weather": {
                "server": "test_server",
                "name": "get_weather",
                "description": "Get weather",
                "inputSchema": {},
            }
        }
        client._servers = {
            "test_server": {
                "config": {"transport": "stdio", "command": "test"},
                "transport": "stdio",
                "connected": True,
            }
        }

        # Mock the transport and session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_content = TextContent(type="text", text="Sunny, 22°C")
        mock_result.content = [mock_content]
        mock_session.call_tool.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = (MagicMock(), MagicMock())

        with patch.object(client, "_create_transport_client", return_value=mock_context):
            with patch("src.agent.mcp_support.mcp_client.ClientSession") as mock_session_class:
                mock_session_class.return_value.__aenter__.return_value = mock_session
                result = await client.call_tool("get_weather", {"city": "London"})

                # Should return processed result
                assert result == "Sunny, 22°C"

                # Should have cached the result
                cache_key = client._generate_cache_key("get_weather", {"city": "London"})
                assert cache_key in client._function_call_cache
                cached_result, cached_time = client._function_call_cache[cache_key]
                assert cached_result == "Sunny, 22°C"
                assert cached_time > 0

    @pytest.mark.asyncio
    async def test_call_tool_expired_cache(self):
        """Test that expired cache entries are ignored and refreshed."""
        client = MCPClientService("test", {})

        # Setup mock server and tools
        client._available_tools = {
            "get_weather": {
                "server": "test_server",
                "name": "get_weather",
                "description": "Get weather",
                "inputSchema": {},
            }
        }
        client._servers = {
            "test_server": {
                "config": {"transport": "stdio", "command": "test"},
                "transport": "stdio",
                "connected": True,
            }
        }

        # Pre-populate cache with expired entry
        cache_key = client._generate_cache_key("get_weather", {"city": "London"})
        client._function_call_cache[cache_key] = ("Old weather", time.time() - 70)  # Expired

        # Mock the transport and session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_content = TextContent(type="text", text="New weather, 25°C")
        mock_result.content = [mock_content]
        mock_session.call_tool.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = (MagicMock(), MagicMock())

        with patch.object(client, "_create_transport_client", return_value=mock_context):
            with patch("src.agent.mcp_support.mcp_client.ClientSession") as mock_session_class:
                mock_session_class.return_value.__aenter__.return_value = mock_session
                result = await client.call_tool("get_weather", {"city": "London"})

                # Should return new result, not cached
                assert result == "New weather, 25°C"

                # Cache should be updated with new result
                cached_result, cached_time = client._function_call_cache[cache_key]
                assert cached_result == "New weather, 25°C"
                assert cached_time > time.time() - 5  # Recent timestamp

    @pytest.mark.asyncio
    async def test_close_clears_cache(self):
        """Test that close() clears the function call cache."""
        client = MCPClientService("test", {})

        # Add some cache entries
        client._function_call_cache = {"key1": ("result1", time.time()), "key2": ("result2", time.time())}

        # Close should clear cache
        await client.close()

        assert len(client._function_call_cache) == 0
