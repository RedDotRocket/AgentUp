"""Unit tests for agent registration functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agent.services.agent_registration import AgentRegistrationClient
from src.agent.services.config import ConfigurationManager
from src.agent.services.model import AgentRegistrationPayload


class TestAgentRegistrationPayload:
    """Test the AgentRegistrationPayload model."""

    def test_valid_payload_creation(self):
        """Test creating a valid registration payload."""
        payload = AgentRegistrationPayload(
            agent_url="http://localhost:8001",
            name="Test Agent",
            version="1.0.0",
            agent_card_url="http://localhost:8001/.well-known/agent-card.json",
            description="A test agent",
        )

        assert payload.agent_url == "http://localhost:8001"
        assert payload.name == "Test Agent"
        assert payload.version == "1.0.0"
        assert payload.agent_card_url == "http://localhost:8001/.well-known/agent-card.json"
        assert payload.description == "A test agent"

    def test_payload_without_description(self):
        """Test creating payload without optional description."""
        payload = AgentRegistrationPayload(
            agent_url="http://localhost:8001",
            name="Test Agent",
            version="1.0.0",
            agent_card_url="http://localhost:8001/.well-known/agent-card.json",
        )

        assert payload.description is None

    def test_invalid_url_validation(self):
        """Test URL validation for agent_url and agent_card_url."""
        with pytest.raises(ValueError, match="URL must start with http:// or https://"):
            AgentRegistrationPayload(
                agent_url="localhost:8001",  # Missing protocol
                name="Test Agent",
                version="1.0.0",
                agent_card_url="http://localhost:8001/.well-known/agent-card.json",
            )

    def test_invalid_version_validation(self):
        """Test version validation."""
        with pytest.raises(ValueError, match="Version must follow semantic versioning"):
            AgentRegistrationPayload(
                agent_url="http://localhost:8001",
                name="Test Agent",
                version="1.0",  # Invalid semantic version
                agent_card_url="http://localhost:8001/.well-known/agent-card.json",
            )

    def test_model_dump(self):
        """Test model serialization."""
        payload = AgentRegistrationPayload(
            agent_url="http://localhost:8001",
            name="Test Agent",
            version="1.0.0",
            agent_card_url="http://localhost:8001/.well-known/agent-card.json",
        )

        data = payload.model_dump()
        expected = {
            "agent_url": "http://localhost:8001",
            "name": "Test Agent",
            "version": "1.0.0",
            "agent_card_url": "http://localhost:8001/.well-known/agent-card.json",
            "description": None,
        }

        assert data == expected


class TestAgentRegistrationClient:
    """Test the AgentRegistrationClient service."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration manager."""
        config_manager = MagicMock(spec=ConfigurationManager)
        return config_manager

    @pytest.fixture
    def registration_client(self, mock_config):
        """Create a registration client with mocked config."""
        return AgentRegistrationClient(mock_config)

    @patch("agent.config.get_settings")
    async def test_initialize_without_orchestrator(self, mock_get_settings, registration_client):
        """Test initialization when no orchestrator is configured."""
        # Mock settings to return None for orchestrator
        mock_settings = MagicMock()
        mock_settings.orchestrator = None
        mock_get_settings.return_value = mock_settings

        await registration_client.initialize()

        assert registration_client._initialized is True
        assert registration_client.orchestrator_url is None

    @patch("agent.config.get_settings")
    async def test_initialize_with_orchestrator(self, mock_get_settings, registration_client):
        """Test initialization with orchestrator configured."""
        # Mock settings with orchestrator URL
        mock_settings = MagicMock()
        mock_settings.orchestrator = "http://localhost:8050"
        mock_settings.project_name = "Test Agent"
        mock_settings.version = "1.0.0"
        mock_settings.description = "Test description"
        mock_settings.api.host = "127.0.0.1"
        mock_settings.api.port = 8001
        mock_get_settings.return_value = mock_settings

        # Mock the registration method to avoid actual HTTP calls
        with patch.object(
            registration_client, "_register_with_orchestrator", new_callable=AsyncMock, return_value=True
        ):
            await registration_client.initialize()

            assert registration_client._initialized is True
            assert registration_client.orchestrator_url == "http://localhost:8050"
            assert registration_client.agent_url == "http://localhost:8001"

    @patch("agent.config.get_settings")
    async def test_initialize_with_localhost_host(self, mock_get_settings, registration_client):
        """Test initialization handles localhost host correctly."""
        mock_settings = MagicMock()
        mock_settings.orchestrator = "http://localhost:8050"
        mock_settings.project_name = "Test Agent"
        mock_settings.version = "1.0.0"
        mock_settings.description = "Test description"
        mock_settings.api.host = "0.0.0.0"  # Should convert to localhost
        mock_settings.api.port = 8001
        mock_get_settings.return_value = mock_settings

        with patch.object(
            registration_client, "_register_with_orchestrator", new_callable=AsyncMock, return_value=True
        ):
            await registration_client.initialize()

            assert registration_client.agent_url == "http://localhost:8001"

    @patch("agent.config.get_settings")
    async def test_initialize_with_failed_registration(self, mock_get_settings, registration_client):
        """Test initialization when registration fails."""
        # Mock settings with orchestrator URL
        mock_settings = MagicMock()
        mock_settings.orchestrator = "http://localhost:8050"
        mock_settings.project_name = "Test Agent"
        mock_settings.version = "1.0.0"
        mock_settings.description = "Test description"
        mock_settings.api.host = "127.0.0.1"
        mock_settings.api.port = 8001
        mock_get_settings.return_value = mock_settings

        # Mock the registration method to return False (failed)
        with patch.object(
            registration_client, "_register_with_orchestrator", new_callable=AsyncMock, return_value=False
        ):
            await registration_client.initialize()

            assert registration_client._initialized is False
            assert registration_client.orchestrator_url == "http://localhost:8050"
            assert registration_client.agent_url == "http://localhost:8001"

    @patch("httpx.AsyncClient")
    async def test_successful_registration(self, mock_http_client, registration_client):
        """Test successful agent registration."""
        # Setup mocks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_response.content = b'{"status": "success"}'

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance

        # Set up registration client
        registration_client.orchestrator_url = "http://localhost:8050"
        registration_client.agent_url = "http://localhost:8001"

        agent_info = {"name": "Test Agent", "version": "1.0.0", "description": "Test description"}

        # Call registration
        await registration_client._register_with_orchestrator(agent_info)

        # Verify HTTP call was made
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args

        assert call_args[0][0] == "http://localhost:8050/agent/register"
        assert call_args[1]["headers"] == {"Content-Type": "application/json"}

        # Verify payload
        payload_data = call_args[1]["json"]
        assert payload_data["agent_url"] == "http://localhost:8001"
        assert payload_data["name"] == "Test Agent"
        assert payload_data["version"] == "1.0.0"

    @patch("httpx.AsyncClient")
    async def test_registration_retry_on_failure(self, mock_http_client, registration_client):
        """Test registration retries on failure."""
        # Setup client to fail twice, then succeed
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Internal Server Error"

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"status": "success"}
        mock_response_success.content = b'{"status": "success"}'

        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance

        # Set retry delay to 0 for faster testing
        registration_client.retry_delay = 0
        registration_client.orchestrator_url = "http://localhost:8050"
        registration_client.agent_url = "http://localhost:8001"

        agent_info = {"name": "Test Agent", "version": "1.0.0", "description": "Test description"}

        await registration_client._register_with_orchestrator(agent_info)

        # Should have made 3 calls (2 failures + 1 success)
        assert mock_client_instance.post.call_count == 3

    @patch("httpx.AsyncClient")
    async def test_registration_timeout_handling(self, mock_http_client, registration_client):
        """Test registration handles timeouts gracefully."""
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.TimeoutException("Timeout")
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance

        registration_client.retry_delay = 0
        registration_client.max_retries = 1  # Reduce retries for faster test
        registration_client.orchestrator_url = "http://localhost:8050"
        registration_client.agent_url = "http://localhost:8001"

        agent_info = {"name": "Test Agent", "version": "1.0.0"}

        # Should not raise exception, just log warnings
        await registration_client._register_with_orchestrator(agent_info)

        assert mock_client_instance.post.call_count == 1

    @patch("httpx.AsyncClient")
    async def test_registration_connection_error_handling(self, mock_http_client, registration_client):
        """Test registration handles connection errors gracefully."""
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.ConnectError("Connection failed")
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance

        registration_client.retry_delay = 0
        registration_client.max_retries = 1
        registration_client.orchestrator_url = "http://localhost:8050"
        registration_client.agent_url = "http://localhost:8001"

        agent_info = {"name": "Test Agent", "version": "1.0.0"}

        # Should not raise exception, just log warnings
        await registration_client._register_with_orchestrator(agent_info)

        assert mock_client_instance.post.call_count == 1

    async def test_missing_urls_handling(self, registration_client):
        """Test handling when URLs are missing."""
        # Don't set URLs
        registration_client.orchestrator_url = None
        registration_client.agent_url = None

        agent_info = {"name": "Test Agent", "version": "1.0.0"}

        # Should return early without making HTTP calls
        await registration_client._register_with_orchestrator(agent_info)

        # No assertions needed - just checking it doesn't crash

    def test_get_registration_status(self, registration_client):
        """Test getting registration status."""
        # Test uninitialized state
        status = registration_client.get_registration_status()
        expected = {"registered": False, "orchestrator_url": None, "agent_url": None}
        assert status == expected

        # Test initialized state
        registration_client._initialized = True
        registration_client.orchestrator_url = "http://localhost:8050"
        registration_client.agent_url = "http://localhost:8001"

        status = registration_client.get_registration_status()
        expected = {
            "registered": True,
            "orchestrator_url": "http://localhost:8050",
            "agent_url": "http://localhost:8001",
        }
        assert status == expected

    async def test_shutdown(self, registration_client):
        """Test service shutdown."""
        registration_client._initialized = True

        await registration_client.shutdown()

        assert registration_client._initialized is False
