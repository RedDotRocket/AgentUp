"""Tests for AgentUpTool."""

from unittest.mock import AsyncMock, patch

import pytest

from agent.integrations.crewai.agentup_tool import (
    AgentUpTool,
    create_agentup_tools,
    query_agentup_agent,
)


class TestAgentUpTool:
    """Test cases for AgentUpTool."""

    @pytest.fixture
    def tool(self):
        """Create a test tool."""
        return AgentUpTool(
            base_url="http://test:8000", api_key="test-key", agent_name="Test Agent", timeout=10, max_retries=2
        )

    @pytest.fixture
    def mock_a2a_client(self):
        """Create a mock A2A client."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        return mock_client

    def test_tool_initialization(self, tool):
        """Test tool initialization."""
        assert tool.config.base_url == "http://test:8000"
        assert tool.config.api_key == "test-key"
        assert tool.config.timeout == 10
        assert tool.config.max_retries == 2
        assert tool.agent_name == "Test Agent"
        assert "Test Agent" in tool.name

    def test_tool_initialization_with_defaults(self):
        """Test tool initialization with default values."""
        tool = AgentUpTool()

        assert tool.config.base_url == "http://localhost:8000"
        assert tool.config.api_key is None
        assert tool.config.timeout == 30
        assert tool.config.max_retries == 3
        assert tool.agent_name == "AgentUp Agent"

    def test_run_synchronous(self, tool):
        """Test synchronous _run method."""

        # Mock the entire _arun method instead of trying to mock the internals
        async def mock_arun(query, context_id=None):
            return "Test response"

        tool._arun = mock_arun

        # Test
        result = tool._run("Test query")

        # Verify
        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_arun_asynchronous(self, tool):
        """Test asynchronous _arun method."""
        # Mock the A2AClient to avoid actual HTTP calls
        with patch("agent.integrations.crewai.agentup_tool.A2AClient") as mock_a2a_class:
            # Create a mock A2A client
            mock_client = AsyncMock()
            mock_a2a_class.return_value.__aenter__.return_value = mock_client
            mock_a2a_class.return_value.__aexit__.return_value = AsyncMock()

            # Mock the send_message method properly with async return
            mock_response = {"message": {"role": "assistant", "parts": [{"kind": "text", "text": "Async response"}]}}

            # Create proper mock functions for both methods
            async def mock_send_message(*args, **kwargs):
                return mock_response

            def mock_extract_text(response):
                return "Async response"

            mock_client.send_message = mock_send_message
            mock_client.extract_text_from_response = mock_extract_text

            result = await tool._arun("Async query", context_id="test-context")

            # Verify
            assert result == "Async response"

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_arun_with_error(self, mock_a2a_client_class, tool):
        """Test _arun method with error handling."""
        # Setup mock to raise exception
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        mock_client.send_message.side_effect = Exception("Connection error")

        # Test
        result = await tool._arun("Test query")

        # Verify error is handled gracefully
        assert "Error communicating with Test Agent" in result
        assert "Connection error" in result

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_arun_empty_response(self, mock_a2a_client_class, tool):
        """Test _arun method with empty response."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = AsyncMock()

        # Create proper mock functions for both methods
        async def mock_send_message(*args, **kwargs):
            return {}

        def mock_extract_text(response):
            return ""

        mock_client.send_message = mock_send_message
        mock_client.extract_text_from_response = mock_extract_text

        # Test
        result = await tool._arun("Test query")

        # Verify default message is returned
        assert "Test Agent processed the request but returned no text response" in result

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_stream_response(self, mock_a2a_client_class, tool):
        """Test streaming response functionality."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        # Create proper async generator function
        async def mock_stream(*args, **kwargs):
            yield {"text": "chunk1"}
            yield {"text": "chunk2"}
            yield {"text": "chunk3"}

        # Assign the async generator function directly
        mock_client.stream_message = mock_stream

        # Test
        chunks = []
        async for chunk in tool.stream_response("Stream query"):
            chunks.append(chunk)

        # Verify
        assert len(chunks) == 3
        assert chunks[0] == {"text": "chunk1"}
        assert chunks[1] == {"text": "chunk2"}
        assert chunks[2] == {"text": "chunk3"}

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_stream_response_with_error(self, mock_a2a_client_class, tool):
        """Test streaming response with error."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        # Create proper async generator that raises exception
        async def mock_stream(*args, **kwargs):
            yield {"text": "chunk1"}
            raise Exception("Stream error")

        # Assign the async generator function directly
        mock_client.stream_message = mock_stream

        # Test
        chunks = []
        async for chunk in tool.stream_response("Stream query"):
            chunks.append(chunk)

        # Verify error chunk is yielded
        assert len(chunks) == 2
        assert chunks[0] == {"text": "chunk1"}
        assert "error" in chunks[1]
        assert "Stream error" in chunks[1]["error"]

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_get_capabilities(self, mock_a2a_client_class, tool):
        """Test getting agent capabilities."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        mock_agent_card = {"capabilities": {"streaming": True, "push_notifications": False}}
        mock_client.get_agent_card.return_value = mock_agent_card

        # Test
        capabilities = await tool.get_capabilities()

        # Verify
        assert capabilities == mock_agent_card["capabilities"]
        mock_client.get_agent_card.assert_called_once()

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_get_capabilities_with_error(self, mock_a2a_client_class, tool):
        """Test getting capabilities with error."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        mock_client.get_agent_card.side_effect = Exception("Network error")

        # Test
        capabilities = await tool.get_capabilities()

        # Verify empty dict is returned on error
        assert capabilities == {}

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    def test_health_check_success(self, mock_a2a_client_class, tool):
        """Test successful health check."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        mock_client.get_agent_card.return_value = {"name": "Test Agent"}

        # Test
        is_healthy = tool.health_check()

        # Verify
        assert is_healthy is True
        mock_client.get_agent_card.assert_called_once()

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    def test_health_check_failure(self, mock_a2a_client_class, tool):
        """Test health check failure."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        mock_client.get_agent_card.side_effect = Exception("Connection failed")

        # Test
        is_healthy = tool.health_check()

        # Verify
        assert is_healthy is False


