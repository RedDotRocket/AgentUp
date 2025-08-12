import httpx
import pytest

from agent.integrations.crewai.a2a_client import A2AClient


class TestA2AClient:
    """Test cases for A2AClient."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return A2AClient(base_url="http://test:8000", api_key="test-key", timeout=10, max_retries=2)

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        return {
            "jsonrpc": "2.0",
            "result": {"message": {"role": "assistant", "parts": [{"kind": "text", "text": "Test response"}]}},
            "id": "test-request-id",
        }

    @pytest.mark.asyncio
    async def test_send_message_success(self, client, mock_response):
        """Test successful message sending."""

        def mock_handler(request):
            # Verify request details
            assert request.url == "http://test:8000"
            assert request.headers["Content-Type"] == "application/json"
            assert request.headers["X-API-Key"] == "test-key"

            # Parse and verify request JSON
            import json

            request_data = json.loads(request.content.decode())
            assert request_data["jsonrpc"] == "2.0"
            assert request_data["method"] == "message/send"
            assert "params" in request_data
            assert "id" in request_data

            return httpx.Response(200, json=mock_response)

        # Create mock transport and client
        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        result = await client.send_message("Test message")

        # Verify result
        assert result == mock_response["result"]

    @pytest.mark.asyncio
    async def test_send_message_with_context_id(self, client, mock_response):
        """Test message sending with context ID."""

        def mock_handler(request):
            import json

            request_data = json.loads(request.content.decode())
            assert request_data["params"]["context_id"] == "test-context"
            return httpx.Response(200, json=mock_response)

        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        await client.send_message("Test message", context_id="test-context")

    @pytest.mark.asyncio
    async def test_send_message_retry_on_failure(self, client):
        """Test retry mechanism on failure."""
        call_count = 0

        def mock_handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails
                return httpx.Response(500, text="Server Error")
            else:
                # Second call succeeds
                return httpx.Response(200, json={"jsonrpc": "2.0", "result": {}, "id": "test"})

        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        await client.send_message("Test message")

        # Should have been called twice
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_send_message_max_retries_exceeded(self, client):
        """Test behavior when max retries are exceeded."""
        call_count = 0

        def mock_handler(_request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, text="Server Error")

        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(Exception, match="500 Internal Server Error"):
            await client.send_message("Test message")

        # Should have been called max_retries times
        assert call_count == client.max_retries

    @pytest.mark.asyncio
    async def test_send_message_a2a_error(self, client):
        """Test handling of A2A protocol errors."""
        error_response = {
            "jsonrpc": "2.0",
            "error": {"code": -32001, "message": "Task not found"},
            "id": "test-request-id",
        }

        def mock_handler(_request):
            return httpx.Response(200, json=error_response)

        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(Exception, match="A2A Error"):
            await client.send_message("Test message")

    @pytest.mark.asyncio
    async def test_get_agent_card(self, client):
        """Test fetching agent card."""
        agent_card = {"name": "Test Agent", "description": "Test Description", "skills": []}

        def mock_handler(request):
            assert request.url == "http://test:8000/.well-known/agent-card.json"
            return httpx.Response(200, json=agent_card)

        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        result = await client.get_agent_card()
        assert result == agent_card

    @pytest.mark.asyncio
    async def test_get_task_status(self, client):
        """Test getting task status."""
        task_status = {"id": "task-123", "status": "completed", "result": "Task completed successfully"}

        def mock_handler(request):
            assert request.url == "http://test:8000/task/task-123/status"
            assert request.headers["X-API-Key"] == "test-key"
            return httpx.Response(200, json=task_status)

        mock_transport = httpx.MockTransport(mock_handler)
        client.client = httpx.AsyncClient(transport=mock_transport)

        result = await client.get_task_status("task-123")
        assert result == task_status

    def test_extract_text_from_response_message_format(self, client):
        """Test text extraction from message format response."""
        response = {
            "message": {
                "role": "assistant",
                "parts": [
                    {"kind": "text", "text": "Hello "},
                    {"kind": "text", "text": "world!"},
                    {"kind": "data", "data": {"key": "value"}},  # Should be ignored
                ],
            }
        }

        result = client.extract_text_from_response(response)
        assert result == "Hello  world!"

    def test_extract_text_from_response_task_format(self, client):
        """Test text extraction from task format response."""
        response = {
            "task": {
                "id": "task-123",
                "artifacts": [
                    {"kind": "text", "content": "Task result here"},
                    {"kind": "data", "content": "data content"},  # Should be ignored
                ],
            }
        }

        result = client.extract_text_from_response(response)
        assert result == "Task result here"

    def test_extract_text_from_response_fallback(self, client):
        """Test text extraction fallback to string representation."""
        response = {"unknown": "format", "data": 123}

        result = client.extract_text_from_response(response)
        assert result == str(response)

    def test_extract_text_from_response_empty(self, client):
        """Test text extraction from empty response."""
        result = client.extract_text_from_response({})
        assert result == ""

        result = client.extract_text_from_response(None)
        assert result == ""

    def test_get_headers_with_api_key(self, client):
        """Test header generation with API key."""
        headers = client._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["X-API-Key"] == "test-key"

    def test_get_headers_without_api_key(self):
        """Test header generation without API key."""
        client = A2AClient(base_url="http://test:8000")
        headers = client._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert "X-API-Key" not in headers

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        client = A2AClient(base_url="http://test:8000")

        async with client as c:
            assert c.client is not None
            assert isinstance(c.client, httpx.AsyncClient)

        # Client should be closed after exiting context
        # Note: In real usage, client would be None or closed


@pytest.mark.integration
class TestA2AClientIntegration:
    """Integration tests for A2AClient (require running AgentUp agent)."""

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    @pytest.mark.asyncio
    async def test_real_agent_connection(self):
        """Test connection to a real AgentUp agent."""
        client = A2AClient(base_url="http://localhost:8000")

        try:
            agent_card = await client.get_agent_card()
            assert "name" in agent_card
            assert "description" in agent_card
        except Exception as e:
            pytest.skip(f"No AgentUp agent running: {e}")

    @pytest.mark.skipif(True, reason="Integration tests disabled (no real agents running)")
    @pytest.mark.asyncio
    async def test_real_message_sending(self):
        """Test sending a real message to AgentUp agent."""
        client = A2AClient(base_url="http://localhost:8000", api_key="test-key")

        try:
            async with client:
                result = await client.send_message("Hello, how are you?")
                assert result is not None

                # Extract text from response
                text = client.extract_text_from_response(result)
                assert isinstance(text, str)
                assert len(text) > 0
        except Exception as e:
            pytest.skip(f"No AgentUp agent running or authentication failed: {e}")


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
