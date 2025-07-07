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
from agent.models import (
    AgentCapabilities,
    AgentCard,
    JSONRPCError,
)


class TestAgentCard:
    """Test agent card creation."""

    @patch("agent.api.routes.load_config")
    def test_create_agent_card_minimal(self, mock_load_config):
        """Test creating agent card with minimal configuration."""
        mock_load_config.return_value = {
            "project_name": "TestAgent",
            "description": "Test Agent Description",
            "agent": {"name": "TestAgent", "description": "Test Agent", "version": "1.0.0"},
            "skills": [],
        }

        card = create_agent_card()

        assert isinstance(card, AgentCard)
        assert card.name == "TestAgent"
        assert card.description == "Test Agent"
        assert card.version == "1.0.0"
        assert card.url == "http://localhost:8000"
        assert len(card.skills) == 0

        # Check capabilities
        assert card.capabilities.streaming is True
        assert card.capabilities.pushNotifications is False
        assert card.capabilities.stateTransitionHistory is True

    @patch("agent.api.routes.load_config")
    def test_create_agent_card_with_skills(self, mock_load_config):
        """Test creating agent card with skills."""
        mock_load_config.return_value = {
            "agent": {"name": "SkillfulAgent", "description": "Agent with skills", "version": "2.0.0"},
            "skills": [
                {
                    "skill_id": "chat",
                    "name": "Chat",
                    "description": "General chat capabilities",
                    "input_mode": "text",
                    "output_mode": "text",
                    "tags": ["chat", "general"],
                }
            ],
        }

        card = create_agent_card()

        assert len(card.skills) == 1
        assert card.skills[0].id == "chat"
        assert card.skills[0].name == "Chat"

    @patch("agent.api.routes.load_config")
    def test_create_agent_card_with_security_enabled(self, mock_load_config):
        """Test creating agent card with security enabled."""
        mock_load_config.return_value = {
            "agent": {"name": "SecureAgent"},
            "skills": [],
            "security": {"enabled": True, "type": "api_key"},
        }

        card = create_agent_card()

        # Just verify security is configured
        assert card.securitySchemes is not None
        assert card.security is not None
        assert len(card.security) > 0


class TestRequestHandlerManagement:
    """Test request handler instance management."""

    def test_set_and_get_request_handler(self):
        """Test setting and getting request handler."""
        mock_handler = Mock(spec=DefaultRequestHandler)

        set_request_handler_instance(mock_handler)
        result = get_request_handler()

        assert result is mock_handler

    def test_get_request_handler_not_initialized(self):
        """Test getting request handler when not initialized."""
        # Clear the global handler
        import agent.api.routes

        agent.api.routes._request_handler = None

        with pytest.raises(RuntimeError, match="Request handler not initialized"):
            get_request_handler()


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @patch("agent.api.routes.load_config")
    def test_health_check(self, mock_load_config, client):
        """Test basic health check endpoint."""
        mock_load_config.return_value = {"project_name": "TestAgent"}

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent"] == "TestAgent"
        assert "timestamp" in data


class TestAgentDiscovery:
    """Test agent discovery endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @patch("agent.api.routes.create_agent_card")
    def test_agent_discovery_endpoint(self, mock_create_card, client):
        """Test /.well-known/agent.json endpoint."""
        mock_card = AgentCard(
            name="TestAgent",
            description="Test Description",
            version="1.0.0",
            url="http://localhost:8000",
            capabilities=AgentCapabilities(streaming=True, pushNotifications=True, stateTransitionHistory=True),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )
        mock_create_card.return_value = mock_card

        response = client.get("/.well-known/agent.json")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TestAgent"
        assert data["version"] == "1.0.0"


class TestJSONRPCEndpoint:
    """Test main JSON-RPC endpoint validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def mock_handler(self):
        """Create mock request handler."""
        handler = Mock(spec=DefaultRequestHandler)
        set_request_handler_instance(handler)
        return handler

    @patch("agent.api.protected")
    def test_jsonrpc_not_dict(self, mock_protected, client, mock_handler):
        """Test JSON-RPC endpoint with non-dict body."""
        mock_protected.return_value = lambda func: func

        response = client.post("/", json=[])

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32600
        assert data["error"]["message"] == "Invalid Request"

    @patch("agent.api.protected")
    def test_jsonrpc_wrong_version(self, mock_protected, client, mock_handler):
        """Test JSON-RPC endpoint with wrong version."""
        mock_protected.return_value = lambda func: func

        response = client.post("/", json={"jsonrpc": "1.0", "method": "test", "id": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32600
        assert data["error"]["message"] == "Invalid Request"

    @patch("agent.api.protected")
    def test_jsonrpc_method_not_found(self, mock_protected, client, mock_handler):
        """Test JSON-RPC endpoint with unknown method."""
        mock_protected.return_value = lambda func: func

        response = client.post("/", json={"jsonrpc": "2.0", "method": "unknown/method", "id": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32601
        assert data["error"]["message"] == "Method not found"


class TestSSEGenerator:
    """Test SSE generator for streaming responses."""

    @pytest.mark.asyncio
    async def test_sse_generator_success(self):
        """Test SSE generator with successful responses."""

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
        """Test SSE generator with error."""

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
    """Test JSON-RPC error handler."""

    @pytest.mark.asyncio
    async def test_jsonrpc_error_handler(self):
        """Test JSON-RPC error handler."""
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
