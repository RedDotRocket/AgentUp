import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import structlog
from a2a.types import Message, Part, Role, Task, TaskState, TaskStatus, TextPart

logger = structlog.get_logger(__name__)


class StreamingHandler:
    def __init__(self, function_registry, conversation_manager):
        self.function_registry = function_registry
        self.conversation_manager = conversation_manager

    async def process_task_streaming(self, task: Task, auth_result) -> AsyncIterator[str | dict[str, Any]]:
        """Process A2A task with streaming support."""
        try:
            from agent.core.dispatcher import get_function_dispatcher
            from agent.services.llm.manager import LLMManager

            dispatcher = get_function_dispatcher()

            # Check if we should use native streaming
            llm = await LLMManager.get_llm_service()
            if llm and getattr(llm, "stream", False):
                # Use native streaming - real tokens as generated
                async for chunk in self._process_task_streaming_native(task, dispatcher, auth_result):
                    yield chunk
            else:
                # Graceful fallback - complete response at once
                response = await dispatcher.process_task(task, auth_result)
                if response:
                    yield response  # Single complete chunk
                else:
                    yield "Task completed."

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"error": str(e)}

    async def _process_task_streaming_native(
        self, task: Task, dispatcher, auth_result
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Process task with native LLM streaming."""
        try:
            from agent.core.function_executor import FunctionExecutor
            from agent.services.llm.manager import LLMManager

            # Validate we have a valid task with messages
            if not hasattr(task, "history") or not task.history:
                yield "I didn't receive any message to process."
                return

            # Get LLM service
            llm = await LLMManager.get_llm_service()
            if not llm:
                yield "LLM service unavailable."
                return

            # Prepare LLM conversation directly from A2A task history
            try:
                messages = dispatcher.conversation_manager.prepare_llm_conversation(task)
            except Exception as e:
                logger.error(f"Error preparing conversation for streaming: {e}", exc_info=True)
                yield f"Error preparing conversation: {str(e)}"
                return

            # Get available functions filtered by user scopes
            if auth_result:
                function_schemas = dispatcher.function_registry.get_available_tools_for_ai(auth_result.scopes)
            else:
                function_schemas = []

            # Create function executor
            function_executor = FunctionExecutor(dispatcher.function_registry, task)

            # Stream LLM processing
            if function_schemas:
                # Use streaming function calling
                async for chunk in LLMManager.llm_with_functions_streaming(
                    llm, messages, function_schemas, function_executor
                ):
                    # Convert LLMManagerResponse to expected type
                    if isinstance(chunk, str | dict):
                        yield chunk
                    elif hasattr(chunk, "content"):
                        # This is likely an LLMManagerResponse with content attribute
                        yield chunk.content
                    else:
                        yield str(chunk)
            else:
                # Direct streaming response (no functions)
                if hasattr(llm, "stream_chat_complete"):
                    from agent.llm_providers.base import ChatMessage

                    chat_messages = []
                    for msg in messages:
                        content = LLMManager._extract_message_content(msg)
                        chat_messages.append(ChatMessage(role=msg.get("role", "user"), content=content))

                    async for chunk in llm.stream_chat_complete(chat_messages):
                        yield chunk
                else:
                    # Graceful fallback - complete response at once
                    response = await LLMManager.llm_direct_response(llm, messages)
                    yield response

        except Exception as e:
            logger.error(f"Native streaming error: {e}", exc_info=True)
            yield f"Error: {str(e)}"

    async def create_streaming_response(
        self, params: dict[str, Any], request_id: str, auth_result
    ) -> AsyncIterator[str]:
        """Create a complete streaming response bypassing A2A JSONRPCHandler."""
        try:
            from agent.core.dispatcher import get_function_dispatcher

            # Create task from request params
            message_params = params.get("message", {})
            # Use existing context if provided, otherwise create new one
            context_id = message_params.get("contextId") or str(uuid.uuid4())
            task_id = str(uuid.uuid4())

            # Convert to A2A Message format
            message = Message(
                kind="message",
                role=message_params.get("role", "user"),
                parts=message_params.get("parts", []),
                message_id=message_params.get("messageId", str(uuid.uuid4())),
                context_id=context_id,
                task_id=task_id,
            )

            # Create A2A Task
            task = Task(
                id=task_id,
                context_id=context_id,
                history=[message],
                kind="task",
                status=TaskStatus(state=TaskState.submitted, timestamp=None, message=None),
            )

            # Get dispatcher and conversation manager
            dispatcher = get_function_dispatcher()

            # Get existing conversation history using the dispatcher's ConversationManager
            conversation_history = await dispatcher.conversation_manager.get_conversation_history(context_id)

            # Convert conversation history to A2A Message format for task history
            a2a_history = []
            for turn in conversation_history:
                # Add user message
                user_msg = Message(
                    kind="message",
                    role=Role.user,
                    parts=[Part(root=TextPart(kind="text", text=turn["user"]))],
                    message_id=str(uuid.uuid4()),
                    context_id=context_id,
                    task_id=task_id,
                )
                a2a_history.append(user_msg)

                # Add agent message (using 'agent' role for A2A compliance)
                agent_msg = Message(
                    kind="message",
                    role=Role.agent,
                    parts=[Part(root=TextPart(kind="text", text=turn["agent"]))],
                    message_id=str(uuid.uuid4()),
                    context_id=context_id,
                    task_id=task_id,
                )
                a2a_history.append(agent_msg)

            # Add current message to history
            all_history = a2a_history + [message]

            # Update task with full history
            task.history = all_history

            # Initial response
            initial_response = {
                "id": request_id,
                "jsonrpc": "2.0",
                "result": {
                    "artifacts": None,
                    "contextId": context_id,
                    "history": [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in all_history],
                    "id": task_id,
                    "kind": "task",
                    "metadata": None,
                    "status": {"message": None, "state": "submitted", "timestamp": None},
                },
            }
            yield f"data: {json.dumps(initial_response)}\n\n"

            # Working status
            working_response = {
                "id": request_id,
                "jsonrpc": "2.0",
                "result": {
                    "contextId": context_id,
                    "final": False,
                    "kind": "status-update",
                    "metadata": None,
                    "status": {
                        "message": {
                            "contextId": context_id,
                            "kind": "message",
                            "parts": [{"kind": "text", "text": "Processing streaming request..."}],
                            "role": "agent",
                        },
                        "state": "working",
                        "timestamp": datetime.now().isoformat(),
                    },
                    "taskId": task_id,
                },
            }
            yield f"data: {json.dumps(working_response)}\n\n"

            # Stream the actual response
            import asyncio

            chunk_count = 0
            batch_parts = []
            full_response = ""  # Track complete response for conversation history

            async for chunk in self.process_task_streaming(task, auth_result):
                chunk_count += 1
                # Handle both string and dict chunk types
                if isinstance(chunk, str):
                    chunk_text = chunk
                    full_response += chunk_text  # Build complete response
                elif isinstance(chunk, dict):
                    chunk_text = str(chunk.get("content", "")) or str(chunk)
                    full_response += chunk_text
                else:
                    chunk_text = str(chunk)
                    full_response += chunk_text

                batch_parts.append({"kind": "text", "metadata": None, "text": chunk_text})

                # Send chunks in batches of 10 for performance
                if len(batch_parts) >= 10:
                    artifact_response = {
                        "id": request_id,
                        "jsonrpc": "2.0",
                        "result": {
                            "append": True,
                            "artifact": {
                                "artifactId": str(uuid.uuid4()),
                                "description": "Streaming response batch",
                                "name": f"streaming-batch-{chunk_count // 10}",
                                "parts": batch_parts,
                            },
                            "contextId": context_id,
                            "kind": "artifact-update",
                            "taskId": task_id,
                        },
                    }
                    yield f"data: {json.dumps(artifact_response)}\n\n"
                    batch_parts = []

                    # Small delay for real-time feel
                    await asyncio.sleep(0.01)

            # Send remaining chunks
            if batch_parts:
                artifact_response = {
                    "id": request_id,
                    "jsonrpc": "2.0",
                    "result": {
                        "append": True,
                        "artifact": {
                            "artifactId": str(uuid.uuid4()),
                            "description": "Final streaming batch",
                            "name": "streaming-final",
                            "parts": batch_parts,
                        },
                        "contextId": context_id,
                        "kind": "artifact-update",
                        "taskId": task_id,
                    },
                }
                yield f"data: {json.dumps(artifact_response)}\n\n"

            # Update conversation history with complete response
            user_input = ""
            for part in message_params.get("parts", []):
                if part.get("kind") == "text":
                    user_input += part.get("text", "")

            if user_input and full_response:
                logger.info("Updating conversation history", context_id=context_id)
                await dispatcher.conversation_manager.update_conversation_history(context_id, user_input, full_response)

            # Final completion status
            completion_response = {
                "id": request_id,
                "jsonrpc": "2.0",
                "result": {
                    "contextId": context_id,
                    "final": True,
                    "kind": "status-update",
                    "status": {"state": "completed", "timestamp": datetime.now().isoformat()},
                    "taskId": task_id,
                },
            }
            yield f"data: {json.dumps(completion_response)}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            error_response = {
                "id": request_id,
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Streaming error: {str(e)}"},
            }
            yield f"data: {json.dumps(error_response)}\n\n"
