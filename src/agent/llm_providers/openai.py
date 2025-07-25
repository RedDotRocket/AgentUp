import json
from typing import Any

import httpx
import structlog

from agent.config.constants import (
    DEFAULT_API_ENDPOINTS,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_MODELS,
    DEFAULT_USER_AGENT,
)

from .base import (
    BaseLLMService,
    ChatMessage,
    FunctionCall,
    LLMProviderAPIError,
    LLMProviderConfigError,
    LLMProviderError,
    LLMResponse,
)

logger = structlog.get_logger(__name__)


class OpenAIProvider(BaseLLMService):
    """OpenAI LLM provider with full function calling support."""

    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        self.client: httpx.AsyncClient | None = None
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", DEFAULT_MODELS["openai"])
        self.base_url = config.get("base_url", DEFAULT_API_ENDPOINTS["openai"])
        self.organization = config.get("organization")
        self.timeout = config.get("timeout", DEFAULT_HTTP_TIMEOUT)
        self._available = False  # Track availability status

    async def initialize(self) -> None:
        """Initialize the OpenAI service."""
        if not self.api_key:
            logger.error(
                f"OpenAI service '{self.name}' initialization failed: API key not found. Check that 'api_key' is set in configuration and OPENAI_API_KEY environment variable is available. Service will be unavailable."
            )
            self._available = False
            return

        logger.info(f"Initializing OpenAI service '{self.name}' with model '{self.model}'")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }

        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=self.timeout)

        # Test connection
        try:
            await self.health_check()
            self._initialized = True
            self._available = True
            logger.info(f"OpenAI service {self.name} initialized successfully")
        except Exception as e:
            logger.error(f"OpenAI service {self.name} initialization failed: {e}")
            self._available = False
            raise LLMProviderError(f"Failed to initialize OpenAI service: {e}") from e

    async def close(self) -> None:
        """Close the OpenAI service."""
        if self.client:
            await self.client.aclose()
        self._initialized = False
        self._available = False

    def is_available(self) -> bool:
        """Check if the OpenAI service is available for use."""
        return self._available

    async def health_check(self) -> dict[str, Any]:
        """Check OpenAI service health."""
        try:
            response = await self.client.get("/models")
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
                "status_code": response.status_code,
                "model": self.model,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "model": self.model}

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate completion from prompt using chat/completions endpoint."""
        if not self._initialized:
            await self.initialize()

        # Convert to chat format for consistency
        messages = [ChatMessage(role="user", content=prompt)]
        return await self.chat_complete(messages, **kwargs)

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        """Generate chat completion from messages."""
        if not self._initialized:
            await self.initialize()

        if not self._available:
            raise LLMProviderConfigError(f"OpenAI service '{self.name}' is not available. Check API key configuration.")

        # Prepare payload
        payload = {
            "model": self.model,
            "messages": [self._chat_message_to_dict(msg) for msg in messages],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0),
            "presence_penalty": kwargs.get("presence_penalty", 0),
        }

        # Add JSON mode if requested
        if kwargs.get("response_format") == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.post("/chat/completions", json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"OpenAI API error: {response.status_code} - {error_detail}")

            data = response.json()
            choice = data["choices"][0]

            return LLMResponse(
                content=choice["message"]["content"] or "",
                finish_reason=choice["finish_reason"],
                usage=data.get("usage"),
                model=data.get("model"),
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"OpenAI API request failed: {e}") from e
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid OpenAI API response format: {e}") from e

    async def _chat_complete_with_functions_native(
        self, messages: list[ChatMessage], functions: list[dict[str, Any]], **kwargs
    ) -> LLMResponse:
        """Native OpenAI function calling implementation."""
        if not self._initialized:
            await self.initialize()

        # Prepare payload with functions
        payload = {
            "model": self.model,
            "messages": [self._chat_message_to_dict(msg) for msg in messages],
            "functions": functions,
            "function_call": kwargs.get("function_call", "auto"),
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"OpenAI API error: {response.status_code} - {error_detail}")

            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]

            # Parse function calls
            function_calls = []
            if "function_call" in message:
                fc = message["function_call"]
                try:
                    # Parse function arguments safely
                    if isinstance(fc["arguments"], str):
                        # Try to parse JSON, handle malformed JSON gracefully
                        try:
                            arguments = json.loads(fc["arguments"])
                        except json.JSONDecodeError as e:
                            logger.warning(f"Malformed function arguments JSON: {fc['arguments']}")
                            logger.warning(f"JSON error: {e}")
                            # Try to fix common JSON issues
                            fixed_args = fc["arguments"].strip()
                            if not fixed_args.startswith("{"):
                                fixed_args = "{" + fixed_args
                            if not fixed_args.endswith("}"):
                                fixed_args = fixed_args + "}"
                            try:
                                arguments = json.loads(fixed_args)
                                logger.info(f"Fixed malformed JSON: {fixed_args}")
                            except json.JSONDecodeError:
                                # If still can't parse, use empty dict
                                logger.warning("Could not fix JSON, using empty arguments")
                                arguments = {}
                    else:
                        arguments = fc["arguments"]

                    function_calls.append(FunctionCall(name=fc["name"], arguments=arguments))
                except Exception as e:
                    logger.error(f"Error processing function call: {e}")
                    # Skip this function call if we can't process it
                    pass

            return LLMResponse(
                content=message.get("content", ""),
                finish_reason=choice["finish_reason"],
                usage=data.get("usage"),
                function_calls=function_calls if function_calls else None,
                model=data.get("model"),
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"OpenAI API request failed: {e}") from e
        except (KeyError, json.JSONDecodeError) as e:
            raise LLMProviderAPIError(f"Invalid OpenAI API response format: {e}") from e

    async def _embed_impl(self, text: str) -> list[float]:
        """Generate embeddings using OpenAI."""
        if not self._initialized:
            await self.initialize()

        # Use embedding model if current model doesn't look like an embedding model
        embed_model = self.model
        if "embed" not in self.model.lower():
            embed_model = "text-embedding-3-small"

        payload = {"model": embed_model, "input": text, "encoding_format": "float"}

        try:
            response = await self.client.post("/embeddings", json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"OpenAI embeddings API error: {response.status_code} - {error_detail}")

            data = response.json()
            return data["data"][0]["embedding"]

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"OpenAI embeddings API request failed: {e}") from e
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid OpenAI embeddings API response format: {e}") from e

    def _chat_message_to_dict(self, message: ChatMessage) -> dict[str, Any]:
        """Convert ChatMessage to OpenAI format, supporting vision inputs."""
        # Handle structured content for vision models
        if isinstance(message.content, list):
            # Multi-modal content (text + images)
            msg_dict = {"role": message.role, "content": message.content}
        else:
            # Simple text content
            msg_dict = {"role": message.role, "content": message.content}

        if message.function_call:
            msg_dict["function_call"] = {
                "name": message.function_call.name,
                "arguments": json.dumps(message.function_call.arguments),
            }

        if message.name:
            msg_dict["name"] = message.name

        return msg_dict

    async def stream_chat_complete(self, messages: list[ChatMessage], **kwargs):
        """Stream chat completion."""

        if not self._initialized:
            await self.initialize()

        payload = {
            "model": self.model,
            "messages": [self._chat_message_to_dict(msg) for msg in messages],
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }

        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    error_detail = await response.aread()
                    raise LLMProviderAPIError(f"OpenAI streaming API error: {response.status_code} - {error_detail}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choice = data["choices"][0]
                            delta = choice.get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue  # Skip invalid JSON lines

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"OpenAI streaming API request failed: {e}") from e
