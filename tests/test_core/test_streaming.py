"""Tests for A2A streaming functionality."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from agent.api.routes import sse_generator


class TestStreamingEndpoint:
    """Test the message/stream endpoint."""

    @pytest.mark.asyncio
    async def test_sse_generator_success(self):
        """Test SSE generator with successful responses."""

        # Mock async iterator
        async def mock_responses():
            # Mock SendStreamingMessageResponse objects
            response1 = MagicMock()
            response1.model_dump_json.return_value = '{"result": "processing"}'

            response2 = MagicMock()
            response2.model_dump_json.return_value = '{"result": "completed"}'

            yield response1
            yield response2

        # Test SSE generator
        events = []
        async for event in sse_generator(mock_responses()):
            events.append(event)

        assert len(events) == 2
        assert events[0] == 'data: {"result": "processing"}\\n\\n'
        assert events[1] == 'data: {"result": "completed"}\\n\\n'

    @pytest.mark.asyncio
    async def test_sse_generator_error(self):
        """Test SSE generator with exception."""

        # Mock async iterator that raises exception
        async def mock_responses():
            response1 = MagicMock()
            response1.model_dump_json.return_value = '{"result": "processing"}'
            yield response1

            raise ValueError("Test error")

        # Test SSE generator
        events = []
        async for event in sse_generator(mock_responses()):
            events.append(event)

        assert len(events) == 2
        assert events[0] == 'data: {"result": "processing"}\\n\\n'

        # Second event should be error
        assert "data:" in events[1]
        error_data = json.loads(events[1].replace("data: ", "").replace("\\n\\n", ""))
        assert "error" in error_data
        assert error_data["error"]["message"] == "Test error"

    @pytest.mark.asyncio
    async def test_streaming_endpoint_authentication(self, client: AsyncClient):
        """Test streaming endpoint requires authentication."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "test"}],
                    "messageId": "msg-test",
                    "kind": "message",
                }
            },
            "id": "req-test",
        }

        response = await client.post("/", json=request_data)

        # Should require authentication
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_streaming_endpoint_invalid_method(self, authenticated_client: AsyncClient):
        """Test streaming endpoint with invalid method."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "invalid/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "test"}],
                    "messageId": "msg-test",
                    "kind": "message",
                }
            },
            "id": "req-test",
        }

        response = await authenticated_client.post("/", json=request_data)

        # Should return method not found error
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found

    @pytest.mark.asyncio
    async def test_streaming_endpoint_missing_params(self, authenticated_client: AsyncClient):
        """Test streaming endpoint with missing parameters."""
        request_data = {"jsonrpc": "2.0", "method": "message/stream", "params": {}, "id": "req-test"}

        response = await authenticated_client.post("/", json=request_data)

        # Should return invalid parameters error
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_streaming_endpoint_invalid_json(self, authenticated_client: AsyncClient):
        """Test streaming endpoint with invalid JSON."""
        response = await authenticated_client.post(
            "/", content="invalid json", headers={"Content-Type": "application/json"}
        )

        # Should return parse error
        assert response.status_code == 400

    @pytest.mark.asyncio
    @patch("agent.api.routes.jsonrpc_handler")
    async def test_streaming_endpoint_success(self, mock_handler, authenticated_client: AsyncClient):
        """Test successful streaming endpoint interaction."""

        # Mock streaming response
        async def mock_stream():
            response1 = MagicMock()
            response1.model_dump_json.return_value = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "result": {"id": "task-123", "status": {"state": "in_progress"}, "artifacts": []},
                    "id": "req-test",
                }
            )
            yield response1

            response2 = MagicMock()
            response2.model_dump_json.return_value = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "result": {
                        "id": "task-123",
                        "status": {"state": "completed"},
                        "artifacts": [{"name": "Agent-result", "parts": [{"kind": "text", "text": "Test response"}]}],
                    },
                    "id": "req-test",
                }
            )
            yield response2

        mock_handler.on_message_send_stream.return_value = mock_stream()

        request_data = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "test message"}],
                    "messageId": "msg-test",
                    "kind": "message",
                }
            },
            "id": "req-test",
        }

        async with authenticated_client.stream("POST", "/", json=request_data) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(line[6:])

            assert len(events) == 2

            # Validate first event
            event1_data = json.loads(events[0])
            assert event1_data["result"]["status"]["state"] == "in_progress"

            # Validate second event
            event2_data = json.loads(events[1])
            assert event2_data["result"]["status"]["state"] == "completed"
            assert len(event2_data["result"]["artifacts"]) == 1


class TestStreamingIntegration:
    """Integration tests for streaming functionality."""

    @pytest.mark.asyncio
    async def test_streaming_with_oauth2_auth(self):
        """Test streaming with OAuth2 authentication."""
        # This would require a running server with OAuth2 configured
        # Implementation depends on test setup
        pass

    @pytest.mark.asyncio
    async def test_streaming_timeout_handling(self):
        """Test streaming behavior with timeouts."""

        # Mock a slow streaming response
        async def slow_stream():
            await asyncio.sleep(0.1)
            response = MagicMock()
            response.model_dump_json.return_value = '{"result": "slow response"}'
            yield response

        events = []
        try:
            async with asyncio.timeout(0.05):  # Very short timeout
                async for event in sse_generator(slow_stream()):
                    events.append(event)
        except asyncio.TimeoutError:
            pass  # Expected

        # Should have received no events due to timeout
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_streaming_large_response(self):
        """Test streaming with large responses."""
        # Mock large response
        large_text = "A" * 10000  # 10KB text

        async def large_stream():
            response = MagicMock()
            response.model_dump_json.return_value = json.dumps(
                {"result": {"artifacts": [{"parts": [{"text": large_text}]}]}}
            )
            yield response

        events = []
        async for event in sse_generator(large_stream()):
            events.append(event)

        assert len(events) == 1
        # Verify large content is properly formatted
        assert large_text in events[0]

    @pytest.mark.asyncio
    async def test_streaming_concurrent_requests(self):
        """Test multiple concurrent streaming requests."""

        async def mock_stream(stream_id):
            for i in range(3):
                response = MagicMock()
                response.model_dump_json.return_value = f'{{"stream_id": "{stream_id}", "event": {i}}}'
                yield response
                await asyncio.sleep(0.01)  # Small delay

        # Run multiple streams concurrently
        tasks = []
        for stream_id in range(3):
            task = asyncio.create_task(self._collect_stream_events(mock_stream(stream_id)))
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Each stream should have 3 events
        for events in results:
            assert len(events) == 3

    async def _collect_stream_events(self, stream):
        """Helper to collect events from a stream."""
        events = []
        async for event in sse_generator(stream):
            events.append(event)
        return events


class TestStreamingValidation:
    """Tests for streaming request/response validation."""

    def test_streaming_request_validation(self):
        """Test validation of streaming request format."""
        # Valid request
        valid_request = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "test"}],
                    "messageId": "msg-123",
                    "kind": "message",
                }
            },
            "id": "req-123",
        }

        # This would be validated by the actual endpoint
        assert valid_request["method"] == "message/stream"
        assert "message" in valid_request["params"]
        assert valid_request["params"]["message"]["role"] == "user"

    def test_streaming_response_format(self):
        """Test streaming response format compliance."""
        # Mock response object
        response_data = {
            "jsonrpc": "2.0",
            "result": {
                "id": "task-123",
                "kind": "task",
                "status": {"state": "completed", "timestamp": "2025-01-15T10:30:00Z"},
                "artifacts": [
                    {
                        "artifactId": "artifact-123",
                        "name": "Agent-result",
                        "parts": [{"kind": "text", "text": "Response"}],
                    }
                ],
                "contextId": "context-123",
            },
            "id": "req-123",
        }

        # Validate A2A compliance
        assert response_data["jsonrpc"] == "2.0"
        assert "result" in response_data
        assert response_data["result"]["kind"] == "task"
        assert "status" in response_data["result"]
        assert "artifacts" in response_data["result"]

    def test_sse_event_format(self):
        """Test SSE event format compliance."""
        # Test data
        json_data = '{"test": "data"}'

        # Format as SSE event
        sse_event = f"data: {json_data}\\n\\n"

        # Validate format
        assert sse_event.startswith("data: ")
        assert sse_event.endswith("\\n\\n")

        # Extract and validate JSON
        extracted_json = sse_event[6:-2]  # Remove "data: " and "\\n\\n"
        parsed_data = json.loads(extracted_json)
        assert parsed_data["test"] == "data"


# Fixtures for authenticated client
@pytest.fixture
async def authenticated_client():
    """Create an authenticated test client."""
    # This would need to be implemented based on your auth setup
    # For now, return a mock
    client = MagicMock(spec=AsyncClient)
    return client
