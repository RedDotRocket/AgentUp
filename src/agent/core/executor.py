import re
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
    new_data_artifact,
    new_task,
)
from a2a.utils.errors import ServerError

from agent.config.a2a import BaseAgent

logger = structlog.get_logger(__name__)


class GenericAgentExecutor(AgentExecutor):
    def __init__(self, agent: BaseAgent | AgentCard):
        self.agent = agent
        self.supports_streaming = getattr(agent, "supports_streaming", False)

        # Handle both BaseAgent and AgentCard
        if isinstance(agent, AgentCard):
            self.agent_name = agent.name
        else:
            self.agent_name = agent.agent_name

        # Load config for routing
        from agent.config import Config

        # Parse plugins for direct routing based on keywords/patterns
        self.plugins = {}
        for plugin_data in Config.plugins:
            if plugin_data.enabled:
                plugin_id = plugin_data.plugin_id
                keywords = plugin_data.keywords or []
                patterns = plugin_data.patterns or []

                self.plugins[plugin_id] = {
                    "keywords": keywords,
                    "patterns": patterns,
                    "name": plugin_data.name or plugin_id,
                    "description": plugin_data.description or "",
                    "priority": plugin_data.priority or 100,
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
                # Process with dispatcher - AI routing
                if self.supports_streaming:
                    # Stream responses incrementally
                    await self._process_streaming(task, updater, event_queue)
                else:
                    # Process synchronously - dispatcher handles routing internally
                    result = await self.dispatcher.process_task(task)
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

        for plugin_id, plugin_info in sorted_plugins:
            # Check keywords
            keywords = plugin_info.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in user_input_lower:
                    logger.debug(f"Keyword '{keyword}' matched for plugin '{plugin_id}'")
                    return plugin_id

            # Check patterns
            patterns = plugin_info.get("patterns", [])
            for pattern in patterns:
                try:
                    if re.search(pattern, user_input, re.IGNORECASE):
                        logger.debug(f"Pattern '{pattern}' matched for plugin '{plugin_id}'")
                        return plugin_id
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}' in plugin '{plugin_id}': {e}")

        return None

    async def _process_direct_routing(self, task: Task, plugin_id: str) -> str:
        logger.info(f"Direct routing to plugin: {plugin_id}")

        try:
            # Get capability executor for the plugin
            from agent.capabilities import get_capability_executor

            executor = get_capability_executor(plugin_id)
            if not executor:
                return f"Plugin '{plugin_id}' is not available or not properly configured."

            # Call the capability directly
            result = await executor(task)
            return result if isinstance(result, str) else str(result)

        except Exception as e:
            logger.error(f"Error in direct routing to plugin '{plugin_id}': {e}")
            return f"Sorry, I encountered an error while processing your request: {str(e)}"

    async def _process_streaming(
        self,
        task: Task,
        updater: TaskUpdater,
        event_queue: EventQueue,
    ) -> None:
        try:
            # Start streaming
            stream = await self.dispatcher.process_task_streaming(task)

            artifact_parts: list[Part] = []
            chunk_count = 0

            async for chunk in stream:
                chunk_count += 1

                if isinstance(chunk, str):
                    # Text chunk - A2A SDK structure
                    part = Part(root=TextPart(text=chunk))
                    artifact_parts.append(part)

                    # Send incremental update
                    artifact = new_artifact(
                        [part], name=f"{self.agent_name}-stream-{chunk_count}", description="Streaming response"
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

                elif isinstance(chunk, dict):
                    # Data chunk - A2A SDK structure
                    part = Part(root=DataPart(data=chunk))
                    artifact_parts.append(part)

                    artifact = new_data_artifact(
                        chunk,
                        name=f"{self.agent_name}-data-{chunk_count}",
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

            # Final update
            if artifact_parts:
                final_artifact = new_artifact(
                    artifact_parts, name=f"{self.agent_name}-complete", description="Complete response"
                )
                await updater.add_artifact(artifact_parts, name=final_artifact.name)

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
