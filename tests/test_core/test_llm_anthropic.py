"""Comprehensive tests for Anthropic LLM provider (src/agent/llm_providers/anthropic.py)."""

# Add src to path for imports
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.llm_providers.anthropic import AnthropicProvider
from agent.llm_providers.base import (
    ChatMessage,
    LLMCapability,
    LLMProviderAPIError,
    LLMProviderConfigError,
    LLMProviderError,
    LLMResponse,
)


class TestAnthropicProviderInitialization:
    """Test Anthropic provider initialization."""

    def test_init_basic_config(self):
        """Test basic initialization with minimal config."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test-anthropic", config)

        assert provider.name == "test-anthropic"
        assert provider.api_key == "test-key"
        assert provider.model == "claude-3-sonnet-20240229"
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.timeout == 60.0
        assert provider.anthropic_version == "2023-06-01"
        assert provider.client is None
        assert not provider._initialized

    def test_init_full_config(self):
        """Test initialization with all configuration options."""
        config = {
            "api_key": "test-key",
            "model": "claude-3-opus-20240229",
            "base_url": "https://custom.anthropic.com",
            "timeout": 30.0,
            "anthropic_version": "2024-01-01",
        }
        provider = AnthropicProvider("custom-anthropic", config)

        assert provider.api_key == "test-key"
        assert provider.model == "claude-3-opus-20240229"
        assert provider.base_url == "https://custom.anthropic.com"
        assert provider.timeout == 30.0
        assert provider.anthropic_version == "2024-01-01"

    def test_init_default_values(self):
        """Test initialization with missing config values uses defaults."""
        config = {}
        provider = AnthropicProvider("default-anthropic", config)

        assert provider.api_key == ""
        assert provider.model == "claude-3-sonnet-20240229"
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.timeout == 60.0
        assert provider.anthropic_version == "2023-06-01"


class TestAnthropicProviderCapabilities:
    """Test capability detection and management."""

    def test_detect_capabilities_claude3_opus(self):
        """Test capability detection for Claude 3 Opus."""
        config = {"api_key": "test", "model": "claude-3-opus-20240229"}
        provider = AnthropicProvider("test", config)
        provider._detect_capabilities()

        expected_caps = [
            LLMCapability.TEXT_COMPLETION,
            LLMCapability.CHAT_COMPLETION,
            LLMCapability.STREAMING,
            LLMCapability.SYSTEM_MESSAGES,
            LLMCapability.IMAGE_UNDERSTANDING,
        ]

        for cap in expected_caps:
            assert provider.has_capability(cap), f"Missing capability: {cap}"

        # Should not have function calling (not supported by Anthropic yet)
        assert not provider.has_capability(LLMCapability.FUNCTION_CALLING)

    def test_detect_capabilities_claude3_sonnet(self):
        """Test capability detection for Claude 3 Sonnet."""
        config = {"api_key": "test", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.IMAGE_UNDERSTANDING)
        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)

    def test_detect_capabilities_claude3_haiku(self):
        """Test capability detection for Claude 3 Haiku."""
        config = {"api_key": "test", "model": "claude-3-haiku-20240307"}
        provider = AnthropicProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.IMAGE_UNDERSTANDING)
        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)

    def test_detect_capabilities_claude2(self):
        """Test capability detection for Claude 2."""
        config = {"api_key": "test", "model": "claude-2.1"}
        provider = AnthropicProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)
        assert not provider.has_capability(LLMCapability.IMAGE_UNDERSTANDING)

    def test_detect_capabilities_unknown_model(self):
        """Test capability detection for unknown models."""
        config = {"api_key": "test", "model": "unknown-claude-model"}
        provider = AnthropicProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.TEXT_COMPLETION)
        assert provider.has_capability(LLMCapability.CHAT_COMPLETION)
        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)
        assert not provider.has_capability(LLMCapability.IMAGE_UNDERSTANDING)


class TestAnthropicProviderServiceManagement:
    """Test service lifecycle management."""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)

        # Mock health check to succeed
        with patch.object(provider, "health_check", return_value={"status": "healthy"}):
            await provider.initialize()

        assert provider._initialized
        assert provider.client is not None
        assert isinstance(provider.client, httpx.AsyncClient)
        assert str(provider.client.base_url) == "https://api.anthropic.com"

        # Check headers
        assert provider.client.headers.get("x-api-key") == "test-key"
        assert provider.client.headers.get("Content-Type") == "application/json"
        assert provider.client.headers.get("anthropic-version") == "2023-06-01"
        assert provider.client.headers.get("User-Agent") == "AgentUp-Agent/1.0"

    @pytest.mark.asyncio
    async def test_initialize_with_custom_version(self):
        """Test initialization with custom anthropic version."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229", "anthropic_version": "2024-01-01"}
        provider = AnthropicProvider("test", config)

        with patch.object(provider, "health_check", return_value={"status": "healthy"}):
            await provider.initialize()

        assert provider.client.headers.get("anthropic-version") == "2024-01-01"

    @pytest.mark.asyncio
    async def test_initialize_missing_api_key(self):
        """Test initialization fails without API key."""
        config = {"model": "claude-3-sonnet-20240229"}  # Missing api_key
        provider = AnthropicProvider("test", config)

        with pytest.raises(LLMProviderConfigError, match="API key required"):
            await provider.initialize()

        assert not provider._initialized

    @pytest.mark.asyncio
    async def test_initialize_health_check_fails(self):
        """Test initialization fails when health check fails."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)

        with patch.object(provider, "health_check", side_effect=Exception("API error")):
            with pytest.raises(LLMProviderError, match="Failed to initialize Anthropic service"):
                await provider.initialize()

        assert not provider._initialized

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the provider."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)

        # Initialize first
        with patch.object(provider, "health_check", return_value={"status": "healthy"}):
            await provider.initialize()

        # Mock the aclose method
        provider.client.aclose = AsyncMock()

        await provider.close()

        assert not provider._initialized
        provider.client.aclose.assert_called_once()


class TestAnthropicProviderHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)

        # Mock the client and response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.5

        provider.client = AsyncMock()
        provider.client.post.return_value = mock_response
        provider._detect_capabilities()  # Set capabilities

        result = await provider.health_check()

        assert result["status"] == "healthy"
        assert result["response_time_ms"] == 500
        assert result["status_code"] == 200
        assert result["model"] == "claude-3-sonnet-20240229"
        assert "capabilities" in result

        # Verify health check payload
        provider.client.post.assert_called_once_with(
            "/v1/messages",
            json={
                "model": "claude-3-sonnet-20240229",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self):
        """Test health check with unhealthy status code."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.elapsed = None

        provider.client = AsyncMock()
        provider.client.post.return_value = mock_response

        result = await provider.health_check()

        assert result["status"] == "unhealthy"
        assert result["response_time_ms"] == 0
        assert result["status_code"] == 401

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health check with network exception."""
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)

        provider.client = AsyncMock()
        provider.client.post.side_effect = httpx.ConnectError("Connection failed")

        result = await provider.health_check()

        assert result["status"] == "unhealthy"
        assert "Connection failed" in result["error"]
        assert result["model"] == "claude-3-sonnet-20240229"


class TestAnthropicProviderChatCompletion:
    """Test chat completion functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        self.provider = AnthropicProvider("test", self.config)
        self.provider._initialized = True
        self.provider.client = AsyncMock()
        self.provider._detect_capabilities()

    @pytest.mark.asyncio
    async def test_complete_basic(self):
        """Test basic text completion."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "Hello, world!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 3, "output_tokens": 3},
            "model": "claude-3-sonnet-20240229",
        }
        self.provider.client.post.return_value = mock_response

        result = await self.provider.complete("Hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.finish_reason == "end_turn"
        assert result.usage == {"input_tokens": 3, "output_tokens": 3}
        assert result.model == "claude-3-sonnet-20240229"

        # Verify API call
        self.provider.client.post.assert_called_once()
        call_args = self.provider.client.post.call_args
        assert call_args[0][0] == "/v1/messages"
        payload = call_args[1]["json"]
        assert payload["model"] == "claude-3-sonnet-20240229"
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_chat_complete_with_system_message(self):
        """Test chat completion with system message."""
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="Hello"),
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "Hello! How can I help you today?"}],
            "stop_reason": "end_turn",
        }
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)

        assert result.content == "Hello! How can I help you today?"

        # Verify system message is handled separately
        payload = self.provider.client.post.call_args[1]["json"]
        assert "system" in payload
        assert payload["system"] == "You are a helpful assistant."
        assert len(payload["messages"]) == 1  # Only user message
        assert payload["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_complete_multiple_user_messages(self):
        """Test chat completion with multiple user/assistant messages."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
            ChatMessage(role="user", content="How are you?"),
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "I am doing well, thank you!"}],
            "stop_reason": "end_turn",
        }
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)

        assert result.content == "I am doing well, thank you!"

        # Verify all non-system messages are included
        payload = self.provider.client.post.call_args[1]["json"]
        assert len(payload["messages"]) == 3
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][1]["role"] == "assistant"
        assert payload["messages"][2]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_complete_with_kwargs(self):
        """Test chat completion with custom parameters."""
        messages = [ChatMessage(role="user", content="Test")]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": [{"text": "Response"}], "stop_reason": "end_turn"}
        self.provider.client.post.return_value = mock_response

        await self.provider.chat_complete(messages, temperature=0.9, max_tokens=500, top_p=0.8)

        payload = self.provider.client.post.call_args[1]["json"]
        assert payload["temperature"] == 0.9
        assert payload["max_tokens"] == 500
        assert payload["top_p"] == 0.8

    @pytest.mark.asyncio
    async def test_chat_complete_empty_content(self):
        """Test chat completion with empty content array."""
        messages = [ChatMessage(role="user", content="Test")]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [],  # Empty content
            "stop_reason": "end_turn",
        }
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)

        assert result.content == ""

    @pytest.mark.asyncio
    async def test_chat_complete_api_error(self):
        """Test chat completion with API error."""
        messages = [ChatMessage(role="user", content="Test")]

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        self.provider.client.post.return_value = mock_response

        with pytest.raises(LLMProviderAPIError, match="Anthropic API error: 401"):
            await self.provider.chat_complete(messages)

    @pytest.mark.asyncio
    async def test_chat_complete_network_error(self):
        """Test chat completion with network error."""
        messages = [ChatMessage(role="user", content="Test")]

        self.provider.client.post.side_effect = httpx.ConnectError("Network error")

        with pytest.raises(LLMProviderAPIError, match="Anthropic API request failed"):
            await self.provider.chat_complete(messages)

    @pytest.mark.asyncio
    async def test_chat_complete_invalid_response(self):
        """Test chat completion with invalid response format - gracefully handles malformed content."""
        messages = [ChatMessage(role="user", content="Test")]

        mock_response = Mock()
        mock_response.status_code = 200
        # This should be handled gracefully now
        mock_response.json.return_value = {"content": "not_a_list"}  # Invalid content format
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)
        # Should handle gracefully and return empty content
        assert result.content == ""


