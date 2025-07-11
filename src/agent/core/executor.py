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
    TaskStatus,
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

from agent.config.models import BaseAgent

logger = structlog.get_logger(__name__)


class GenericAgentExecutor(AgentExecutor):
    """A2A-compliant AgentExecutor with streaming and multi-modal support."""

    def __init__(self, agent: BaseAgent | AgentCard):
        self.agent = agent
        self.supports_streaming = getattr(agent, "supports_streaming", False)

        # Handle both BaseAgent and AgentCard
        if isinstance(agent, AgentCard):
            self.agent_name = agent.name
        else:
            self.agent_name = agent.agent_name

        # Load config for new routing system
        from agent.config import load_config

        config = load_config()

        # Parse routing configuration (implicit routing based on keywords/patterns)
        self.fallback_plugin = "echo"  # Default fallback plugin
        self.fallback_enabled = True

        # Parse plugins with implicit routing configuration
        self.plugins = {}
        for plugin_data in config.get("plugins", []):
            if plugin_data.get("enabled", True):
                plugin_id = plugin_data["plugin_id"]
                keywords = plugin_data.get("keywords", [])
                patterns = plugin_data.get("patterns", [])

                # Implicit routing: if keywords or patterns exist, direct routing is available
                has_direct_routing = bool(keywords or patterns)

                self.plugins[plugin_id] = {
                    "has_direct_routing": has_direct_routing,
                    "keywords": keywords,
                    "patterns": patterns,
                    "name": plugin_data.get("name", plugin_id),
                    "description": plugin_data.get("description", ""),
                    "priority": plugin_data.get("priority", 100),
                }

        # Initialize Function Dispatcher for AI routing (all plugins are available for AI routing)
        # AI routing is available when there are plugins without direct routing or as fallback
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

        updater = TaskUpdater(event_queue, task.id, task.contextId)

        try:
            # Transition to working state
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Processing request with for task {task.id} using {self.agent_name}.",
                    task.contextId,
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
                        task.contextId,
                        task.id,
                    ),
                    final=False,
                )
                return

            # New routing system: determine plugin and routing mode
            user_input = self._extract_user_message(task)
            target_plugin, routing_mode = self._determine_plugin_and_routing(user_input)

            if routing_mode == "ai":
                logger.info(
                    f"Processing task {task.id} using {routing_mode} routing (LLM will select appropriate functions)"
                )
            else:
                logger.info(f"Processing task {task.id} with plugin '{target_plugin}' using {routing_mode} routing")

            # Process based on determined routing mode
            if routing_mode == "ai":
                # Use AI routing - LLM selects the appropriate plugin
                if self.supports_streaming:
                    # Stream responses incrementally
                    await self._process_streaming(task, updater, event_queue)
                else:
                    # Process synchronously with AI
                    result = await self.dispatcher.process_task(task)
                    await self._create_response_artifact(result, task, updater)
            else:
                # Use direct routing - invoke specific plugin handler
                result = await self._process_direct_routing(task, target_plugin)
                await self._create_response_artifact(result, task, updater)

        except ValueError as e:
            # Handle unsupported operations gracefully (UnsupportedOperationError is a data model, not exception)
            if "unsupported" in str(e).lower():
                logger.warning(f"Unsupported operation requested: {e}")
                await updater.update_status(
                    TaskState.rejected,
                    new_agent_text_message(
                        f"This operation is not supported: {str(e)}",
                        task.contextId,
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
                    task.contextId,
                    task.id,
                ),
                final=True,
            )

    def _determine_plugin_and_routing(self, user_input: str) -> tuple[str, str]:
        """Determine which plugin and routing mode to use for the user input.

        New implicit routing logic:
        1. Check for direct routing matches (keywords/patterns) with priority
        2. If no direct match found, use AI routing
        3. If multiple direct matches, use highest priority plugin
        """
        import re

        if not user_input:
            return self.fallback_plugin, "direct"

        direct_matches = []

        # Check each plugin for direct routing matches
        for plugin_id, plugin_config in self.plugins.items():
            if not plugin_config["has_direct_routing"]:
                continue

            keywords = plugin_config.get("keywords", [])
            patterns = plugin_config.get("patterns", [])

            # Check keywords
            for keyword in keywords:
                if keyword.lower() in user_input.lower():
                    logger.debug(f"Matched keyword '{keyword}' for plugin '{plugin_id}'")
                    direct_matches.append((plugin_id, plugin_config["priority"]))
                    break  # Found a match for this plugin, no need to check more keywords

            # Check patterns if no keyword match found for this plugin
            if not any(match[0] == plugin_id for match in direct_matches):
                for pattern in patterns:
                    try:
                        if re.search(pattern, user_input, re.IGNORECASE):
                            logger.debug(f"Matched pattern '{pattern}' for plugin '{plugin_id}'")
                            direct_matches.append((plugin_id, plugin_config["priority"]))
                            break  # Found a match for this plugin
                    except re.error as e:
                        logger.warning(f"Invalid regex pattern '{pattern}' in plugin '{plugin_id}': {e}")

        # If direct matches found, use the highest priority one
        if direct_matches:
            # Sort by priority (lower number = higher priority)
            direct_matches.sort(key=lambda x: x[1])
            selected_plugin = direct_matches[0][0]
            logger.info(f"Direct routing to plugin '{selected_plugin}' (priority: {direct_matches[0][1]})")
            return selected_plugin, "direct"

        # No direct routing match found, use AI routing
        logger.info("No direct routing match found, using AI routing")
        return None, "ai"

    async def _process_direct_routing(self, task: Task, target_plugin: str = None) -> str:
        """Process task using direct handler routing (no AI)."""
        logger.info(f"Starting direct routing for task: {task}")

        # Use provided target plugin or fall back to fallback plugin
        plugin_id = target_plugin or self.fallback_plugin
        logger.info(f"Routing to plugin: {plugin_id}")

        # Get handler for the plugin
        from agent.handlers import get_handler

        handler = get_handler(plugin_id)

        if not handler:
            return f"No handler found for plugin: {plugin_id}"

        # Call handler directly
        try:
            result = await handler(task)
            return result if isinstance(result, str) else str(result)
        except Exception as e:
            logger.error(f"Error in handler {plugin_id}: {e}")
            return f"Error processing request: {str(e)}"

    def _extract_user_message(self, task: Task) -> str:
        """Extract user message from A2A task using A2A SDK structure."""
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

    async def _process_streaming(
        self,
        task: Task,
        updater: TaskUpdater,
        event_queue: EventQueue,
    ) -> None:
        """Process task with streaming support."""
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
                        contextId=task.contextId,
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
                        contextId=task.contextId,
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
        """Create appropriate artifact based on result type."""
        if not result:
            # Empty response
            await updater.update_status(
                TaskState.completed,
                new_agent_text_message(
                    "Task completed successfully.",
                    task.contextId,
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
        """Check if task requires additional input from user."""
        # This could be enhanced with actual logic to detect incomplete requests
        # For now, return False to proceed with processing
        return False

    def _validate_request(self, context: RequestContext) -> bool:
        return False

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> Task | None:
        """Cancel a running task if supported."""
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
                updater = TaskUpdater(event_queue, task.id, task.contextId)
                await updater.update_status(
                    TaskState.canceled,
                    new_agent_text_message(
                        "Task has been canceled by user request.",
                        task.contextId,
                        task.id,
                    ),
                    final=True,
                )

                # Return updated task
                task.status = TaskStatus(state=TaskState.canceled)
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
