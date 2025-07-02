import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.llm_providers.base import BaseLLMService, ChatMessage, FunctionCall, LLMCapability, LLMResponse


class TestLLMResponse:
    """Test the LLMResponse data class."""

    def test_llm_response_initialization(self):
        """Test LLMResponse initialization with all fields."""
        function_call_dict = {"name": "test_function", "arguments": {"arg1": "value1"}, "call_id": "call_123"}

        response = LLMResponse(
            content="Test response",
            finish_reason="stop",
            usage={"input_tokens": 10, "output_tokens": 20},
            function_calls=[function_call_dict],
            model="gpt-4",
        )

        assert response.content == "Test response"
        assert response.finish_reason == "stop"
        assert response.usage == {"input_tokens": 10, "output_tokens": 20}
        assert len(response.function_calls) == 1
        assert response.function_calls[0]["name"] == "test_function"
        assert response.model == "gpt-4"

    def test_llm_response_minimal(self):
        """Test LLMResponse with minimal required fields."""
        response = LLMResponse(content="Minimal response", finish_reason="stop")

        assert response.content == "Minimal response"
        assert response.finish_reason == "stop"
        assert response.usage is None
        assert response.function_calls is None
        assert response.model is None

    def test_llm_response_empty_function_calls(self):
        """Test LLMResponse with empty function_calls list."""
        response = LLMResponse(content="No functions", finish_reason="stop", function_calls=[])

        assert response.function_calls == []

    def test_llm_response_default_finish_reason(self):
        """Test LLMResponse with default finish_reason."""
        response = LLMResponse(content="Test")

        assert response.content == "Test"
        assert response.finish_reason == "stop"


class TestFunctionCall:
    """Test the FunctionCall data class."""

    def test_function_call_initialization(self):
        """Test FunctionCall initialization."""
        function_call = FunctionCall(name="calculate_sum", arguments={"a": 5, "b": 10}, call_id="call_abc123")

        assert function_call.name == "calculate_sum"
        assert function_call.arguments == {"a": 5, "b": 10}
        assert function_call.call_id == "call_abc123"

    def test_function_call_without_call_id(self):
        """Test FunctionCall without call_id."""
        function_call = FunctionCall(name="get_weather", arguments={"location": "New York"})

        assert function_call.name == "get_weather"
        assert function_call.arguments == {"location": "New York"}
        assert function_call.call_id is None

    def test_function_call_empty_arguments(self):
        """Test FunctionCall with empty arguments."""
        function_call = FunctionCall(name="no_args_function", arguments={})

        assert function_call.name == "no_args_function"
        assert function_call.arguments == {}


class TestChatMessage:
    """Test the ChatMessage data class."""

    def test_chat_message_user(self):
        """Test ChatMessage for user role."""
        message = ChatMessage(role="user", content="Hello, how are you?")

        assert message.role == "user"
        assert message.content == "Hello, how are you?"
        assert message.function_call is None
        assert message.function_calls is None
        assert message.name is None

    def test_chat_message_assistant_with_function_call(self):
        """Test ChatMessage for assistant with function call."""
        function_call = FunctionCall(name="get_weather", arguments={"location": "San Francisco"})

        message = ChatMessage(
            role="assistant", content="I'll check the weather for you.", function_calls=[function_call]
        )

        assert message.role == "assistant"
        assert message.content == "I'll check the weather for you."
        assert len(message.function_calls) == 1
        assert message.function_calls[0].name == "get_weather"

    def test_chat_message_function_result(self):
        """Test ChatMessage for function result."""
        message = ChatMessage(role="function", content='{"temperature": 72, "condition": "sunny"}', name="get_weather")

        assert message.role == "function"
        assert message.content == '{"temperature": 72, "condition": "sunny"}'
        assert message.name == "get_weather"

    def test_chat_message_system(self):
        """Test ChatMessage for system role."""
        message = ChatMessage(role="system", content="You are a helpful assistant.")

        assert message.role == "system"
        assert message.content == "You are a helpful assistant."


