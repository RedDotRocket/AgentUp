import json
from typing import Any

import httpx
import structlog

from .base import (
    BaseLLMService,
    ChatMessage,
    LLMProviderAPIError,
    LLMProviderError,
    LLMResponse,
)

logger = structlog.get_logger(__name__)


class OllamaProvider(BaseLLMService):
    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        self.client: httpx.AsyncClient | None = None
        self.model = config.get("model", "llama2")
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.timeout = config.get("timeout", 120.0)  # Longer timeout for local models

    async def initialize(self) -> None:
        logger.info(f"Initializing Ollama service '{self.name}' with model '{self.model}'")

        headers = {"Content-Type": "application/json", "User-Agent": "AgentUp-Agent/1.0"}

        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=self.timeout)

        # Test connection and model availability
        try:
            await self._ensure_model_available()
            await self.health_check()
            self._initialized = True
            logger.info(f"Ollama service {self.name} initialized successfully")
        except Exception as e:
            logger.error(f"Ollama service {self.name} initialization failed: {e}")
            raise LLMProviderError(f"Failed to initialize Ollama service: {e}") from e


    async def _ensure_model_available(self):
        """Ensure the model is available, pull if necessary."""
        try:
            # Check if model exists
            response = await self.client.get("/api/tags")
            if response.status_code != 200:
                raise LLMProviderAPIError(f"Failed to check Ollama models: {response.status_code}")

            data = response.json()
            model_names = [model["name"].split(":")[0] for model in data.get("models", [])]

            if self.model not in model_names:
                logger.info(f"Model {self.model} not found locally, attempting to pull...")
                await self._pull_model()

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Failed to connect to Ollama: {e}") from e

    async def _pull_model(self):
        """Pull model from Ollama registry."""
        payload = {"name": self.model}

        try:
            response = await self.client.post("/api/pull", json=payload)
            if response.status_code != 200:
                raise LLMProviderAPIError(f"Failed to pull model {self.model}: {response.status_code}")

            logger.info(f"Successfully pulled model {self.model}")

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Failed to pull model {self.model}: {e}") from e

    async def close(self) -> None:
        """Close the Ollama service."""
        if self.client:
            await self.client.aclose()
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        """Check Ollama service health."""
        try:
            # Test with a simple generation
            response = await self.client.post(
                "/api/generate", json={"model": self.model, "prompt": "Test", "stream": False}
            )

            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
                "status_code": response.status_code,
                "model": self.model,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "model": self.model}

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate completion from prompt."""
        if not self._initialized:
            await self.initialize()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1.0),
                "top_k": kwargs.get("top_k", 40),
                "num_predict": kwargs.get("max_tokens", 1000),
            },
        }

        try:
            response = await self.client.post("/api/generate", json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"Ollama API error: {response.status_code} - {error_detail}")

            data = response.json()

            return LLMResponse(
                content=data.get("response", ""),
                finish_reason="stop" if data.get("done", False) else "length",
                model=self.model,
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Ollama API request failed: {e}") from e
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid Ollama API response format: {e}") from e

    def _is_vision_model(self) -> bool:
        """Check if the current model supports vision."""
        vision_models = ["llava", "bakllava", "llava-llama3", "llava-phi3", "llava-code"]
        return any(vision_model in self.model.lower() for vision_model in vision_models)

    def _flatten_content_for_ollama(self, content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        """Handle multi-modal content for Ollama, preserving structure for vision models."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            # If this is a vision model, preserve the structure
            if self._is_vision_model():
                return content

            # For text-only models, extract text parts and handle images appropriately
            text_parts = []
            for part in content:
                if part.get("type") == "text":
                    text_content = part.get("text", "")
                    # Check if this is file content (has document markers)
                    if "--- Content of" in text_content and "---" in text_content:
                        # This is extracted document content, include it directly
                        text_parts.append(text_content)
                    else:
                        # Regular text content
                        text_parts.append(text_content)
                elif part.get("type") == "image_url":
                    # Text-only models can't process images
                    text_parts.append(
                        "[Image attached - This model cannot process images directly. Please describe the image contents.]"
                    )

            return " ".join(text_parts)

        return str(content)

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        """Generate chat completion from messages."""
        if not self._initialized:
            await self.initialize()

        # Convert messages to Ollama chat format
        ollama_messages = []
        for msg in messages:
            # Handle multi-modal content appropriately
            content = self._flatten_content_for_ollama(msg.content)

            # For vision models with structured content, handle images
            if self._is_vision_model() and isinstance(content, list):
                # Ollama vision models expect images as base64 data
                text_content = ""
                images = []

                for part in content:
                    if part.get("type") == "text":
                        text_content += part.get("text", "")
                    elif part.get("type") == "image_url":
                        image_url = part.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:"):
                            # Extract base64 data from data URL
                            _, base64_data = image_url.split(",", 1)
                            images.append(base64_data)

                # Build message with proper Ollama format
                ollama_msg = {"role": msg.role, "content": text_content}
                if images:
                    ollama_msg["images"] = images

                ollama_messages.append(ollama_msg)
            else:
                ollama_messages.append({"role": msg.role, "content": content})

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1.0),
                "top_k": kwargs.get("top_k", 40),
                "num_predict": kwargs.get("max_tokens", 1000),
            },
        }

        try:
            response = await self.client.post("/api/chat", json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"Ollama chat API error: {response.status_code} - {error_detail}")

            data = response.json()
            message = data.get("message", {})

            return LLMResponse(
                content=message.get("content", ""),
                finish_reason="stop" if data.get("done", False) else "length",
                model=self.model,
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Ollama chat API request failed: {e}") from e
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid Ollama chat API response format: {e}") from e

    async def stream_chat_complete(self, messages: list[ChatMessage], **kwargs):
        """Stream chat completion."""

        if not self._initialized:
            await self.initialize()

        # Convert messages to Ollama chat format
        ollama_messages = []
        for msg in messages:
            # Handle multi-modal content appropriately
            content = self._flatten_content_for_ollama(msg.content)

            # For vision models with structured content, handle images
            if self._is_vision_model() and isinstance(content, list):
                # Ollama vision models expect images as base64 data
                text_content = ""
                images = []

                for part in content:
                    if part.get("type") == "text":
                        text_content += part.get("text", "")
                    elif part.get("type") == "image_url":
                        image_url = part.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:"):
                            # Extract base64 data from data URL
                            _, base64_data = image_url.split(",", 1)
                            images.append(base64_data)

                # Build message with proper Ollama format
                ollama_msg = {"role": msg.role, "content": text_content}
                if images:
                    ollama_msg["images"] = images

                ollama_messages.append(ollama_msg)
            else:
                ollama_messages.append({"role": msg.role, "content": content})

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1.0),
                "top_k": kwargs.get("top_k", 40),
                "num_predict": kwargs.get("max_tokens", 1000),
            },
        }

        try:
            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    error_detail = await response.aread()
                    raise LLMProviderAPIError(f"Ollama streaming API error: {response.status_code} - {error_detail}")

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                content = data["message"].get("content", "")
                                if content:
                                    yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue  # Skip invalid JSON lines

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Ollama streaming API request failed: {e}") from e

    async def get_available_models(self) -> list[dict[str, Any]]:
        """Get list of available models."""
        if not self._initialized:
            await self.initialize()

        try:
            response = await self.client.get("/api/tags")
            if response.status_code != 200:
                raise LLMProviderAPIError(f"Failed to get models: {response.status_code}")

            data = response.json()
            return data.get("models", [])

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Failed to get available models: {e}") from e

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the current model."""
        info = super().get_model_info()
        info.update({"base_url": self.base_url, "local_inference": True, "supports_pull": True})
        return info