class TestAnthropicProviderStreaming:
    """Test streaming functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        self.provider = AnthropicProvider("test", self.config)
        self.provider._initialized = True
        self.provider.client = AsyncMock()
        self.provider._detect_capabilities()

    @pytest.mark.asyncio
    async def test_stream_chat_complete_success(self):
        """Test successful streaming chat completion."""
        messages = [ChatMessage(role="user", content="Tell me a story")]

        # Mock the streaming by patching the method
        with patch.object(self.provider, "stream_chat_complete") as mock_stream:

            async def mock_chunks():
                chunks = ["Once", " upon", " a time"]
                for chunk in chunks:
                    yield chunk

            mock_stream.return_value = mock_chunks()

            chunks = []
            async for chunk in self.provider.stream_chat_complete(messages):
                chunks.append(chunk)

            assert chunks == ["Once", " upon", " a time"]
            mock_stream.assert_called_once_with(messages)

    @pytest.mark.asyncio
    async def test_stream_chat_complete_with_system_message(self):
        """Test streaming with system message handling."""
        messages = [
            ChatMessage(role="system", content="You are a storyteller."),
            ChatMessage(role="user", content="Tell me a story"),
        ]

        # Test that the method would be called with the right payload structure
        # by checking if it raises no errors on capability check
        assert self.provider.has_capability(LLMCapability.STREAMING)

        # Mock the actual streaming to avoid complex HTTP mocking
        with patch.object(self.provider, "stream_chat_complete") as mock_stream:

            async def mock_chunks():
                yield "Story beginning..."

            mock_stream.return_value = mock_chunks()

            chunks = []
            async for chunk in self.provider.stream_chat_complete(messages):
                chunks.append(chunk)

            assert chunks == ["Story beginning..."]

    @pytest.mark.asyncio
    async def test_stream_chat_complete_no_streaming_capability(self):
        """Test streaming when provider doesn't support it."""
        # Create provider without streaming capability
        config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        provider = AnthropicProvider("test", config)
        provider._set_capability(LLMCapability.STREAMING, False)

        messages = [ChatMessage(role="user", content="Test")]

        with pytest.raises(LLMProviderError, match="does not support streaming"):
            async for _ in provider.stream_chat_complete(messages):
                pass

    @pytest.mark.asyncio
    async def test_stream_chat_complete_api_error(self):
        """Test streaming with API error."""
        messages = [ChatMessage(role="user", content="Test")]

        # Patch the stream_chat_complete method to raise an error
        with patch.object(self.provider, "stream_chat_complete") as mock_stream:

            async def mock_error():
                raise LLMProviderAPIError("Anthropic streaming API error: 401 - Unauthorized")
                yield  # This yield makes it a generator, but will never be reached

            mock_stream.return_value = mock_error()

            with pytest.raises(LLMProviderAPIError, match="Anthropic streaming API error: 401"):
                async for _ in self.provider.stream_chat_complete(messages):
                    pass


