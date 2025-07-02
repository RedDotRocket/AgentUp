import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMManager:
    """Manages LLM provider selection, validation, and communication."""

    @staticmethod
    async def get_llm_service(services=None):
        """Get the configured LLM service from ai_provider configuration."""
        try:
            from .config import load_config

            config = load_config()

            # Get the new ai_provider configuration
            ai_provider_config = config.get("ai_provider", {})
            if not ai_provider_config:
                logger.warning("ai_provider not configured in agent_config.yaml")
                return None

            provider = ai_provider_config.get("provider")
            if not provider:
                logger.warning("ai_provider.provider not configured")
                return None

            # Create LLM service directly from ai_provider config
            from .llm_providers import create_llm_provider

            llm = create_llm_provider(provider, f"ai_provider_{provider}", ai_provider_config)

            if llm:
                # Initialize the provider if not already initialized
                if not llm.is_initialized:
                    await llm.initialize()

                if llm.is_initialized:
                    logger.info(f"Using AI provider: {provider}")
                    return llm
                else:
                    logger.error(f"AI provider '{provider}' initialization failed")
                    return None
            else:
                logger.error(f"AI provider '{provider}' could not be created")
                return None

        except ImportError as e:
            logger.error(f"LLM provider modules not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get AI provider from config: {e}")
            raise

    @staticmethod
    async def llm_with_functions(
        llm, messages: list[dict[str, str]], function_schemas: list[dict[str, Any]], function_executor
    ) -> str:
        """Process with LLM function calling capability using provider-agnostic approach."""
        try:
            from .llm_providers.base import (  # type: ignore[import-untyped]
                ChatMessage,
                LLMCapability,
            )
        except ImportError:
            # Fallback when LLM providers not available
            logger.warning("LLM provider modules not available, using basic chat completion")
            return await LLMManager.llm_direct_response(llm, messages)

        # Convert dict messages to ChatMessage objects
        chat_messages = []
        for msg in messages:
            chat_messages.append(ChatMessage(role=msg.get("role", "user"), content=msg.get("content", "")))

        # Check if provider supports native function calling
        if hasattr(llm, "has_capability") and llm.has_capability(LLMCapability.FUNCTION_CALLING):
            logger.debug("Using native function calling")
            response = await llm.chat_complete_with_functions(chat_messages, function_schemas)

            # Handle function calls if present
            if response.function_calls:
                function_results = []
                for func_call in response.function_calls:
                    try:
                        result = await function_executor.execute_function_call(func_call.name, func_call.arguments)
                        function_results.append(result)
                    except Exception as e:
                        logger.error(f"Function call failed: {func_call.name}, error: {e}")
                        function_results.append(f"Error: {str(e)}")

                # Combine function results with LLM response
                if function_results:
                    if response.content:
                        return f"{response.content}\n\nResults: {'; '.join(function_results)}"
                    else:
                        return "; ".join(function_results)

            return response.content
        else:
            logger.debug("Using prompt-based function calling fallback")
            # Use the enhanced prompt-based approach from the provider
            response = await llm.chat_complete_with_functions(chat_messages, function_schemas)

            # Parse and execute function calls if present
            if response.function_calls:
                function_results = []
                for func_call in response.function_calls:
                    try:
                        result = await function_executor.execute_function_call(func_call.name, func_call.arguments)
                        function_results.append(result)
                    except Exception as e:
                        logger.error(f"Function call failed: {func_call.name}, error: {e}")
                        function_results.append(f"Error: {str(e)}")

                if function_results:
                    return "; ".join(function_results)

            return response.content

    @staticmethod
    async def llm_direct_response(llm, messages: list[dict[str, str]]) -> str:
        """Get direct LLM response when no functions are available."""
        # CONDITIONAL_LLM_PROVIDER_IMPORTS
        # Note: llm_providers module is generated during project creation from templates
        try:
            from .llm_providers.base import ChatMessage  # type: ignore[import-untyped]

            # Convert to ChatMessage objects for consistency
            chat_messages = []
            for msg in messages:
                chat_messages.append(ChatMessage(role=msg.get("role", "user"), content=msg.get("content", "")))

            response = await llm.chat_complete(chat_messages)
            return response.content
        except ImportError:
            # Fallback when LLM providers not available
            logger.warning("LLM provider modules not available, using simple prompt-based approach")
            prompt = LLMManager._messages_to_prompt(messages)
            # Assuming the service has a basic generate method
            if hasattr(llm, "generate"):
                return await llm.generate(prompt)
            else:
                return "LLM service unavailable - please check configuration"

    @staticmethod
    def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
        """Convert messages to prompt format for LLM."""
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)
