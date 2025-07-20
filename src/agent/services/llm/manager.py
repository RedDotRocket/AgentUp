from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class LLMManager:
    """Manages LLM provider selection, validation, and communication."""

    @staticmethod
    async def get_llm_service(services=None):
        """Get the configured LLM service from ai_provider configuration."""
        try:
            from agent.config import load_config

            config = load_config()

            # Get the new ai_provider configuration
            ai_provider_config = config.get("ai_provider", {})
            if not ai_provider_config:
                logger.warning("ai_provider not configured in agentup.yml")
                return None

            provider = ai_provider_config.get("provider")
            if not provider:
                logger.warning("ai_provider.provider not configured")
                return None

            # Create LLM service directly from ai_provider config
            from agent.llm_providers import create_llm_provider

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
            from agent.llm_providers.base import ChatMessage  # type: ignore[import-untyped]
        except ImportError:
            # Fallback when LLM providers not available
            logger.warning("LLM provider modules not available, using basic chat completion")
            return await LLMManager.llm_direct_response(llm, messages)

        # Convert dict messages to ChatMessage objects with multi-modal support
        chat_messages = []
        for msg in messages:
            content = LLMManager._extract_message_content(msg)
            chat_messages.append(ChatMessage(role=msg.get("role", "user"), content=content))

        # Always try function calling - provider will handle fallback if needed
        logger.debug("Calling LLM with functions")
        response = await llm.chat_complete_with_functions(chat_messages, function_schemas)

        # Handle function calls if present
        if response.function_calls:
            # Log which functions the LLM selected
            selected_functions = [func_call.name for func_call in response.function_calls]
            logger.info(f"LLM selected function(s): {', '.join(selected_functions)}")

            function_results = []
            for func_call in response.function_calls:
                try:
                    logger.debug(f"Executing function: {func_call.name} with arguments: {func_call.arguments}")
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

    @staticmethod
    async def llm_direct_response(llm, messages: list[dict[str, str]]) -> str:
        """Get direct LLM response when no functions are available."""
        # CONDITIONAL_LLM_PROVIDER_IMPORTS
        # Note: llm_providers module is generated during project creation from templates
        try:
            from agent.llm_providers.base import ChatMessage  # type: ignore[import-untyped]

            # Convert to ChatMessage objects for consistency
            chat_messages = []
            for msg in messages:
                content = LLMManager._extract_message_content(msg)
                chat_messages.append(ChatMessage(role=msg.get("role", "user"), content=content))

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

    @staticmethod
    def _extract_message_content(msg: dict[str, Any]) -> str | list[dict[str, Any]]:
        """Extract content from A2A message, handling both text and multi-modal parts."""
        # If it's already simple content, return as-is
        if "content" in msg and isinstance(msg["content"], str):
            return msg["content"]

        # Handle A2A message parts
        if "parts" in msg:
            return LLMManager._process_message_parts(msg["parts"])

        return ""

    @staticmethod
    def _process_message_parts(parts: list[Any]) -> str | list[dict[str, Any]]:
        """Process A2A message parts into LLM-compatible format."""
        content_parts = []
        text_parts = []

        for part in parts:
            # Handle both dict and A2A SDK Part objects
            if hasattr(part, "root"):
                # A2A SDK Part object
                LLMManager._process_a2a_part(part, content_parts, text_parts)
            elif isinstance(part, dict):
                # Dict format (fallback)
                LLMManager._process_dict_part(part, content_parts, text_parts)

        # Return structured content if we have images or multiple parts
        if len(content_parts) > 1 or any(p.get("type") == "image_url" for p in content_parts):
            return content_parts

        # Return simple text if only text parts
        return " ".join(text_parts) if text_parts else ""

    @staticmethod
    def _process_a2a_part(part: Any, content_parts: list[dict[str, Any]], text_parts: list[str]) -> None:
        """Process A2A SDK Part object."""
        kind = part.root.kind

        if kind == "text":
            text_content = part.root.text
            text_parts.append(text_content)
            content_parts.append({"type": "text", "text": text_content})

        elif kind == "file":
            LLMManager._process_file_part(part.root.file, content_parts, text_parts)

    @staticmethod
    def _process_dict_part(part: dict[str, Any], content_parts: list[dict[str, Any]], text_parts: list[str]) -> None:
        """Process dict-format part."""
        kind = part.get("kind")

        if kind == "text":
            text_content = part.get("text", "")
            text_parts.append(text_content)
            content_parts.append({"type": "text", "text": text_content})

        elif kind == "file" and "file" in part:
            LLMManager._process_file_info(part["file"], content_parts, text_parts)

    @staticmethod
    def _process_file_part(file_info: Any, content_parts: list[dict[str, Any]], text_parts: list[str]) -> None:
        """Process A2A SDK file object."""
        mime_type = getattr(file_info, "mimeType", None)
        file_name = getattr(file_info, "name", "file")

        if mime_type and mime_type.startswith("image/"):
            # Handle images for vision models
            if hasattr(file_info, "bytes") and file_info.bytes:
                image_url = f"data:{mime_type};base64,{file_info.bytes}"
                content_parts.append({"type": "image_url", "image_url": {"url": image_url}})
            elif hasattr(file_info, "uri") and file_info.uri:
                content_parts.append({"type": "image_url", "image_url": {"url": file_info.uri}})

        elif mime_type and LLMManager._is_text_mime_type(mime_type):
            # Handle text-based files
            if hasattr(file_info, "bytes") and file_info.bytes:
                try:
                    import base64

                    decoded_content = base64.b64decode(file_info.bytes).decode("utf-8")
                    text_content = LLMManager._format_file_content(file_name, mime_type, decoded_content)
                    text_parts.append(text_content)
                    content_parts.append({"type": "text", "text": text_content})
                except Exception as e:
                    logger.warning(f"Failed to decode text file {file_name}: {e}")
        else:
            # Handle other file types with notice
            file_notice = LLMManager._format_file_notice(file_name, mime_type)
            text_parts.append(file_notice)
            content_parts.append({"type": "text", "text": file_notice})

    @staticmethod
    def _process_file_info(
        file_info: dict[str, Any], content_parts: list[dict[str, Any]], text_parts: list[str]
    ) -> None:
        """Process dict-format file info."""
        mime_type = file_info.get("mimeType", "")
        file_name = file_info.get("name", "file")

        if mime_type and mime_type.startswith("image/"):
            # Handle images for vision models
            if "bytes" in file_info:
                image_url = f"data:{mime_type};base64,{file_info['bytes']}"
                content_parts.append({"type": "image_url", "image_url": {"url": image_url}})
            elif "uri" in file_info:
                content_parts.append({"type": "image_url", "image_url": {"url": file_info["uri"]}})

        elif mime_type and LLMManager._is_text_mime_type(mime_type):
            # Handle text-based files
            if "bytes" in file_info:
                try:
                    import base64

                    decoded_content = base64.b64decode(file_info["bytes"]).decode("utf-8")
                    text_content = LLMManager._format_file_content(file_name, mime_type, decoded_content)
                    text_parts.append(text_content)
                    content_parts.append({"type": "text", "text": text_content})
                except Exception as e:
                    logger.warning(f"Failed to decode text file {file_name}: {e}")
        else:
            # Handle other file types with notice
            file_notice = LLMManager._format_file_notice(file_name, mime_type)
            text_parts.append(file_notice)
            content_parts.append({"type": "text", "text": file_notice})

    @staticmethod
    def _is_text_mime_type(mime_type: str) -> bool:
        """Check if MIME type represents text content."""
        return (
            mime_type.startswith("text/")
            or mime_type == "application/json"
            or mime_type == "application/xml"
            or mime_type == "application/yaml"
            or mime_type == "application/markdown"
        )

    @staticmethod
    def _format_file_content(file_name: str, mime_type: str, content: str) -> str:
        """Format file content for inclusion in LLM prompt."""
        return f"\n\n--- Content of {file_name} ({mime_type}) ---\n{content}\n--- End of {file_name} ---\n"

    @staticmethod
    def _format_file_notice(file_name: str, mime_type: str) -> str:
        """Format file notice for non-text files."""
        return f"\n\n--- File attached: {file_name} ({mime_type}) ---\n[Binary file content not displayed]\n"
