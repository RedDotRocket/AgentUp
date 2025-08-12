"""Tests for AgentUp discovery functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.integrations.crewai.discovery import (
    AgentUpDiscovery,
    discover_and_filter_tools,
    discover_local_agents,
)


class TestAgentUpDiscovery:
    """Test cases for AgentUpDiscovery."""

    @pytest.fixture
    def discovery(self):
        """Create a test discovery instance."""
        return AgentUpDiscovery(base_urls=["http://agent1:8000", "http://agent2:8001"], api_key="test-key", timeout=10)

    @pytest.fixture
    def mock_agent_card(self):
        """Create a mock agent card."""
        return {
            "name": "Test Agent",
            "description": "Test agent description",
            "version": "1.0.0",
            "capabilities": {"streaming": True, "push_notifications": False},
            "skills": [
                {
                    "id": "skill1",
                    "name": "Research Skill",
                    "description": "Research and analysis",
                    "inputModes": ["text"],
                    "outputModes": ["text"],
                    "tags": ["research", "analysis"],
                },
                {
                    "id": "skill2",
                    "name": "Writing Skill",
                    "description": "Content creation",
                    "inputModes": ["text"],
                    "outputModes": ["text"],
                    "tags": ["writing", "content"],
                },
            ],
            "securitySchemes": {},
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }

    @pytest.mark.asyncio
    async def test_discover_agents_success(self, discovery, mock_agent_card):
        """Test successful agent discovery."""
        with patch("agent.integrations.crewai.discovery.A2AClient") as mock_client_class:
            # Setup mocks for both agents
            mock_client1 = AsyncMock()
            mock_client2 = AsyncMock()

            # Configure mock clients
            mock_client_class.side_effect = [mock_client1, mock_client2]

            mock_agent_card1 = {**mock_agent_card, "name": "Agent 1"}
            mock_agent_card2 = {**mock_agent_card, "name": "Agent 2"}

            mock_client1.__aenter__.return_value = mock_client1
            mock_client1.__aexit__.return_value = None
            mock_client1.get_agent_card.return_value = mock_agent_card1

            mock_client2.__aenter__.return_value = mock_client2
            mock_client2.__aexit__.return_value = None
            mock_client2.get_agent_card.return_value = mock_agent_card2

            # Test
            agents = await discovery.discover_agents()

            # Verify
            assert len(agents) == 2

            agent1 = agents[0]
            assert agent1["name"] == "Agent 1"
            assert agent1["base_url"] == "http://agent1:8000"
            assert len(agent1["skills"]) == 2

            agent2 = agents[1]
            assert agent2["name"] == "Agent 2"
            assert agent2["base_url"] == "http://agent2:8001"

    @pytest.mark.asyncio
    async def test_discover_agents_with_failure(self, discovery, mock_agent_card):
        """Test agent discovery with one agent failing."""
        with patch("agent.integrations.crewai.discovery.A2AClient") as mock_client_class:
            # Setup mocks - first agent fails, second succeeds
            mock_client1 = AsyncMock()
            mock_client2 = AsyncMock()

            mock_client_class.side_effect = [mock_client1, mock_client2]

            # First client fails
            mock_client1.__aenter__.return_value = mock_client1
            mock_client1.__aexit__.return_value = None
            mock_client1.get_agent_card.side_effect = Exception("Connection failed")

            # Second client succeeds
            mock_client2.__aenter__.return_value = mock_client2
            mock_client2.__aexit__.return_value = None
            mock_client2.get_agent_card.return_value = mock_agent_card

            # Test
            agents = await discovery.discover_agents()

            # Verify - only one agent discovered
            assert len(agents) == 1
            assert agents[0]["name"] == "Test Agent"
            assert agents[0]["base_url"] == "http://agent2:8001"

    @pytest.mark.asyncio
    async def test_create_tools_from_agents(self, discovery, mock_agent_card):
        """Test creating tools from discovered agents."""
        # Mock discovery.discover_agents
        with patch.object(discovery, "discover_agents") as mock_discover:
            mock_discover.return_value = [
                {"name": "Agent 1", "description": "First agent", "base_url": "http://agent1:8000"},
                {"name": "Agent 2", "description": "Second agent", "base_url": "http://agent2:8001"},
            ]

            # Mock AgentUpTool creation
            with patch("agent.integrations.crewai.discovery.AgentUpTool") as mock_tool_class:
                mock_tool1 = MagicMock()
                mock_tool2 = MagicMock()
                mock_tool_class.side_effect = [mock_tool1, mock_tool2]

                # Test
                tools = await discovery.create_tools_from_agents()

                # Verify
                assert len(tools) == 2
                assert tools[0] == mock_tool1
                assert tools[1] == mock_tool2

                # Verify tool creation calls
                assert mock_tool_class.call_count == 2

                call1 = mock_tool_class.call_args_list[0]
                assert call1[1]["base_url"] == "http://agent1:8000"
                assert call1[1]["agent_name"] == "Agent 1"

                call2 = mock_tool_class.call_args_list[1]
                assert call2[1]["base_url"] == "http://agent2:8001"
                assert call2[1]["agent_name"] == "Agent 2"

    @pytest.mark.asyncio
    async def test_create_skill_specific_tools(self, discovery, mock_agent_card):
        """Test creating skill-specific tools."""
        with patch.object(discovery, "discover_agents") as mock_discover:
            mock_discover.return_value = [
                {
                    "name": "Test Agent",
                    "base_url": "http://test:8000",
                    "skills": [
                        {
                            "id": "research",
                            "name": "Research Skill",
                            "description": "Research capability",
                            "inputModes": ["text"],
                            "outputModes": ["text"],
                            "tags": ["research"],
                        },
                        {
                            "id": "writing",
                            "name": "Writing Skill",
                            "description": "Writing capability",
                            "inputModes": ["text"],
                            "outputModes": ["text"],
                            "tags": ["writing"],
                        },
                    ],
                }
            ]

            # Mock AgentUpTool creation
            with patch("agent.integrations.crewai.discovery.AgentUpTool") as mock_tool_class:
                mock_tool1 = MagicMock()
                mock_tool2 = MagicMock()
                mock_tool_class.side_effect = [mock_tool1, mock_tool2]

                # Test
                tools = await discovery.create_skill_specific_tools()

                # Verify
                assert len(tools) == 2

                # Check that tools have skill-specific attributes
                assert hasattr(mock_tool1, "skill_id")
                assert hasattr(mock_tool1, "skill_tags")
                assert hasattr(mock_tool2, "skill_id")
                assert hasattr(mock_tool2, "skill_tags")

    @pytest.mark.asyncio
    async def test_get_agent_health_status(self, discovery):
        """Test getting health status of agents."""
        with patch("agent.integrations.crewai.discovery.A2AClient") as mock_client_class:
            # Setup mocks
            mock_client1 = AsyncMock()
            mock_client2 = AsyncMock()

            mock_client_class.side_effect = [mock_client1, mock_client2]

            # First agent healthy
            mock_client1.__aenter__.return_value = mock_client1
            mock_client1.__aexit__.return_value = None
            mock_client1.get_agent_card.return_value = {"name": "Agent 1"}

            # Second agent unhealthy
            mock_client2.__aenter__.return_value = mock_client2
            mock_client2.__aexit__.return_value = None
            mock_client2.get_agent_card.side_effect = Exception("Connection failed")

            # Test
            health_status = await discovery.get_agent_health_status()

            # Verify
            assert len(health_status) == 2
            assert health_status["http://agent1:8000"] is True
            assert health_status["http://agent2:8001"] is False

    @pytest.mark.asyncio
    async def test_find_agents_by_capability(self, discovery):
        """Test finding agents by capability."""
        with patch.object(discovery, "discover_agents") as mock_discover:
            mock_discover.return_value = [
                {
                    "name": "Research Agent",
                    "skills": [
                        {
                            "name": "data analysis",
                            "description": "analyze research data",
                            "tags": ["research", "analysis"],
                        }
                    ],
                },
                {
                    "name": "Writing Agent",
                    "skills": [
                        {
                            "name": "content creation",
                            "description": "create written content",
                            "tags": ["writing", "content"],
                        }
                    ],
                },
                {
                    "name": "Multi Agent",
                    "skills": [
                        {"name": "research skill", "description": "research capability", "tags": ["research"]},
                        {"name": "analysis tool", "description": "data analysis tools", "tags": ["analysis"]},
                    ],
                },
            ]

            # Test finding by tag
            research_agents = await discovery.find_agents_by_capability("research")
            assert len(research_agents) == 2
            assert research_agents[0]["name"] == "Research Agent"
            assert research_agents[1]["name"] == "Multi Agent"

            # Test finding by name
            analysis_agents = await discovery.find_agents_by_capability("analysis")
            assert len(analysis_agents) == 2

            # Test finding by description
            content_agents = await discovery.find_agents_by_capability("content")
            assert len(content_agents) == 1
            assert content_agents[0]["name"] == "Writing Agent"

    def test_init_with_single_url(self):
        """Test initialization with single URL."""
        discovery = AgentUpDiscovery("http://single:8000")
        assert discovery.base_urls == ["http://single:8000"]

    def test_init_with_multiple_urls(self):
        """Test initialization with multiple URLs."""
        urls = ["http://agent1:8000", "http://agent2:8001"]
        discovery = AgentUpDiscovery(urls)
        assert discovery.base_urls == urls


class TestDiscoveryUtilityFunctions:
    """Test utility functions for discovery."""

    @pytest.mark.asyncio
    async def test_discover_local_agents(self):
        """Test discovering local agents."""
        with patch("agent.integrations.crewai.discovery.AgentUpDiscovery") as mock_discovery_class:
            mock_discovery = AsyncMock()
            mock_discovery_class.return_value = mock_discovery

            mock_tools = [MagicMock(), MagicMock()]
            mock_discovery.create_tools_from_agents.return_value = mock_tools

            # Test with default ports
            tools = await discover_local_agents()

            # Verify discovery was called with default ports
            mock_discovery_class.assert_called_once()
            call_args = mock_discovery_class.call_args
            base_urls = call_args[1]["base_urls"]
            assert "http://localhost:8000" in base_urls
            assert "http://localhost:8001" in base_urls

            assert tools == mock_tools

    @pytest.mark.asyncio
    async def test_discover_local_agents_custom_ports(self):
        """Test discovering local agents with custom ports."""
        with patch("agent.integrations.crewai.discovery.AgentUpDiscovery") as mock_discovery_class:
            mock_discovery = AsyncMock()
            mock_discovery_class.return_value = mock_discovery

            mock_tools = [MagicMock()]
            mock_discovery.create_tools_from_agents.return_value = mock_tools

            # Test with custom ports
            await discover_local_agents(ports=[9000, 9001], api_key="test-key")

            # Verify
            call_args = mock_discovery_class.call_args
            base_urls = call_args[1]["base_urls"]
            assert base_urls == ["http://localhost:9000", "http://localhost:9001"]
            assert call_args[1]["api_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_discover_and_filter_tools(self):
        """Test discovering and filtering tools by capabilities."""
        base_urls = ["http://agent1:8000", "http://agent2:8001"]

        with patch("agent.integrations.crewai.discovery.AgentUpDiscovery") as mock_discovery_class:
            mock_discovery = AsyncMock()
            mock_discovery_class.return_value = mock_discovery

            # Mock tools and agents
            mock_tool1 = MagicMock()
            mock_tool2 = MagicMock()
            mock_tools = [mock_tool1, mock_tool2]

            mock_agents = [
                {"name": "Agent 1", "skills": [{"name": "research skill", "tags": ["research"]}]},
                {"name": "Agent 2", "skills": [{"name": "writing skill", "tags": ["writing"]}]},
            ]

            mock_discovery.create_tools_from_agents.return_value = mock_tools
            mock_discovery.discover_agents.return_value = mock_agents

            # Test without filtering
            tools = await discover_and_filter_tools(base_urls)
            assert tools == mock_tools

            # Test with filtering
            tools = await discover_and_filter_tools(base_urls, required_capabilities=["research"])

            # Should return only the first tool (research agent)
            assert len(tools) == 1
            assert tools[0] == mock_tool1

    @pytest.mark.asyncio
    async def test_discover_and_filter_tools_no_matches(self):
        """Test filtering with no matching capabilities."""
        base_urls = ["http://agent1:8000"]

        with patch("agent.integrations.crewai.discovery.AgentUpDiscovery") as mock_discovery_class:
            mock_discovery = AsyncMock()
            mock_discovery_class.return_value = mock_discovery

            mock_tools = [MagicMock()]
            mock_agents = [{"name": "Agent 1", "skills": [{"name": "writing skill", "tags": ["writing"]}]}]

            mock_discovery.create_tools_from_agents.return_value = mock_tools
            mock_discovery.discover_agents.return_value = mock_agents

            # Test with non-matching capability
            tools = await discover_and_filter_tools(base_urls, required_capabilities=["nonexistent"])

            # Should return empty list
            assert tools == []


@pytest.mark.integration
class TestAgentUpDiscoveryIntegration:
    """Integration tests for AgentUpDiscovery."""

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    @pytest.mark.asyncio
    async def test_real_discovery(self):
        """Test discovery against real AgentUp agents."""
        discovery = AgentUpDiscovery(base_urls=["http://localhost:8000"])

        try:
            agents = await discovery.discover_agents()
            assert isinstance(agents, list)

            if agents:
                agent = agents[0]
                assert "name" in agent
                assert "base_url" in agent
                assert "skills" in agent
        except Exception as e:
            pytest.skip(f"No AgentUp agents running: {e}")

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    @pytest.mark.asyncio
    async def test_real_tool_creation(self):
        """Test creating tools from real agents."""
        discovery = AgentUpDiscovery(base_urls=["http://localhost:8000"])

        try:
            tools = await discovery.create_tools_from_agents()
            assert isinstance(tools, list)

            for tool in tools:
                # Each tool should have the expected attributes
                assert hasattr(tool, "agent_name")
                assert hasattr(tool, "config")
                assert callable(tool.health_check)
        except Exception as e:
            pytest.skip(f"No AgentUp agents running: {e}")


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
