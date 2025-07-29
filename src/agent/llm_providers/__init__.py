from typing import Any

import structlog

from .anthropic import AnthropicProvider
from .base import BaseLLMService, ChatMessage, FunctionCall, LLMResponse
from .ollama import OllamaProvider
from .openai import OpenAIProvider

logger = structlog.get_logger(__name__)

# Provider registry
PROVIDER_REGISTRY: dict[str, type[BaseLLMService]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "ollama": OllamaProvider,
}


def create_llm_provider(provider_type: str, name: str, config: dict[str, Any]) -> BaseLLMService:
    """Create an LLM provider instance.

    Args:
        provider_type: Type of provider ('openai', 'anthropic', 'ollama', etc.)
        name: Name for the provider instance
        config: Provider configuration

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider type is not supported
    """
    provider_type = provider_type.lower()

    if provider_type not in PROVIDER_REGISTRY:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unsupported LLM provider: {provider_type}. Available: {available}")

    provider_class = PROVIDER_REGISTRY[provider_type]
    return provider_class(name, config)


def get_available_providers() -> dict[str, type[BaseLLMService]]:
    return PROVIDER_REGISTRY.copy()


def register_provider(provider_type: str, provider_class: type[BaseLLMService]):
    """Register a custom LLM provider.

    Args:
        provider_type: Type identifier for the provider
        provider_class: Provider class that inherits from BaseLLMService
    """
    if not issubclass(provider_class, BaseLLMService):
        raise ValueError("Provider class must inherit from BaseLLMService")

    PROVIDER_REGISTRY[provider_type.lower()] = provider_class
    logger.info(f"Registered custom LLM provider: {provider_type}")


# Export all public components
__all__ = [
    "BaseLLMService",
    "LLMResponse",
    "ChatMessage",
    "FunctionCall",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "create_llm_provider",
    "get_available_providers",
    "register_provider",
    "PROVIDER_REGISTRY",
]
