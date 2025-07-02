import json
import logging
from pathlib import Path
from typing import Any

import httpx
import yaml

from ..constants import (
    DEFAULT_API_ENDPOINTS,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_MODELS,
    DEFAULT_USER_AGENT,
    MODEL_CAPABILITIES_FILE,
)
from .base import (
    BaseLLMService,
    ChatMessage,
    FunctionCall,
    LLMCapability,
    LLMProviderAPIError,
    LLMProviderConfigError,
    LLMProviderError,
    LLMResponse,
)

logger = logging.getLogger(__name__)


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

        # Load model capabilities from configuration file
        self._model_capabilities = self._load_model_capabilities()

    def _load_model_capabilities(self) -> dict[str, list[LLMCapability]]:
        """Load model capabilities from external configuration file."""
        try:
            if Path(MODEL_CAPABILITIES_FILE).exists():
                with open(MODEL_CAPABILITIES_FILE) as f:
                    capabilities_config = yaml.safe_load(f)

                openai_config = capabilities_config.get("openai", {})
                models_config = openai_config.get("models", {})

                # Convert string capabilities to LLMCapability enums
                capabilities_map = {}
                for model, caps in models_config.items():
                    model_caps = []
                    for cap in caps:
                        try:
                            # Try to get the capability by name
                            model_caps.append(LLMCapability(cap.lower()))
                        except ValueError:
                            logger.warning(f"Unknown capability '{cap}' for model {model}")
                    capabilities_map[model] = model_caps

                return capabilities_map
        except Exception as e:
            logger.warning(f"Failed to load model capabilities from {MODEL_CAPABILITIES_FILE}: {e}")

        # Fallback to basic capabilities
        return {
            "gpt-4": [LLMCapability.TEXT_COMPLETION, LLMCapability.CHAT_COMPLETION, LLMCapability.FUNCTION_CALLING],
            "gpt-3.5-turbo": [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.FUNCTION_CALLING,
            ],
        }

    async def initialize(self) -> None:
        """Initialize the OpenAI service."""
        if not self.api_key:
            logger.error(
                f"OpenAI service '{self.name}' initialization failed: API key not found. Check that 'api_key' is set in configuration and OPENAI_API_KEY environment variable is available."
            )
            raise LLMProviderConfigError(f"API key required for OpenAI service {self.name}")

        logger.info(f"Initializing OpenAI service '{self.name}' with model '{self.model}'")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }

        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=self.timeout)

        # Set capabilities based on model
        self._detect_capabilities()

        # Test connection
        try:
            await self.health_check()
            self._initialized = True
            logger.info(f"OpenAI service {self.name} initialized successfully")
            logger.info(f"Capabilities: {[cap.value for cap in self.get_capabilities()]}")
        except Exception as e:
            logger.error(f"OpenAI service {self.name} initialization failed: {e}")
            raise LLMProviderError(f"Failed to initialize OpenAI service: {e}") from e

    def _detect_capabilities(self):
        """Detect capabilities based on model."""
        model_key = self.model.lower()

        # Find matching capabilities
        capabilities = []
        for model_pattern, caps in self._model_capabilities.items():
            if model_pattern in model_key:
                capabilities = caps
                break

        # Default capabilities for unknown models
        if not capabilities:
            if "embed" in model_key:
                capabilities = [LLMCapability.EMBEDDINGS]
            else:
                capabilities = [
                    LLMCapability.TEXT_COMPLETION,
                    LLMCapability.CHAT_COMPLETION,
                    LLMCapability.SYSTEM_MESSAGES,
                ]

        # Set capabilities
        for cap in capabilities:
            self._set_capability(cap, True)

    async def close(self) -> None:
        """Close the OpenAI service."""
        if self.client:
            await self.client.aclose()
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        """Check OpenAI service health."""
        try:
            response = await self.client.get("/models")
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
                "status_code": response.status_code,
                "model": self.model,
                "capabilities": [cap.value for cap in self.get_capabilities()],
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

        # Add JSON mode if requested and supported
        if kwargs.get("response_format") == "json" and self.has_capability(LLMCapability.JSON_MODE):
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

        # Use embedding model if current model doesn't support embeddings
        embed_model = self.model
        if not self.has_capability(LLMCapability.EMBEDDINGS):
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
        """Convert ChatMessage to OpenAI format."""
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
        """Stream chat completion (if streaming is enabled)."""
        if not self.has_capability(LLMCapability.STREAMING):
            raise LLMProviderError(f"Provider {self.name} does not support streaming")

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