class TestLLMCapability:
    """Test the LLMCapability enum."""

    def test_llm_capability_values(self):
        """Test LLMCapability enum values."""
        assert LLMCapability.FUNCTION_CALLING.value == "function_calling"
        assert LLMCapability.STREAMING.value == "streaming"
        assert LLMCapability.EMBEDDINGS.value == "embeddings"
        assert LLMCapability.JSON_MODE.value == "json_mode"
        assert LLMCapability.TEXT_COMPLETION.value == "text_completion"
        assert LLMCapability.CHAT_COMPLETION.value == "chat_completion"
        assert LLMCapability.IMAGE_UNDERSTANDING.value == "image_understanding"
        assert LLMCapability.SYSTEM_MESSAGES.value == "system_messages"

    def test_llm_capability_enumeration(self):
        """Test enumerating all capabilities."""
        capabilities = list(LLMCapability)
        assert len(capabilities) >= 8
        assert LLMCapability.FUNCTION_CALLING in capabilities
        assert LLMCapability.STREAMING in capabilities


class TestBaseLLMService:
    """Test the BaseLLMService abstract base class."""

    def test_base_llm_service_initialization(self):
        """Test BaseLLMService initialization."""
        config = {"model": "test-model", "api_key": "test-key", "base_url": "https://api.test.com"}

        # Create a concrete implementation for testing
        class ConcreteService(BaseLLMService):
            async def initialize(self):
                self._initialized = True

            async def close(self):
                self._initialized = False

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", config)

        assert service.name == "test_service"
        assert service.config == config
        assert service._capabilities == {}
        assert service._initialized is False

    def test_base_llm_service_default_config(self):
        """Test BaseLLMService with minimal config."""
        config = {}

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                self._initialized = True

            async def close(self):
                self._initialized = False

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", config)

        assert service.name == "test_service"
        assert service.config == config

    def test_base_llm_service_abstract_methods(self):
        """Test that abstract methods raise NotImplementedError."""
        # Trying to instantiate BaseLLMService directly should fail
        with pytest.raises(TypeError):
            BaseLLMService("test", {})

    def test_has_capability(self):
        """Test has_capability method."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", {})

        # Initially no capabilities
        assert not service.has_capability(LLMCapability.FUNCTION_CALLING)
        assert not service.has_capability(LLMCapability.STREAMING)

        # Add capabilities
        service._set_capability(LLMCapability.FUNCTION_CALLING, True)
        assert service.has_capability(LLMCapability.FUNCTION_CALLING)
        assert not service.has_capability(LLMCapability.STREAMING)

    def test_set_capability(self):
        """Test setting capabilities for service."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", {})

        # Set single capability
        service._set_capability(LLMCapability.FUNCTION_CALLING, True)
        assert service.has_capability(LLMCapability.FUNCTION_CALLING)

        # Set multiple capabilities
        service._set_capability(LLMCapability.STREAMING, True)
        service._set_capability(LLMCapability.EMBEDDINGS, True)
        assert service.has_capability(LLMCapability.STREAMING)
        assert service.has_capability(LLMCapability.EMBEDDINGS)

        # Disable capability
        service._set_capability(LLMCapability.FUNCTION_CALLING, False)
        assert not service.has_capability(LLMCapability.FUNCTION_CALLING)

    def test_get_capabilities(self):
        """Test getting list of capabilities."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", {})

        # Initially no capabilities
        assert service.get_capabilities() == []

        # Add capabilities
        service._set_capability(LLMCapability.FUNCTION_CALLING, True)
        service._set_capability(LLMCapability.STREAMING, True)
        capabilities = service.get_capabilities()

        assert len(capabilities) == 2
        assert LLMCapability.FUNCTION_CALLING in capabilities
        assert LLMCapability.STREAMING in capabilities

    @pytest.mark.asyncio
    async def test_embed_not_supported(self):
        """Test embed method when embeddings not supported."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", {})

        with pytest.raises(NotImplementedError):
            await service.embed("test text")

    @pytest.mark.asyncio
    async def test_embed_supported_but_not_implemented(self):
        """Test embed method when embeddings supported but not implemented."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", {})
        service._set_capability(LLMCapability.EMBEDDINGS, True)

        with pytest.raises(NotImplementedError):
            await service.embed("test text")

    @pytest.mark.asyncio
    async def test_chat_complete_with_functions_native(self):
        """Test chat completion with native function calling."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def _chat_complete_with_functions_native(self, messages, functions, **kwargs):
                return LLMResponse(
                    content="Function call response",
                    finish_reason="function_call",
                    function_calls=[{"name": "test_function", "arguments": {}}],
                )

        service = ConcreteService("test_service", {})
        service._set_capability(LLMCapability.FUNCTION_CALLING, True)

        messages = [ChatMessage(role="user", content="Test")]
        functions = [{"name": "test_function", "description": "Test"}]

        response = await service.chat_complete_with_functions(messages, functions)

        assert response.content == "Function call response"
        assert response.finish_reason == "function_call"

    @pytest.mark.asyncio
    async def test_chat_complete_with_functions_prompt_fallback(self):
        """Test chat completion with prompt-based function calling fallback."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                # Return response that looks like function call
                return LLMResponse(
                    content='FUNCTION_CALL: test_function(param="value")\nHere\'s the result.', finish_reason="stop"
                )

        service = ConcreteService("test_service", {})
        # Don't set function calling capability to trigger fallback

        messages = [ChatMessage(role="user", content="Test")]
        functions = [{"name": "test_function", "description": "Test function"}]

        response = await service.chat_complete_with_functions(messages, functions)

        assert "FUNCTION_CALL:" in response.content
        # Function calls should be parsed from the response
        assert response.function_calls is not None

    def test_parse_function_calls(self):
        """Test parsing function calls from text."""

        class ConcreteService(BaseLLMService):
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return LLMResponse(content="test", finish_reason="stop")

        service = ConcreteService("test_service", {})

        content = """I'll help you with that.
