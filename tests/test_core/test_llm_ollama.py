# Add src to path for imports
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.llm_providers.base import ChatMessage, LLMCapability, LLMProviderAPIError, LLMProviderError, LLMResponse
from agent.llm_providers.ollama import OllamaProvider


class TestOllamaProviderInitialization:
    """Test Ollama provider initialization."""

    def test_init_basic_config(self):
        """Test basic initialization with minimal config."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test-ollama", config)

        assert provider.name == "test-ollama"
        assert provider.model == "llama2"
        assert provider.base_url == "http://localhost:11434"
        assert provider.timeout == 120.0
        assert provider.client is None
        assert not provider._initialized

    def test_init_full_config(self):
        """Test initialization with all configuration options."""
        config = {"model": "mistral", "base_url": "http://custom-ollama:11434", "timeout": 180.0}
        provider = OllamaProvider("custom-ollama", config)

        assert provider.model == "mistral"
        assert provider.base_url == "http://custom-ollama:11434"
        assert provider.timeout == 180.0

    def test_init_default_values(self):
        """Test initialization with missing config values uses defaults."""
        config = {}
        provider = OllamaProvider("default-ollama", config)

        assert provider.model == "llama2"
        assert provider.base_url == "http://localhost:11434"
        assert provider.timeout == 120.0


class TestOllamaProviderCapabilities:
    """Test capability detection and management."""

    def test_detect_capabilities_llama2(self):
        """Test capability detection for Llama2."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)
        provider._detect_capabilities()

        expected_caps = [
            LLMCapability.TEXT_COMPLETION,
            LLMCapability.CHAT_COMPLETION,
            LLMCapability.STREAMING,
            LLMCapability.SYSTEM_MESSAGES,
        ]

        for cap in expected_caps:
            assert provider.has_capability(cap), f"Missing capability: {cap}"

        # Ollama typically doesn't support function calling natively
        assert not provider.has_capability(LLMCapability.FUNCTION_CALLING)

    def test_detect_capabilities_llama3(self):
        """Test capability detection for Llama3."""
        config = {"model": "llama3"}
        provider = OllamaProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)
        assert provider.has_capability(LLMCapability.CHAT_COMPLETION)

    def test_detect_capabilities_mistral(self):
        """Test capability detection for Mistral."""
        config = {"model": "mistral:7b"}
        provider = OllamaProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)
        assert provider.has_capability(LLMCapability.CHAT_COMPLETION)

    def test_detect_capabilities_codellama(self):
        """Test capability detection for CodeLlama."""
        config = {"model": "codellama:13b"}
        provider = OllamaProvider("test", config)
        provider._detect_capabilities()

        assert provider.has_capability(LLMCapability.TEXT_COMPLETION)
        assert provider.has_capability(LLMCapability.CHAT_COMPLETION)
        assert provider.has_capability(LLMCapability.STREAMING)

    def test_detect_capabilities_unknown_model(self):
        """Test capability detection for unknown models."""
        config = {"model": "unknown-custom-model"}
        provider = OllamaProvider("test", config)
        provider._detect_capabilities()

        # Should get default capabilities
        assert provider.has_capability(LLMCapability.TEXT_COMPLETION)
        assert provider.has_capability(LLMCapability.CHAT_COMPLETION)
        assert provider.has_capability(LLMCapability.STREAMING)
        assert provider.has_capability(LLMCapability.SYSTEM_MESSAGES)
        assert not provider.has_capability(LLMCapability.FUNCTION_CALLING)


