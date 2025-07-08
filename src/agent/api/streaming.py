from collections.abc import AsyncIterator
from typing import Any

import structlog
from a2a.types import Task

from ..core.function_executor import FunctionExecutor

logger = structlog.get_logger(__name__)


class StreamingHandler:
    """Handles streaming operations for LLM responses."""

    def __init__(self, function_registry, conversation_manager):
        self.function_registry = function_registry
        self.conversation_manager = conversation_manager

    async def process_task_streaming(
        self, task: Task, llm_manager, extract_user_message_func, fallback_response_func
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Process A2A task with streaming support.

        Yields chunks of text or structured data as they become available.

        Args:
            task: A2A Task object

        Yields:
            Union[str, dict[str, Any]]: Text chunks or structured data
        """
        try:
            # Extract user message
            user_input = extract_user_message_func(task)
            if not user_input:
                yield "I didn't receive any message to process."
                return

            # Get LLM service
            from ..services import get_services

            services = get_services()
            llm = await llm_manager.get_llm_service(services)

            if not llm:
                yield fallback_response_func(user_input)
                return

            # Get context and prepare conversation
            context_id = getattr(task, "contextId", task.id)
            conversation = self.conversation_manager.get_conversation_history(context_id)
            messages = await self.conversation_manager.prepare_llm_conversation(user_input, conversation)

            # Check if LLM supports streaming
            if hasattr(llm, "chat_complete_stream"):
                # Stream with function calling if available
                function_schemas = self.function_registry.get_function_schemas()

                if function_schemas and hasattr(llm, "chat_complete_stream_with_functions"):
                    # Stream with functions
                    accumulated_response = ""
                    async for chunk in self._stream_with_functions(llm, messages, function_schemas, task):
                        if isinstance(chunk, str):
                            accumulated_response += chunk
                        yield chunk

                    # Update conversation history with complete response
                    self.conversation_manager.update_conversation_history(context_id, user_input, accumulated_response)
                else:
                    # Direct streaming without functions
                    accumulated_response = ""
                    async for chunk in llm.chat_complete_stream(messages):
                        text_chunk = chunk.content if hasattr(chunk, "content") else str(chunk)
                        accumulated_response += text_chunk
                        yield text_chunk

                    self.conversation_manager.update_conversation_history(context_id, user_input, accumulated_response)
            else:
                # Fallback to non-streaming with simulated chunks
                # This would need to call the main process_task method
                response = "Streaming not supported by this LLM provider"

                # Simulate streaming by yielding in chunks
                chunk_size = 100
                for i in range(0, len(response), chunk_size):
                    yield response[i : i + chunk_size]

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"error": str(e)}

    async def _stream_with_functions(
        self, llm, messages: list[dict[str, str]], function_schemas: list[dict[str, Any]], task: Task
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Stream LLM responses with function calling support."""
        try:
            # This is a simplified version - actual implementation would depend on LLM provider
            # Which I will need to dig into more deeply
            # to understand how they handle function calls in streaming mode.
            # Most providers stream function calls as special tokens/markers
            function_executor = FunctionExecutor(self.function_registry, task)

            async for chunk in llm.chat_complete_stream_with_functions(messages, function_schemas):
                if hasattr(chunk, "function_call"):
                    # Execute function and yield result
                    function_name = chunk.function_call.name
                    arguments = chunk.function_call.arguments

                    result = await function_executor.execute_function_call(function_name, arguments)

                    # Yield structured data for function results
                    yield {"type": "function_result", "function": function_name, "result": result}

                    # Continue conversation with function result
                    messages.append({"role": "function", "name": function_name, "content": result})
                elif hasattr(chunk, "content") and chunk.content:
                    # Regular text chunk
                    yield chunk.content

        except Exception as e:
            logger.error(f"Function streaming error: {e}")
            # Fall back to non-streaming
            from ..services.llm.manager import LLMManager

            response = await LLMManager.llm_with_functions(llm, messages, function_schemas, function_executor)
            yield response