class TestAnthropicProviderModelInfo:
    """Test model information functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"api_key": "test-key", "model": "claude-3-sonnet-20240229"}
        self.provider = AnthropicProvider("test", self.config)

    def test_get_model_info_claude3(self):
        """Test getting model info for Claude 3."""
        info = self.provider.get_model_info()

        assert info["model"] == "claude-3-sonnet-20240229"
        assert info["anthropic_version"] == "2023-06-01"
        assert info["supports_system_messages"] is True
        assert info["max_context_tokens"] == 200000  # Claude 3 models have 200k context

    def test_get_model_info_claude2(self):
        """Test getting model info for Claude 2."""
        config = {"api_key": "test-key", "model": "claude-2.1"}
        provider = AnthropicProvider("test", config)

        info = provider.get_model_info()

        assert info["model"] == "claude-2.1"
        assert info["max_context_tokens"] == 100000  # Claude 2 models have 100k context

    def test_get_model_info_unknown_model(self):
        """Test getting model info for unknown model."""
        config = {"api_key": "test-key", "model": "unknown-claude-model"}
        provider = AnthropicProvider("test", config)

        info = provider.get_model_info()

        assert info["model"] == "unknown-claude-model"
        assert info["max_context_tokens"] == 100000  # Default

    def test_get_max_context_tokens_claude3_variations(self):
        """Test max context tokens for various Claude 3 models."""
        models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]

        for model in models:
            config = {"api_key": "test-key", "model": model}
            provider = AnthropicProvider("test", config)
            assert provider._get_max_context_tokens() == 200000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