class TestOllamaProviderServiceManagement:
    """Test service lifecycle management."""

    @pytest.mark.asyncio
    async def test_initialize_success_model_exists(self):
        """Test successful initialization when model exists."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        # Mock model availability check and health check
        with (
            patch.object(provider, "_ensure_model_available") as mock_ensure,
            patch.object(provider, "health_check", return_value={"status": "healthy"}) as mock_health,
        ):
            await provider.initialize()

        assert provider._initialized
        assert provider.client is not None
        assert isinstance(provider.client, httpx.AsyncClient)
        assert str(provider.client.base_url) == "http://localhost:11434"

        # Check headers
        assert provider.client.headers.get("Content-Type") == "application/json"
        assert provider.client.headers.get("User-Agent") == "AgentUp-Agent/1.0"

        mock_ensure.assert_called_once()
        mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        config = {"model": "mistral", "base_url": "http://custom-ollama:11434"}
        provider = OllamaProvider("test", config)

        with (
            patch.object(provider, "_ensure_model_available"),
            patch.object(provider, "health_check", return_value={"status": "healthy"}),
        ):
            await provider.initialize()

        assert str(provider.client.base_url) == "http://custom-ollama:11434"

    @pytest.mark.asyncio
    async def test_initialize_model_check_fails(self):
        """Test initialization fails when model check fails."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        with patch.object(provider, "_ensure_model_available", side_effect=Exception("Model check failed")):
            with pytest.raises(LLMProviderError, match="Failed to initialize Ollama service"):
                await provider.initialize()

        assert not provider._initialized

    @pytest.mark.asyncio
    async def test_initialize_health_check_fails(self):
        """Test initialization fails when health check fails."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        with (
            patch.object(provider, "_ensure_model_available"),
            patch.object(provider, "health_check", side_effect=Exception("Health check failed")),
        ):
            with pytest.raises(LLMProviderError, match="Failed to initialize Ollama service"):
                await provider.initialize()

        assert not provider._initialized

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the provider."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        # Initialize first
        with (
            patch.object(provider, "_ensure_model_available"),
            patch.object(provider, "health_check", return_value={"status": "healthy"}),
        ):
            await provider.initialize()

        # Mock the aclose method
        provider.client.aclose = AsyncMock()

        await provider.close()

        assert not provider._initialized
        provider.client.aclose.assert_called_once()


class TestOllamaProviderModelManagement:
    """Test model availability and pulling functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"model": "llama2"}
        self.provider = OllamaProvider("test", self.config)
        self.provider.client = AsyncMock()

    @pytest.mark.asyncio
    async def test_ensure_model_available_exists(self):
        """Test model availability check when model exists."""
        # Mock response showing model exists
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama2:latest"}, {"name": "mistral:7b"}]}
        self.provider.client.get.return_value = mock_response

        await self.provider._ensure_model_available()

        # Should not try to pull model
        self.provider.client.get.assert_called_once_with("/api/tags")
        self.provider.client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_model_available_needs_pull(self):
        """Test model availability check when model needs to be pulled."""
        # Mock response showing model doesn't exist
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "mistral:7b"}  # llama2 not in list
            ]
        }
        self.provider.client.get.return_value = mock_response

        # Mock pull response
        mock_pull_response = Mock()
        mock_pull_response.status_code = 200
        self.provider.client.post.return_value = mock_pull_response

        await self.provider._ensure_model_available()

        # Should check models and then pull
        self.provider.client.get.assert_called_once_with("/api/tags")
        self.provider.client.post.assert_called_once_with("/api/pull", json={"name": "llama2"})

    @pytest.mark.asyncio
    async def test_ensure_model_available_api_error(self):
        """Test model availability check with API error."""
        mock_response = Mock()
        mock_response.status_code = 500
        self.provider.client.get.return_value = mock_response

        with pytest.raises(LLMProviderAPIError, match="Failed to check Ollama models"):
            await self.provider._ensure_model_available()

    @pytest.mark.asyncio
    async def test_ensure_model_available_connection_error(self):
        """Test model availability check with connection error."""
        self.provider.client.get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(LLMProviderAPIError, match="Failed to connect to Ollama"):
            await self.provider._ensure_model_available()

    @pytest.mark.asyncio
    async def test_pull_model_success(self):
        """Test successful model pulling."""
        mock_response = Mock()
        mock_response.status_code = 200
        self.provider.client.post.return_value = mock_response

        await self.provider._pull_model()

        self.provider.client.post.assert_called_once_with("/api/pull", json={"name": "llama2"})

    @pytest.mark.asyncio
    async def test_pull_model_api_error(self):
        """Test model pulling with API error."""
        mock_response = Mock()
        mock_response.status_code = 404
        self.provider.client.post.return_value = mock_response

        with pytest.raises(LLMProviderAPIError, match="Failed to pull model"):
            await self.provider._pull_model()

    @pytest.mark.asyncio
    async def test_pull_model_network_error(self):
        """Test model pulling with network error."""
        self.provider.client.post.side_effect = httpx.ConnectError("Network error")

        with pytest.raises(LLMProviderAPIError, match="Failed to pull model"):
            await self.provider._pull_model()


class TestOllamaProviderHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        # Mock the client and response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.8

        provider.client = AsyncMock()
        provider.client.post.return_value = mock_response
        provider._detect_capabilities()  # Set capabilities

        result = await provider.health_check()

        assert result["status"] == "healthy"
        assert result["response_time_ms"] == 800
        assert result["status_code"] == 200
        assert result["model"] == "llama2"
        assert "capabilities" in result

        # Verify health check payload
        provider.client.post.assert_called_once_with(
            "/api/generate", json={"model": "llama2", "prompt": "Test", "stream": False}
        )

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self):
        """Test health check with unhealthy status code."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.elapsed = None

        provider.client = AsyncMock()
        provider.client.post.return_value = mock_response

        result = await provider.health_check()

        assert result["status"] == "unhealthy"
        assert result["response_time_ms"] == 0
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health check with exception."""
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)

        provider.client = AsyncMock()
        provider.client.post.side_effect = httpx.ConnectError("Connection failed")

        result = await provider.health_check()

        assert result["status"] == "unhealthy"
        assert "Connection failed" in result["error"]
        assert result["model"] == "llama2"


class TestOllamaProviderTextCompletion:
    """Test text completion functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"model": "llama2"}
        self.provider = OllamaProvider("test", self.config)
        self.provider._initialized = True
        self.provider.client = AsyncMock()
        self.provider._detect_capabilities()

    @pytest.mark.asyncio
    async def test_complete_basic(self):
        """Test basic text completion."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Hello, world!", "done": True}
        self.provider.client.post.return_value = mock_response

        result = await self.provider.complete("Hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.finish_reason == "stop"
        assert result.model == "llama2"

        # Verify API call
        self.provider.client.post.assert_called_once()
        call_args = self.provider.client.post.call_args
        assert call_args[0][0] == "/api/generate"
        payload = call_args[1]["json"]
        assert payload["model"] == "llama2"
        assert payload["prompt"] == "Hello"
        assert payload["stream"] is False

    @pytest.mark.asyncio
    async def test_complete_with_kwargs(self):
        """Test text completion with custom parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Response", "done": True}
        self.provider.client.post.return_value = mock_response

        await self.provider.complete("Test", temperature=0.9, max_tokens=500, top_p=0.8, top_k=30)

        payload = self.provider.client.post.call_args[1]["json"]
        options = payload["options"]
        assert options["temperature"] == 0.9
        assert options["num_predict"] == 500
        assert options["top_p"] == 0.8
        assert options["top_k"] == 30

    @pytest.mark.asyncio
    async def test_complete_not_done(self):
        """Test completion with done=False."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Partial response", "done": False}
        self.provider.client.post.return_value = mock_response

        result = await self.provider.complete("Test")

        assert result.content == "Partial response"
        assert result.finish_reason == "length"

    @pytest.mark.asyncio
    async def test_complete_api_error(self):
        """Test completion with API error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        self.provider.client.post.return_value = mock_response

        with pytest.raises(LLMProviderAPIError, match="Ollama API error: 500"):
            await self.provider.complete("Test")

    @pytest.mark.asyncio
    async def test_complete_network_error(self):
        """Test completion with network error."""
        self.provider.client.post.side_effect = httpx.ConnectError("Network error")

        with pytest.raises(LLMProviderAPIError, match="Ollama API request failed"):
            await self.provider.complete("Test")


class TestOllamaProviderChatCompletion:
    """Test chat completion functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"model": "llama2"}
        self.provider = OllamaProvider("test", self.config)
        self.provider._initialized = True
        self.provider.client = AsyncMock()
        self.provider._detect_capabilities()

    @pytest.mark.asyncio
    async def test_chat_complete_basic(self):
        """Test basic chat completion."""
        messages = [ChatMessage(role="user", content="Hello")]

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Hello, how can I help you?"}, "done": True}
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, how can I help you?"
        assert result.finish_reason == "stop"
        assert result.model == "llama2"

        # Verify API call
        self.provider.client.post.assert_called_once()
        call_args = self.provider.client.post.call_args
        assert call_args[0][0] == "/api/chat"
        payload = call_args[1]["json"]
        assert payload["model"] == "llama2"
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_chat_complete_multiple_messages(self):
        """Test chat completion with multiple messages."""
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
            ChatMessage(role="user", content="How are you?"),
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "I am doing well, thank you!"}, "done": True}
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)

        assert result.content == "I am doing well, thank you!"

        # Verify all messages were sent (including system message)
        payload = self.provider.client.post.call_args[1]["json"]
        assert len(payload["messages"]) == 4
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][2]["role"] == "assistant"
        assert payload["messages"][3]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_complete_empty_message_content(self):
        """Test chat completion with empty message content."""
        messages = [ChatMessage(role="user", content="Test")]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {},  # No content
            "done": True,
        }
        self.provider.client.post.return_value = mock_response

        result = await self.provider.chat_complete(messages)

        assert result.content == ""

    @pytest.mark.asyncio
    async def test_chat_complete_api_error(self):
        """Test chat completion with API error."""
        messages = [ChatMessage(role="user", content="Test")]

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        self.provider.client.post.return_value = mock_response

        with pytest.raises(LLMProviderAPIError, match="Ollama chat API error: 400"):
            await self.provider.chat_complete(messages)


