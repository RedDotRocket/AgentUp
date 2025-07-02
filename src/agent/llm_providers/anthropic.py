"""Anthropic LLM provider implementation for {{ project_name }}."""

import json
import logging
from typing import Any

import httpx

from .base import (
    BaseLLMService,
    ChatMessage,
    LLMCapability,
    LLMProviderAPIError,
    LLMProviderConfigError,
    LLMProviderError,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMService):
    """Anthropic Claude LLM provider."""

    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        self.client: httpx.AsyncClient | None = None
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "claude-3-sonnet-20240229")
        self.base_url = config.get("base_url", "https://api.anthropic.com")
        self.timeout = config.get("timeout", 60.0)
        self.anthropic_version = config.get("anthropic_version", "2023-06-01")

        # Claude model capabilities
        self._model_capabilities = {
            "claude-3-opus": [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES,
                LLMCapability.IMAGE_UNDERSTANDING,
            ],
            "claude-3-sonnet": [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES,
                LLMCapability.IMAGE_UNDERSTANDING,
            ],
            "claude-3-haiku": [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES,
                LLMCapability.IMAGE_UNDERSTANDING,
            ],
            "claude-2": [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES,
            ],
        }

    async def initialize(self) -> None:
        """Initialize the Anthropic service."""
        if not self.api_key:
            logger.error(
                f"Anthropic service '{self.name}' initialization failed: API key not found. Check that 'api_key' is set in configuration and ANTHROPIC_API_KEY environment variable is available."
            )
            raise LLMProviderConfigError(f"API key required for Anthropic service {self.name}")

        logger.info(f"Initializing Anthropic service '{self.name}' with model '{self.model}'")

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": self.anthropic_version,
            "User-Agent": "AgentUp-Agent/1.0",
        }

        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=self.timeout)

        # Set capabilities based on model
        self._detect_capabilities()

        # Test connection
        try:
            await self.health_check()
            self._initialized = True
            logger.info(f"Anthropic service {self.name} initialized successfully")
            logger.info(f"Capabilities: {[cap.value for cap in self.get_capabilities()]}")
        except Exception as e:
            logger.error(f"Anthropic service {self.name} initialization failed: {e}")
            raise LLMProviderError(f"Failed to initialize Anthropic service: {e}") from e

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
            capabilities = [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES,
            ]

        # Set capabilities
        for cap in capabilities:
            self._set_capability(cap, True)

    async def close(self) -> None:
        """Close the Anthropic service."""
        if self.client:
            await self.client.aclose()
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        """Check Anthropic service health."""
        try:
            # Test with a simple message
            test_payload = {"model": self.model, "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]}

            response = await self.client.post("/v1/messages", json=test_payload)
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
        """Generate completion from prompt using messages endpoint."""
        if not self._initialized:
            await self.initialize()

        # Convert to chat format for consistency
        messages = [ChatMessage(role="user", content=prompt)]
        return await self.chat_complete(messages, **kwargs)

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        """Generate chat completion from messages."""
        if not self._initialized:
            await self.initialize()

        # Anthropic uses system parameter separately
        system_content = None
        user_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        # Prepare payload
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "messages": user_messages,
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
        }

        if system_content:
            payload["system"] = system_content

        try:
            response = await self.client.post("/v1/messages", json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"Anthropic API error: {response.status_code} - {error_detail}")

            data = response.json()

            # Anthropic returns content in a list format
            content = ""
            if data.get("content"):
                content_list = data["content"]
                if isinstance(content_list, list) and content_list:
                    content = content_list[0].get("text", "") if isinstance(content_list[0], dict) else ""
                else:
                    content = ""

            return LLMResponse(
                content=content,
                finish_reason=data.get("stop_reason", "stop"),
                usage=data.get("usage"),
                model=data.get("model"),
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Anthropic API request failed: {e}") from e
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid Anthropic API response format: {e}") from e

    async def stream_chat_complete(self, messages: list[ChatMessage], **kwargs):
        """Stream chat completion."""
        if not self.has_capability(LLMCapability.STREAMING):
            raise LLMProviderError(f"Provider {self.name} does not support streaming")

        if not self._initialized:
            await self.initialize()

        # Prepare messages like in chat_complete
        system_content = None
        user_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "messages": user_messages,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
        }

        if system_content:
            payload["system"] = system_content

        try:
            async with self.client.stream("POST", "/v1/messages", json=payload) as response:
                if response.status_code != 200:
                    error_detail = await response.aread()
                    raise LLMProviderAPIError(f"Anthropic streaming API error: {response.status_code} - {error_detail}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
                        except json.JSONDecodeError:
                            continue  # Skip invalid JSON lines

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Anthropic streaming API request failed: {e}") from e

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the model."""
        info = super().get_model_info()
        info.update(
            {
                "anthropic_version": self.anthropic_version,
                "supports_system_messages": True,
                "max_context_tokens": self._get_max_context_tokens(),
            }
        )
        return info

    def _get_max_context_tokens(self) -> int:
        """Get max context tokens for the model."""
        if "claude-3" in self.model:
            return 200000  # Claude 3 models have 200k context
        elif "claude-2" in self.model:
            return 100000  # Claude 2 models have 100k context
        else:
            return 100000  # Default
