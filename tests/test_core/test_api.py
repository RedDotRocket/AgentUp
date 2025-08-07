import json

# Import the API components to test
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Import FastAPI testing utilities
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from a2a.server.request_handlers import DefaultRequestHandler

from agent.api import (
    create_agent_card,
    get_request_handler,
    jsonrpc_error_handler,
    router,
    set_request_handler_instance,
    sse_generator,
)
from agent.config.a2a import (
    AgentCapabilities,
    AgentCard,
    JSONRPCError,
)


class TestAgentCard:
    @patch("agent.api.routes.ConfigurationManager")
    def test_create_agent_card_minimal(self, mock_config_manager):
        mock_config = {
            "project_name": "TestAgent",
            "description": "Test Agent Description",
            "agent": {"name": "TestAgent", "description": "Test Agent", "version": "1.0.0"},
            "skills": [],
            "state_management": {"enabled": True},
        }
        mock_config_manager.return_value.config = mock_config

        card = create_agent_card()

        assert isinstance(card, AgentCard)
        assert card.name == "TestAgent"
        assert card.description == "Test Agent"
        assert card.version == "1.0.0"
        assert card.url == "http://localhost:8000"
        assert len(card.skills) == 0

        # Check capabilities
        assert card.capabilities.streaming is True
        assert card.capabilities.state_transition_history is True

    @patch("agent.api.routes.ConfigurationManager")
    def test_create_agent_card_with_skills(self, mock_config_manager):
        mock_config = {
            "agent": {"name": "SkillfulAgent", "description": "Agent with skills", "version": "2.0.0"},
            "plugins": [
                {
                    "plugin_id": "chat",
                    "name": "Chat",
                    "description": "General chat capabilities",
                    "input_mode": "text",
                    "output_mode": "text",
                    "tags": ["chat", "general"],
                }
            ],
        }
        mock_config_manager.return_value.config = mock_config

        card = create_agent_card()

        # With registry-only approach, configured plugins don't appear unless loaded in registry
        assert len(card.skills) == 0

    @patch("agent.api.routes.ConfigurationManager")
    def test_create_agent_card_with_security_enabled(self, mock_config_manager):
        mock_config = {
            "agent": {"name": "SecureAgent"},
            "skills": [],
            "security": {"enabled": True, "type": "api_key"},
        }
        mock_config_manager.return_value.config = mock_config

        card = create_agent_card()

        # Just verify security is configured
        assert card.security is not None
        assert len(card.security) > 0

    @patch("agent.api.routes.ConfigurationManager")
    def test_create_agent_card_caching(self, mock_config_manager):
        """Test that AgentCard creation works (caching removed for simplicity)."""
        mock_config = {
            "project_name": "CachedAgent",
            "agent": {"name": "CachedAgent", "description": "Test caching", "version": "1.0.0"},
            "plugins": [],
        }
        mock_config_manager.return_value.config = mock_config

        # Create agent cards
        card1 = create_agent_card()
        card2 = create_agent_card()

        # Cards should be equal but not necessarily the same instance (no caching)
        assert card1 == card2
        assert card1.name == "CachedAgent"

        # Test extended cards
        extended_card1 = create_agent_card(extended=True)
        extended_card2 = create_agent_card(extended=True)

        assert extended_card1 == extended_card2


class TestRequestHandlerManagement:
    def test_set_and_get_request_handler(self):
        mock_handler = Mock(spec=DefaultRequestHandler)

        set_request_handler_instance(mock_handler)
        result = get_request_handler()

        assert result is mock_handler

    def test_get_request_handler_not_initialized(self):
        # Clear the global handler
        import agent.api.routes

        agent.api.routes._request_handler = None

        with pytest.raises(RuntimeError, match="Request handler not initialized"):
            get_request_handler()


class TestHealthEndpoints:
    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    @patch("agent.api.routes.ConfigurationManager")
    def test_health_check(self, mock_config_manager, client):
        mock_config_manager.return_value.get.return_value = "TestAgent"

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent"] == "TestAgent"
        assert "timestamp" in data


