import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import structlog
from a2a.types import Message, Task, TaskState

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
            if llm and hasattr(llm, "stream") and llm.stream:
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

    async def _process_task_streaming_native(self, task: Task, dispatcher, auth_result) -> AsyncIterator[str]:
        """Process task with native LLM streaming."""
        try:
            from agent.core.function_executor import FunctionExecutor
            from agent.services.llm.manager import LLMManager

            # Extract user message from A2A task
            user_message = dispatcher._extract_user_message_full(task)
            if not user_message:
                yield "I didn't receive any message to process."
                return

            # Get LLM service
            llm = await LLMManager.get_llm_service()
            if not llm:
                yield "LLM service unavailable."
                return

            # Get conversation context
            try:
                context_id = getattr(task, "context_id", task.id)
                conversation = dispatcher.conversation_manager.get_conversation_history(context_id)
            except KeyError:
                conversation = []

            # Prepare LLM conversation
            messages = await dispatcher.conversation_manager.prepare_llm_conversation(user_message, conversation)

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
                full_response = ""
                async for chunk in LLMManager.llm_with_functions_streaming(
                    llm, messages, function_schemas, function_executor
                ):
                    full_response += chunk
                    yield chunk

                # Update conversation history with complete response
                user_input = dispatcher._extract_user_message(task)
                dispatcher.conversation_manager.update_conversation_history(context_id, user_input, full_response)
            else:
                # Direct streaming response (no functions)
                if hasattr(llm, "stream_chat_complete"):
                    from agent.llm_providers.base import ChatMessage

                    chat_messages = []
                    for msg in messages:
                        content = LLMManager._extract_message_content(msg)
                        chat_messages.append(ChatMessage(role=msg.get("role", "user"), content=content))

                    full_response = ""
                    async for chunk in llm.stream_chat_complete(chat_messages):
                        full_response += chunk
                        yield chunk

                    # Update conversation history
                    user_input = dispatcher._extract_user_message(task)
                    dispatcher.conversation_manager.update_conversation_history(context_id, user_input, full_response)
                else:
                    # Graceful fallback - complete response at once
                    response = await LLMManager.llm_direct_response(llm, messages)
                    yield response

                    # Update conversation history
                    user_input = dispatcher._extract_user_message(task)
                    dispatcher.conversation_manager.update_conversation_history(context_id, user_input, response)

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
                messageId=message_params.get("messageId", str(uuid.uuid4())),
                contextId=context_id,
                taskId=task_id,
            )

            # Create A2A Task
            task = Task(
                id=task_id,
                contextId=context_id,
                history=[message],
                kind="task",
                status={"state": TaskState.submitted, "timestamp": None, "message": None},
            )

            # Get dispatcher and conversation manager
            dispatcher = get_function_dispatcher()

            # Get existing conversation history using the dispatcher's ConversationManager
            conversation_history = dispatcher.conversation_manager.get_conversation_history(context_id)

            # Convert conversation history to A2A Message format for task history
            a2a_history = []
            for turn in conversation_history:
                # Add user message
                user_msg = Message(
                    kind="message",
                    role="user",
                    parts=[{"kind": "text", "text": turn["user"]}],
                    messageId=str(uuid.uuid4()),
                    contextId=context_id,
                    taskId=task_id,
                )
                a2a_history.append(user_msg)

                # Add agent message (using 'agent' role for A2A compliance)
                agent_msg = Message(
                    kind="message",
                    role="agent",
                    parts=[{"kind": "text", "text": turn["assistant"]}],
                    messageId=str(uuid.uuid4()),
                    contextId=context_id,
                    taskId=task_id,
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
                full_response += chunk  # Build complete response
                batch_parts.append({"kind": "text", "metadata": None, "text": chunk})

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
                dispatcher.conversation_manager.update_conversation_history(context_id, user_input, full_response)

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