class TestStandaloneFunctions:
    """Test standalone functions."""

    @patch("agent.integrations.crewai.agentup_tool.A2AClient")
    @pytest.mark.asyncio
    async def test_query_agentup_agent(self, mock_a2a_client_class):
        """Test standalone query function."""
        # Setup mock
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value.__aenter__.return_value = mock_client
        mock_a2a_client_class.return_value.__aexit__.return_value = None

        # Create proper mock functions for both methods
        async def mock_send_message(*args, **kwargs):
            return {"result": "test"}

        def mock_extract_text(response):
            return "Test response"

        mock_client.send_message = mock_send_message
        mock_client.extract_text_from_response = mock_extract_text

        # Test
        result = await query_agentup_agent(
            query="Test query", base_url="http://test:8000", api_key="test-key", context_id="test-context"
        )

        # Verify
        assert result == "Test response"
        mock_a2a_client_class.assert_called_once_with(base_url="http://test:8000", api_key="test-key")

    def test_create_agentup_tools(self):
        """Test factory function for creating multiple tools."""
        agents = [
            {"name": "Agent 1", "base_url": "http://agent1:8000", "api_key": "key1", "description": "First agent"},
            {
                "name": "Agent 2",
                "base_url": "http://agent2:8000",
                "description": "Second agent",
                # No api_key provided
            },
        ]

        tools = create_agentup_tools(agents)

        # Verify correct number of tools created
        assert len(tools) == 2

        # Verify first tool
        tool1 = tools[0]
        assert tool1.config.base_url == "http://agent1:8000"
        assert tool1.config.api_key == "key1"
        assert tool1.agent_name == "Agent 1"
        assert "Agent 1" in tool1.name

        # Verify second tool
        tool2 = tools[1]
        assert tool2.config.base_url == "http://agent2:8000"
        assert tool2.config.api_key is None
        assert tool2.agent_name == "Agent 2"
        assert "Agent 2" in tool2.name

    def test_create_agentup_tools_empty_list(self):
        """Test factory function with empty list."""
        tools = create_agentup_tools([])
        assert len(tools) == 0


@pytest.mark.integration
class TestAgentUpToolIntegration:
    """Integration tests for AgentUpTool (require running AgentUp agent)."""

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    def test_real_tool_health_check(self):
        """Test health check against real AgentUp agent."""
        tool = AgentUpTool(base_url="http://localhost:8000")

        try:
            is_healthy = tool.health_check()
            assert isinstance(is_healthy, bool)
        except Exception as e:
            pytest.skip(f"No AgentUp agent running: {e}")

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    def test_real_tool_run(self):
        """Test _run method against real AgentUp agent."""
        tool = AgentUpTool(base_url="http://localhost:8000", api_key="test-key")

        try:
            result = tool._run("Hello, can you help me?")
            assert isinstance(result, str)
            assert len(result) > 0
        except Exception as e:
            pytest.skip(f"No AgentUp agent running or authentication failed: {e}")

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    @pytest.mark.asyncio
    async def test_real_tool_capabilities(self):
        """Test getting capabilities from real AgentUp agent."""
        tool = AgentUpTool(base_url="http://localhost:8000")

        try:
            capabilities = await tool.get_capabilities()
            assert isinstance(capabilities, dict)
        except Exception as e:
            pytest.skip(f"No AgentUp agent running: {e}")


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "asyncio: marks tests as async tests")
