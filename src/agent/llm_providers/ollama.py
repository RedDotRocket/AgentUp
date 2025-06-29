"""Ollama LLM provider implementation for {{ project_name }}."""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import (
    BaseLLMService,
    LLMCapability,
    LLMResponse,
    ChatMessage,
    LLMProviderError,
    LLMProviderAPIError,
)

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMService):
    """Ollama LLM provider for local model inference."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.client: Optional[httpx.AsyncClient] = None
        self.model = config.get('model', 'llama2')
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.timeout = config.get('timeout', 120.0)  # Longer timeout for local models

        # Ollama model capabilities (most models support basic chat)
        self._model_capabilities = {
            'llama2': [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES
            ],
            'llama3': [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES
            ],
            'mistral': [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES
            ],
            'codellama': [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES
            ],
            'neural-chat': [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES
            ],
            'dolphin': [
                LLMCapability.TEXT_COMPLETION,
                LLMCapability.CHAT_COMPLETION,
                LLMCapability.STREAMING,
                LLMCapability.SYSTEM_MESSAGES
            ]
        }

    async def initialize(self) -> None:
        """Initialize the Ollama service."""
        logger.info(f"Initializing Ollama service '{self.name}' with model '{self.model}'")

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AgentUp-Agent/1.0'
        }

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout
        )

        # Set capabilities based on model
        self._detect_capabilities()

        # Test connection and model availability
        try:
            await self._ensure_model_available()
            await self.health_check()
            self._initialized = True
            logger.info(f"Ollama service {self.name} initialized successfully")
            logger.info(f"Capabilities: {[cap.value for cap in self.get_capabilities()]}")
        except Exception as e:
            logger.error(f"Ollama service {self.name} initialization failed: {e}")
            raise LLMProviderError(f"Failed to initialize Ollama service: {e}")

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
                LLMCapability.SYSTEM_MESSAGES
            ]

        # Set capabilities (Ollama typically doesn't support function calling natively)
        for cap in capabilities:
            self._set_capability(cap, True)

    async def _ensure_model_available(self):
        """Ensure the model is available, pull if necessary."""
        try:
            # Check if model exists
            response = await self.client.get('/api/tags')
            if response.status_code != 200:
                raise LLMProviderAPIError(f"Failed to check Ollama models: {response.status_code}")

            data = response.json()
            model_names = [model['name'].split(':')[0] for model in data.get('models', [])]

            if self.model not in model_names:
                logger.info(f"Model {self.model} not found locally, attempting to pull...")
                await self._pull_model()

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Failed to connect to Ollama: {e}")

    async def _pull_model(self):
        """Pull model from Ollama registry."""
        payload = {'name': self.model}

        try:
            response = await self.client.post('/api/pull', json=payload)
            if response.status_code != 200:
                raise LLMProviderAPIError(f"Failed to pull model {self.model}: {response.status_code}")

            logger.info(f"Successfully pulled model {self.model}")

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Failed to pull model {self.model}: {e}")

    async def close(self) -> None:
        """Close the Ollama service."""
        if self.client:
            await self.client.aclose()
        self._initialized = False

    async def health_check(self) -> Dict[str, Any]:
        """Check Ollama service health."""
        try:
            # Test with a simple generation
            response = await self.client.post('/api/generate', json={
                'model': self.model,
                'prompt': 'Test',
                'stream': False
            })

            return {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'response_time_ms': response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
                'status_code': response.status_code,
                'model': self.model,
                'capabilities': [cap.value for cap in self.get_capabilities()]
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'model': self.model
            }

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate completion from prompt."""
        if not self._initialized:
            await self.initialize()

        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 1.0),
                'top_k': kwargs.get('top_k', 40),
                'num_predict': kwargs.get('max_tokens', 1000)
            }
        }

        try:
            response = await self.client.post('/api/generate', json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"Ollama API error: {response.status_code} - {error_detail}")

            data = response.json()

            return LLMResponse(
                content=data.get('response', ''),
                finish_reason='stop' if data.get('done', False) else 'length',
                model=self.model
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Ollama API request failed: {e}")
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid Ollama API response format: {e}")

    async def chat_complete(self, messages: List[ChatMessage], **kwargs) -> LLMResponse:
        """Generate chat completion from messages."""
        if not self._initialized:
            await self.initialize()

        # Convert messages to Ollama chat format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                'role': msg.role,
                'content': msg.content
            })

        payload = {
            'model': self.model,
            'messages': ollama_messages,
            'stream': False,
            'options': {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 1.0),
                'top_k': kwargs.get('top_k', 40),
                'num_predict': kwargs.get('max_tokens', 1000)
            }
        }

        try:
            response = await self.client.post('/api/chat', json=payload)

            if response.status_code != 200:
                error_detail = response.text
                raise LLMProviderAPIError(f"Ollama chat API error: {response.status_code} - {error_detail}")

            data = response.json()
            message = data.get('message', {})

            return LLMResponse(
                content=message.get('content', ''),
                finish_reason='stop' if data.get('done', False) else 'length',
                model=self.model
            )

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Ollama chat API request failed: {e}")
        except KeyError as e:
            raise LLMProviderAPIError(f"Invalid Ollama chat API response format: {e}")

    async def stream_chat_complete(self, messages: List[ChatMessage], **kwargs):
        """Stream chat completion."""
        if not self.has_capability(LLMCapability.STREAMING):
            raise LLMProviderError(f"Provider {self.name} does not support streaming")

        if not self._initialized:
            await self.initialize()

        # Convert messages to Ollama chat format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                'role': msg.role,
                'content': msg.content
            })

        payload = {
            'model': self.model,
            'messages': ollama_messages,
            'stream': True,
            'options': {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 1.0),
                'top_k': kwargs.get('top_k', 40),
                'num_predict': kwargs.get('max_tokens', 1000)
            }
        }

        try:
            async with self.client.stream('POST', '/api/chat', json=payload) as response:
                if response.status_code != 200:
                    error_detail = await response.aread()
                    raise LLMProviderAPIError(f"Ollama streaming API error: {response.status_code} - {error_detail}")

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if 'message' in data:
                                content = data['message'].get('content', '')
                                if content:
                                    yield content
                            if data.get('done', False):
                                break
                        except json.JSONDecodeError:
                            continue  # Skip invalid JSON lines

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Ollama streaming API request failed: {e}")

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models."""
        if not self._initialized:
            await self.initialize()

        try:
            response = await self.client.get('/api/tags')
            if response.status_code != 200:
                raise LLMProviderAPIError(f"Failed to get models: {response.status_code}")

            data = response.json()
            return data.get('models', [])

        except httpx.HTTPError as e:
            raise LLMProviderAPIError(f"Failed to get available models: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        info = super().get_model_info()
        info.update({
            'base_url': self.base_url,
            'local_inference': True,
            'supports_pull': True
        })
        return info