class TestOllamaProviderStreaming:
    """Test streaming functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"model": "llama2"}
        self.provider = OllamaProvider("test", self.config)
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
    async def test_stream_chat_complete_no_streaming_capability(self):
        """Test streaming when provider doesn't support it."""
        # Create provider without streaming capability
        config = {"model": "llama2"}
        provider = OllamaProvider("test", config)
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
                raise LLMProviderAPIError("Ollama streaming API error: 500 - Server Error")
                yield  # This yield makes it a generator, but will never be reached

            mock_stream.return_value = mock_error()

            with pytest.raises(LLMProviderAPIError, match="Ollama streaming API error: 500"):
                async for _ in self.provider.stream_chat_complete(messages):
                    pass


class TestOllamaProviderUtilities:
    """Test utility functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"model": "llama2"}
        self.provider = OllamaProvider("test", self.config)
        self.provider._initialized = True
        self.provider.client = AsyncMock()

    @pytest.mark.asyncio
    async def test_get_available_models_success(self):
        """Test getting available models."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama2:latest", "size": 3825819519}, {"name": "mistral:7b", "size": 4109906704}]
        }
        self.provider.client.get.return_value = mock_response

        models = await self.provider.get_available_models()

        assert len(models) == 2
        assert models[0]["name"] == "llama2:latest"
        assert models[1]["name"] == "mistral:7b"

        self.provider.client.get.assert_called_once_with("/api/tags")

    @pytest.mark.asyncio
    async def test_get_available_models_api_error(self):
        """Test getting available models with API error."""
        mock_response = Mock()
        mock_response.status_code = 500
        self.provider.client.get.return_value = mock_response

        with pytest.raises(LLMProviderAPIError, match="Failed to get models"):
            await self.provider.get_available_models()

    @pytest.mark.asyncio
    async def test_get_available_models_network_error(self):
        """Test getting available models with network error."""
        self.provider.client.get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(LLMProviderAPIError, match="Failed to get available models"):
            await self.provider.get_available_models()

    def test_get_model_info(self):
        """Test getting model information."""
        info = self.provider.get_model_info()

        assert info["model"] == "llama2"
        assert info["base_url"] == "http://localhost:11434"
        assert info["local_inference"] is True
        assert info["supports_pull"] is True

    def test_get_model_info_with_custom_config(self):
        """Test getting model info with custom configuration."""
        config = {"model": "mistral:7b", "base_url": "http://custom-ollama:11434"}
        provider = OllamaProvider("test", config)

        info = provider.get_model_info()

        assert info["model"] == "mistral:7b"
        assert info["base_url"] == "http://custom-ollama:11434"
        assert info["local_inference"] is True
        assert info["supports_pull"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