class TestAgentDiscovery:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @patch("agent.api.routes.create_agent_card")
    def test_agent_discovery_endpoint(self, mock_create_card, client):
        # Create a mock agent card
        mock_card = AgentCard(
            name="TestAgent",
            description="Test Description",
            version="1.0.0",
            url="http://localhost:8000",
            capabilities=AgentCapabilities(streaming=True, state_transition_history=True),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        # Mock create_agent_card to return our test card
        mock_create_card.return_value = mock_card

        response = client.get("/.well-known/agent-card.json")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TestAgent"
        assert data["version"] == "1.0.0"


class TestJSONRPCEndpoint:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def mock_handler(self):
        handler = Mock(spec=DefaultRequestHandler)
        set_request_handler_instance(handler)
        return handler

    @patch("agent.api.protected")
    def test_jsonrpc_not_dict(self, mock_protected, client, mock_handler):
        mock_protected.return_value = lambda func: func

        response = client.post("/", json=[])

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32600
        assert data["error"]["message"] == "Invalid Request"

    @patch("agent.api.protected")
    def test_jsonrpc_wrong_version(self, mock_protected, client, mock_handler):
        mock_protected.return_value = lambda func: func

        response = client.post("/", json={"jsonrpc": "1.0", "method": "test", "id": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32600
        assert data["error"]["message"] == "Invalid Request"

    @patch("agent.api.protected")
    @patch("agent.api.routes.get_auth_result")
    def test_jsonrpc_method_not_found(self, mock_get_auth_result, mock_protected, client, mock_handler):
        mock_protected.return_value = lambda func: func
        mock_get_auth_result.return_value = None

        # Mock the app.state.agent_card
        mock_card = AgentCard(
            name="TestAgent",
            description="Test Description",
            version="1.0.0",
            url="http://localhost:8000",
            capabilities=AgentCapabilities(streaming=True, state_transition_history=True),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        # Mock the security manager to avoid the async authentication call
        mock_security_manager = Mock()
        mock_security_manager.is_auth_enabled.return_value = False

        client.app.state = Mock()
        client.app.state.agent_card = mock_card
        client.app.state.security_manager = mock_security_manager

        response = client.post("/", json={"jsonrpc": "2.0", "method": "unknown/method", "id": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32601
        assert data["error"]["message"] == "Method not found"


class TestSSEGenerator:
    @pytest.mark.asyncio
    async def test_sse_generator_success(self):
        async def mock_iterator():
            for i in range(3):
                mock_response = Mock()
                mock_response.model_dump_json.return_value = f'{{"data": {i}}}'
                yield mock_response

        result = []
        async for data in sse_generator(mock_iterator()):
            result.append(data)

        assert len(result) == 3
        assert result[0] == 'data: {"data": 0}\n\n'
        assert result[1] == 'data: {"data": 1}\n\n'
        assert result[2] == 'data: {"data": 2}\n\n'

    @pytest.mark.asyncio
    async def test_sse_generator_error(self):
        async def mock_iterator():
            yield Mock(model_dump_json=Mock(return_value='{"data": "ok"}'))
            raise Exception("Stream error")

        result = []
        async for data in sse_generator(mock_iterator()):
            result.append(data)

        assert len(result) == 2
        assert result[0] == 'data: {"data": "ok"}\n\n'
        assert "Stream error" in result[1]


class TestJSONRPCErrorHandler:
    @pytest.mark.asyncio
    async def test_jsonrpc_error_handler(self):
        request = Mock(spec=Request)
        error = JSONRPCError(code=-32600, message="Invalid Request", data={"detail": "Missing required field"})

        response = await jsonrpc_error_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        content = json.loads(response.body)
        assert content["error"]["code"] == -32600
        assert content["error"]["message"] == "Invalid Request"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
