import re
import threading
from typing import Any

import structlog
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    DataPart,
    InvalidParamsError,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_artifact,
    new_task,
)
from a2a.utils.errors import ServerError

from agent.config.model import BaseAgent

logger = structlog.get_logger(__name__)

# Thread-local storage for auth context
_thread_local = threading.local()


def set_current_auth_for_executor(auth_result):
    """Store auth result in thread-local storage for executor access."""
    _thread_local.auth_result = auth_result


def get_current_auth_for_executor():
    """Retrieve auth result from thread-local storage."""
    return getattr(_thread_local, "auth_result", None)


class AgentUpExecutor(AgentExecutor):
    """AgentUpExecutor executor for AgentUp agents.
    The AgentUpExecutor allows us to inject Middleware into the agent's execution
    context. This is where all the AgentUp logic maps out from A2A'isms.
    A2A Handler → AgentUp Executor → Main Dispatcher
    """

    def __init__(self, agent: BaseAgent | AgentCard):
        self.agent = agent
        # Check streaming support from agent configuration
        if hasattr(agent, "supports_streaming"):
            self.supports_streaming = agent.supports_streaming
        elif hasattr(agent, "capabilities") and agent.capabilities:
            # Check A2A AgentCard capabilities
            self.supports_streaming = getattr(agent.capabilities, "streaming", False)
        else:
            self.supports_streaming = False

        # Handle both BaseAgent and AgentCard
        if isinstance(agent, AgentCard):
            self.agent_name = agent.name
        else:
            self.agent_name = agent.agent_name

        # Load config for routing
        from agent.config import Config

        # Parse plugins for direct routing based on keywords/patterns
        self.plugins = {}
        # Handle new dictionary-based plugin structure
        if hasattr(Config, "plugins") and isinstance(Config.plugins, dict):
            for package_name, plugin_data in Config.plugins.items():
                if plugin_data.get("enabled", True):
                    plugin_name = plugin_data.get("name", package_name)
                    keywords = plugin_data.get("keywords", [])
                    patterns = plugin_data.get("patterns", [])

                    self.plugins[plugin_name] = {
                        "keywords": keywords,
                        "patterns": patterns,
                        "name": plugin_name,
                        "description": plugin_data.get("description", ""),
                        "priority": plugin_data.get("priority", 100),
                    }
        else:
            # Fallback: old list-based structure (deprecated)
            for plugin_data in getattr(Config, "plugins", []):
                if getattr(plugin_data, "enabled", True):
                    plugin_name = getattr(plugin_data, "name", "unknown")
                    keywords = getattr(plugin_data, "keywords", [])
                    patterns = getattr(plugin_data, "patterns", [])

                    self.plugins[plugin_name] = {
                        "keywords": keywords,
                        "patterns": patterns,
                        "name": plugin_name,
                        "description": getattr(plugin_data, "description", ""),
                        "priority": getattr(plugin_data, "priority", 100),
                    }

        # Initialize Function Dispatcher for AI routing (fallback)
        from .dispatcher import get_function_dispatcher

        self.dispatcher = get_function_dispatcher()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        logger.info(f"Executing agent {self.agent_name}")
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError(data={"reason": error}))

        task = context.current_task

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            # Transition to working state
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Processing request with for task {task.id} using {self.agent_name}.",
                    task.context_id,
                    task.id,
                ),
                final=False,
            )

            # Check if task requires specific input/clarification
            if await self._requires_input(task, context):
                await updater.update_status(
                    TaskState.input_required,
                    new_agent_text_message(
                        "I need more information to proceed. Please provide additional details.",
                        task.context_id,
                        task.id,
                    ),
                    final=False,
                )
                return

            # Check for direct routing first (keyword/pattern matching)
            user_input = self._extract_user_message(task)
            direct_plugin = self._find_direct_plugin(user_input)

            if direct_plugin:
                logger.info(f"Processing task {task.id} with direct routing to plugin: {direct_plugin}")
                # Process with direct routing to specific plugin
                result = await self._process_direct_routing(task, direct_plugin)
                await self._create_response_artifact(result, task, updater)
            else:
                logger.info(f"Processing task {task.id} with AI routing (no direct match)")
                # Always execute normally - streaming is handled at response layer
                auth_result = get_current_auth_for_executor()
                result = await self.dispatcher.process_task(task, auth_result)
                await self._create_response_artifact(result, task, updater)

        except ValueError as e:
            # Handle unsupported operations gracefully (UnsupportedOperationError is a data model, not exception)
            if "unsupported" in str(e).lower():
                logger.warning(f"Unsupported operation requested: {e}")
                await updater.update_status(
                    TaskState.rejected,
                    new_agent_text_message(
                        f"This operation is not supported: {str(e)}",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    f"I encountered an error processing your request: {str(e)}",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )

    def _extract_user_message(self, task: Task) -> str:
        """Extract user message text from A2A task history.

        Args:
            task: A2A Task object

        Returns:
            User message text or empty string
        """
        try:
            if not (hasattr(task, "history") and task.history):
                return ""

            # Get the latest user message from history
            for message in reversed(task.history):
                if message.role == "user" and message.parts:
                    for part in message.parts:
                        # A2A SDK uses Part(root=TextPart(...)) structure
                        if hasattr(part, "root") and hasattr(part.root, "kind"):
                            if part.root.kind == "text" and hasattr(part.root, "text"):
                                return part.root.text
            return ""
        except Exception as e:
            logger.error(f"Error extracting user message: {e}")
            return ""

    def _find_direct_plugin(self, user_input: str) -> str | None:
        if not user_input:
            return None

        user_input_lower = user_input.lower()

        # Sort plugins by priority (lower number = higher priority)
        sorted_plugins = sorted(self.plugins.items(), key=lambda x: x[1].get("priority", 100))

        for plugin_name, plugin_info in sorted_plugins:
            # Check keywords
            keywords = plugin_info.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in user_input_lower:
                    logger.debug(f"Keyword '{keyword}' matched for plugin '{plugin_name}'")
                    return plugin_name

            # Check patterns
            patterns = plugin_info.get("patterns", [])
            for pattern in patterns:
                try:
                    if re.search(pattern, user_input, re.IGNORECASE):
                        logger.debug(f"Pattern '{pattern}' matched for plugin '{plugin_name}'")
                        return plugin_name
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}' in plugin '{plugin_name}': {e}")

        return None

    async def _process_direct_routing(self, task: Task, plugin_name: str) -> str:
        logger.info(f"Direct routing to plugin: {plugin_name}")

        try:
            # Get capability executor for the plugin
            from agent.capabilities import get_capability_executor

            logger.debug(f"Getting capability executor for plugin '{plugin_name}'")
            executor = get_capability_executor(plugin_name)
            if not executor:
                return f"Plugin '{plugin_name}' is not available or not properly configured."

            # Call the capability directly
            result = await executor(task)
            return result if isinstance(result, str) else str(result)

        except Exception as e:
            logger.error(f"Error in direct routing to plugin '{plugin_name}': {e}")
            return f"Sorry, I encountered an error while processing your request: {str(e)}"

    async def execute_streaming(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute task with streaming for message/stream endpoint."""
        logger.info(f"Executing agent {self.agent_name} with streaming")
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError(data={"reason": error}))

        task = context.task
        updater = context.updater

        try:
            # Set thread-local auth for executor access
            set_current_auth_for_executor(context.auth_result)

            # Start with working status
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Processing streaming request for task {task.id} using {self.agent_name}.",
                    task.context_id,
                    task.id,
                ),
                final=False,
            )

            # Always use streaming for message/stream endpoint
            await self._process_streaming(task, updater, event_queue)

        except Exception as e:
            logger.error(f"Error in streaming execution: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    f"I encountered an error processing your streaming request: {str(e)}",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )

    async def _process_streaming(
        self,
        task: Task,
        updater: TaskUpdater,
        event_queue: EventQueue,
    ) -> None:
        try:
            # Get current auth context from thread-local storage
            auth_result = get_current_auth_for_executor()

            # Start streaming with auth context
            artifact_parts: list[Part] = []
            chunk_count = 0

            # Collect all streaming chunks without sending individual events
            async for chunk in self.dispatcher.process_task_streaming(task, auth_result):
                chunk_count += 1

                if isinstance(chunk, str):
                    # Text chunk - A2A SDK structure
                    part = Part(root=TextPart(text=chunk))
                    artifact_parts.append(part)

                elif isinstance(chunk, dict):
                    # Data chunk - A2A SDK structure
                    part = Part(root=DataPart(data=chunk))
                    artifact_parts.append(part)

                # Send periodic updates every 10 chunks to maintain streaming feel
                if chunk_count % 10 == 0:
                    # Send the last 10 chunks as a batch
                    batch_parts = artifact_parts[-10:]
                    artifact = new_artifact(
                        batch_parts,
                        name=f"{self.agent_name}-stream-batch-{chunk_count // 10}",
                        description="Streaming response batch",
                    )

                    update_event = TaskArtifactUpdateEvent(
                        taskId=task.id,
                        context_id=task.context_id,
                        artifact=artifact,
                        append=True,
                        lastChunk=False,
                        kind="artifact-update",
                    )
                    await event_queue.enqueue_event(update_event)

            # Send any remaining chunks at the end
            remaining_chunks = chunk_count % 10
            if remaining_chunks > 0:
                batch_parts = artifact_parts[-remaining_chunks:]
                artifact = new_artifact(
                    batch_parts, name=f"{self.agent_name}-stream-final", description="Final streaming batch"
                )
                update_event = TaskArtifactUpdateEvent(
                    taskId=task.id,
                    context_id=task.context_id,
                    artifact=artifact,
                    append=True,
                    lastChunk=False,
                    kind="artifact-update",
                )
                await event_queue.enqueue_event(update_event)

            # Streaming complete - no need for final artifact since we already sent all chunks
            await updater.complete()

        except Exception:
            raise

    async def _create_response_artifact(
        self,
        result: Any,
        task: Task,
        updater: TaskUpdater,
    ) -> None:
        if not result:
            # Empty response
            await updater.update_status(
                TaskState.completed,
                new_agent_text_message(
                    "Task completed successfully.",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )
            return

        parts: list[Part] = []

        # Handle different result types
        if isinstance(result, str):
            # Text response
            parts.append(Part(root=TextPart(text=result)))
        elif isinstance(result, dict):
            # Structured data response
            # Add both human-readable text and machine-readable data
            if "summary" in result:
                parts.append(Part(root=TextPart(text=result["summary"])))
            parts.append(Part(root=DataPart(data=result)))
        elif isinstance(result, list):
            # list of items - convert to structured data
            parts.append(Part(root=DataPart(data={"items": result})))
        else:
            # Fallback to string representation
            parts.append(Part(root=TextPart(text=str(result))))

        # Create multi-modal artifact
        artifact = new_artifact(parts, name=f"{self.agent_name}-result", description=f"Response from {self.agent_name}")

        await updater.add_artifact(parts, name=artifact.name)
        await updater.complete()

    async def _requires_input(self, task: Task, context: RequestContext) -> bool:
        # This could be enhanced with actual logic to detect incomplete requests
        # For now, return False to proceed with processing
        return False

    def _validate_request(self, context: RequestContext) -> bool:
        return False

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> Task | None:
        task = request.current_task

        if not task:
            raise ServerError(error=InvalidParamsError(data={"reason": "No task to cancel"}))

        # Check if task can be canceled
        if task.status.state in [TaskState.completed, TaskState.failed, TaskState.canceled, TaskState.rejected]:
            raise ServerError(
                error=UnsupportedOperationError(
                    data={"reason": f"Task in state '{task.status.state}' cannot be canceled"}
                )
            )

        # If dispatcher supports cancellation
        if hasattr(self.dispatcher, "cancel_task"):
            try:
                await self.dispatcher.cancel_task(task.id)

                # Update task status
                updater = TaskUpdater(event_queue, task.id, task.context_id)
                await updater.update_status(
                    TaskState.canceled,
                    new_agent_text_message(
                        "Task has been canceled by user request.",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )

                # Return original task - status already updated via updater
                return task

            except Exception as e:
                logger.error(f"Error canceling task {task.id}: {e}")
                raise ServerError(
                    error=UnsupportedOperationError(data={"reason": f"Failed to cancel task: {str(e)}"})
                ) from e
        else:
            # Cancellation not supported by dispatcher
            raise ServerError(
                error=UnsupportedOperationError(data={"reason": "Task cancellation is not supported by this agent"})
            )
