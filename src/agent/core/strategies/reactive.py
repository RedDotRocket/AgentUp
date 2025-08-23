"""Reactive execution strategy - single-shot request/response pattern."""

import re
from typing import Any

import structlog
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import DataPart, Part, Task, TaskArtifactUpdateEvent, TaskState, TextPart
from a2a.utils import new_agent_text_message, new_artifact

from agent.core.base import AgentExecutorBase, get_current_auth_for_executor

logger = structlog.get_logger(__name__)


class ReactiveStrategy(AgentExecutorBase):
    """Reactive execution strategy for single-shot request/response interactions.

    This strategy processes a request once and provides a response, similar to
    the current AgentUpExecutor behavior but with cleaner architecture.

    Features:
    - Direct plugin routing based on configuration
    - AI routing via function dispatcher as fallback
    - Streaming support for message/stream endpoint
    - Clean error handling and state management
    """

    def __init__(self, agent, config=None) -> None:
        super().__init__(agent)

        # Load plugin configuration for direct routing
        from agent.config import Config

        self.plugins = {}
        # Handle dictionary-based plugin structure
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

        # Initialize Function Dispatcher for AI routing
        from agent.core.dispatcher import get_function_dispatcher

        self.dispatcher = get_function_dispatcher()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute reactive agent processing."""
        logger.info(f"Executing reactive agent {self.agent_name}")

        # Validate request
        error = self._validate_request(context)
        if error:
            from a2a.types import InvalidParamsError
            from a2a.utils.errors import ServerError

            raise ServerError(error=InvalidParamsError(data={"reason": error}))

        # Ensure task exists
        task = self._ensure_task_exists(context, event_queue)
        updater = self._create_task_updater(task, event_queue)

        try:
            # Transition to working state
            await self._transition_to_working(task, updater)

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

            # Check for direct routing first
            user_input = self._extract_user_message(task)
            direct_plugin = self._find_direct_plugin(user_input)

            if direct_plugin:
                logger.info(f"Processing task {task.id} with direct routing to plugin: {direct_plugin}")
                result = await self._process_direct_routing(task, direct_plugin)
                await self._create_response_artifact(result, task, updater)
            else:
                logger.info(f"Processing task {task.id} with AI routing")
                auth_result = get_current_auth_for_executor()
                result = await self.dispatcher.process_task(task, auth_result)
                await self._create_response_artifact(result, task, updater)

        except Exception as e:
            await self._handle_execution_error(e, task, updater)

    async def execute_streaming(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute task with streaming for message/stream endpoint."""
        logger.info(f"Executing reactive agent {self.agent_name} with streaming")

        error = self._validate_request(context)
        if error:
            from a2a.types import InvalidParamsError
            from a2a.utils.errors import ServerError

            raise ServerError(error=InvalidParamsError(data={"reason": error}))

        task = getattr(context, "task", None) or context.current_task
        updater = getattr(context, "updater", None)

        if not task:
            from a2a.types import InvalidParamsError
            from a2a.utils.errors import ServerError

            raise ServerError(error=InvalidParamsError(data={"reason": "No task available for streaming"}))

        if not updater:
            updater = self._create_task_updater(task, event_queue)

        try:
            # Set auth context
            auth_result = getattr(context, "auth_result", None)
            from agent.core.base import set_current_auth_for_executor

            set_current_auth_for_executor(auth_result)

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

            # Process with streaming
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

    def _extract_user_message(self, task: Task) -> str:
        """Extract user message text from A2A task history."""
        try:
            if not (hasattr(task, "history") and task.history):
                return ""

            # Get the latest user message from history
            for message in reversed(task.history):
                if message.role == "user" and message.parts:
                    # Use ConversationManager static helper for consistency
                    from agent.state.conversation import ConversationManager

                    return ConversationManager.extract_text_from_parts(message.parts)
            return ""
        except Exception as e:
            logger.error(f"Error extracting user message: {e}")
            return ""

    def _find_direct_plugin(self, user_input: str) -> str | None:
        """Find plugin for direct routing based on keywords and patterns."""
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
        """Process task using direct plugin routing."""
        logger.info(f"Direct routing to plugin: {plugin_name}")

        try:
            from agent.capabilities import get_capability_executor

            logger.debug(f"Getting capability executor for plugin '{plugin_name}'")
            executor = get_capability_executor(plugin_name)
            if not executor:
                return f"Plugin '{plugin_name}' is not available or not properly configured."

            # Call the capability directly
            if callable(executor):
                import inspect

                if inspect.iscoroutinefunction(executor):
                    result = await executor(task)
                else:
                    result = executor(task)
                return result if isinstance(result, str) else str(result)
            else:
                return f"Plugin '{plugin_name}' executor is not callable."

        except Exception as e:
            logger.error(f"Error in direct routing to plugin '{plugin_name}': {e}")
            return f"Sorry, I encountered an error while processing your request: {str(e)}"

    async def _process_streaming(self, task: Task, updater, event_queue: EventQueue) -> None:
        """Process task with streaming response."""
        try:
            # Get current auth context
            auth_result = get_current_auth_for_executor()

            # Start streaming
            artifact_parts: list[Part] = []
            chunk_count = 0

            # Collect all streaming chunks
            async for chunk in self.dispatcher.streaming_handler.process_task_streaming(task, auth_result):
                chunk_count += 1

                if isinstance(chunk, str):
                    # Text chunk
                    part = Part(root=TextPart(text=chunk))
                    artifact_parts.append(part)
                elif isinstance(chunk, dict):
                    # Data chunk
                    part = Part(root=DataPart(data=chunk))
                    artifact_parts.append(part)

                # Send periodic updates every 10 chunks
                if chunk_count % 10 == 0:
                    batch_parts = artifact_parts[-10:]
                    artifact = new_artifact(
                        batch_parts,
                        name=f"{self.agent_name}-stream-batch-{chunk_count // 10}",
                        description="Streaming response batch",
                    )

                    update_event = TaskArtifactUpdateEvent(
                        task_id=task.id,
                        context_id=task.context_id,
                        artifact=artifact,
                        append=True,
                        last_chunk=False,
                        kind="artifact-update",
                    )
                    await event_queue.enqueue_event(update_event)

            # Send any remaining chunks
            remaining_chunks = chunk_count % 10
            if remaining_chunks > 0:
                batch_parts = artifact_parts[-remaining_chunks:]
                artifact = new_artifact(
                    batch_parts,
                    name=f"{self.agent_name}-stream-final",
                    description="Final streaming batch",
                )
                update_event = TaskArtifactUpdateEvent(
                    task_id=task.id,
                    context_id=task.context_id,
                    artifact=artifact,
                    append=True,
                    last_chunk=False,
                    kind="artifact-update",
                )
                await event_queue.enqueue_event(update_event)

            # Complete streaming
            await updater.complete()

        except Exception:
            raise

    async def _create_response_artifact(self, result: Any, task: Task, updater) -> None:
        """Create response artifact from result."""
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
            if "summary" in result:
                parts.append(Part(root=TextPart(text=result["summary"])))
            parts.append(Part(root=DataPart(data=result)))
        elif isinstance(result, list):
            # List of items
            parts.append(Part(root=DataPart(data={"items": result})))
        else:
            # Fallback to string representation
            parts.append(Part(root=TextPart(text=str(result))))

        # Create multi-modal artifact
        artifact = new_artifact(parts, name=f"{self.agent_name}-result", description=f"Response from {self.agent_name}")

        await updater.add_artifact(parts, name=artifact.name)
        await updater.complete()

    async def _requires_input(self, task: Task, context: RequestContext) -> bool:
        """Check if task requires additional input."""
        # Basic implementation - can be enhanced with actual logic
        return False