FUNCTION_CALL: get_weather(location="New York")
FUNCTION_CALL: get_time(timezone="EST")
Here are the results."""

        function_calls = service._parse_function_calls(content)

        assert len(function_calls) == 2
        assert function_calls[0].name == "get_weather"
        assert function_calls[1].name == "get_time"


class TestLLMServiceIntegration:
    """Test integration scenarios for LLM services."""

    @pytest.mark.asyncio
    async def test_complete_with_function_calls(self):
        """Test complete method with function calling capability."""

        class MockService(BaseLLMService):
            def __init__(self, name, config):
                super().__init__(name, config)
                self._set_capability(LLMCapability.FUNCTION_CALLING, True)

            async def initialize(self):
                self._initialized = True

            async def close(self):
                self._initialized = False

            async def health_check(self):
                return {"status": "healthy"}

            async def complete(self, prompt, **kwargs):
                if kwargs.get("functions"):
                    return LLMResponse(
                        content="I'll help you with that.",
                        finish_reason="function_call",
                        function_calls=[{"name": "test_function", "arguments": {"param": "value"}}],
                    )
                return LLMResponse(content="Simple response", finish_reason="stop")

            async def chat_complete(self, messages, **kwargs):
                return await self.complete("", **kwargs)

        service = MockService("test", {})
        await service.initialize()

        # Test with functions
        functions = [{"name": "test_function", "description": "Test"}]
        response = await service.complete("Test prompt", functions=functions)

        assert response.finish_reason == "function_call"
        assert len(response.function_calls) == 1
        assert response.function_calls[0]["name"] == "test_function"

        # Test without functions
        response = await service.complete("Test prompt")
        assert response.content == "Simple response"
        assert response.finish_reason == "stop"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
