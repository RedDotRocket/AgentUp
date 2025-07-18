"""
Service-oriented agent executor for AgentUp framework.
"""

from typing import Any

import structlog
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCard, Task, TaskState
from a2a.utils import new_agent_text_message, new_task

logger = structlog.get_logger(__name__)


class ServiceAgentExecutor(AgentExecutor):
    def __init__(self, services: dict[str, Any]):
        """
        Initialize the service executor.

        Args:
            services: Dictionary of initialized services
        """
        self.services = services
        self.logger = structlog.get_logger(self.__class__.__name__)

        # Get the capability registry service
        self.capabilities = services.get("capabilityregistry")
        if not self.capabilities:
            raise RuntimeError("CapabilityRegistry service not available")

    @property
    def agent(self) -> AgentCard:
        """Get the agent card."""
        # Import here to avoid circular imports
        from agent.api.routes import create_agent_card

        return create_agent_card()

    async def execute_task(self, task: Task) -> str:
        """Execute a task using the service layer following A2A protocol.

        Args:
            task: A2A Task object with message history

        Returns:
            Task execution result
        """
        try:
            # Extract user message from A2A task history
            user_message = self._extract_user_message(task)
            self.logger.info(f"Processing user message: {user_message[:100]}...")

            # Determine which capability to invoke based on message content
            capability_id = self._route_message_to_capability(user_message)
            self.logger.info(f"Routed to capability: {capability_id}")

            # Get authentication result from context if available
            auth_result = None
            try:
                from agent.security.context import get_current_auth

                auth_result = get_current_auth()
            except ImportError:
                self.logger.debug("Security module not available")

            # Execute the capability through the registry (handles auth, middleware, etc.)
            result = await self.capabilities.execute(capability_id, task, auth_result)

            self.logger.debug(f"Task {capability_id} completed successfully")
            return result

        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            return f"Task execution failed: {str(e)}"

    def _extract_user_message(self, task: Task) -> str:
        """Extract user message text from A2A task history.

        Args:
            task: A2A Task object

        Returns:
            User message text or empty string
        """
        try:
            self.logger.info(f"DEBUG: Task type: {type(task)}")
            self.logger.info(f"DEBUG: Task hasattr history: {hasattr(task, 'history')}")

            if hasattr(task, "history"):
                self.logger.info(f"DEBUG: Task history length: {len(task.history) if task.history else 0}")
                self.logger.info(f"DEBUG: Task history: {task.history}")

            if not (hasattr(task, "history") and task.history):
                self.logger.debug("No task history available")
                return ""

            # Get the latest user message from history
            for i, message in enumerate(reversed(task.history)):
                self.logger.info(f"DEBUG: Message {i} type: {type(message)}")
                self.logger.info(f"DEBUG: Message {i} hasattr role: {hasattr(message, 'role')}")
                if hasattr(message, "role"):
                    self.logger.info(f"DEBUG: Message {i} role: {message.role}")

                if hasattr(message, "role") and message.role == "user":
                    self.logger.info(f"DEBUG: Found user message, hasattr parts: {hasattr(message, 'parts')}")
                    if hasattr(message, "parts"):
                        self.logger.info(f"DEBUG: Parts length: {len(message.parts) if message.parts else 0}")
                        self.logger.info(f"DEBUG: Parts: {message.parts}")

                    if hasattr(message, "parts") and message.parts:
                        for j, part in enumerate(message.parts):
                            self.logger.info(f"DEBUG: Part {j} type: {type(part)}")
                            self.logger.info(f"DEBUG: Part {j} hasattr kind: {hasattr(part, 'kind')}")
                            self.logger.info(f"DEBUG: Part {j} hasattr root: {hasattr(part, 'root')}")

                            # Handle A2A Part structure
                            if hasattr(part, "kind"):
                                self.logger.info(f"DEBUG: Part {j} kind: {part.kind}")
                                if part.kind == "text":
                                    self.logger.info(f"DEBUG: Part {j} hasattr text: {hasattr(part, 'text')}")
                                    if hasattr(part, "text"):
                                        self.logger.info(f"DEBUG: Part {j} text: {part.text}")
                                        return part.text
                            # Handle nested structure if SDK wraps parts
                            elif hasattr(part, "root") and hasattr(part.root, "kind"):
                                self.logger.info(f"DEBUG: Part {j} root kind: {part.root.kind}")
                                if part.root.kind == "text" and hasattr(part.root, "text"):
                                    self.logger.info(f"DEBUG: Part {j} root text: {part.root.text}")
                                    return part.root.text

            self.logger.debug("No user text message found in task history")
            return ""

        except Exception as e:
            self.logger.error(f"Error extracting user message: {e}")
            import traceback

            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return ""

    def _route_message_to_capability(self, user_message: str) -> str:
        """Route user message to appropriate capability.

        Args:
            user_message: User's text message

        Returns:
            Capability ID to invoke
        """
        self.logger.info(f"DEBUG: Routing message: '{user_message}'")

        if not user_message:
            self.logger.info("DEBUG: Empty message, routing to echo")
            return "echo"  # Default fallback

        message_lower = user_message.lower().strip()
        self.logger.info(f"DEBUG: Normalized message: '{message_lower}'")

        # Simple keyword-based routing for AgentUp core capabilities
        if any(keyword in message_lower for keyword in ["status", "health", "ping"]):
            self.logger.info("DEBUG: Routing to status")
            return "status"
        elif any(keyword in message_lower for keyword in ["capabilities", "skills", "what can you do", "help"]):
            self.logger.info("DEBUG: Routing to capabilities")
            return "capabilities"
        elif any(keyword in message_lower for keyword in ["echo", "repeat", "say"]):
            self.logger.info("DEBUG: Routing to echo")
            return "echo"
        elif any(keyword in message_lower for keyword in ["system", "info", "system info", "get system info"]):
            self.logger.info("DEBUG: Routing to system_info")
            return "system_info"
        else:
            # Default to echo for unknown requests
            self.logger.info("DEBUG: No match found, routing to echo")
            return "echo"

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute method required by AgentExecutor interface with A2A compliance."""
        task = context.current_task

        # Create task if not exists (A2A protocol requirement)
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            self.logger.debug(f"Created new task: {task.id}")

        updater = TaskUpdater(event_queue, task.id, task.contextId)

        try:
            # Update to working status (A2A task lifecycle)
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Processing request for task {task.id}",
                    task.contextId,
                    task.id,
                ),
                final=False,
            )
            self.logger.info(f"Task {task.id} transitioned to working state")

            # Execute the task using our service layer
            result = await self.execute_task(task)

            # Validate result
            if not result or not isinstance(result, str):
                raise ValueError("Capability returned invalid result")

            # Send successful completion (A2A terminal state)
            await updater.update_status(
                TaskState.completed,
                new_agent_text_message(result, task.contextId, task.id),
                final=True,
            )
            self.logger.info(f"Task {task.id} completed successfully")

        except ValueError as e:
            # Handle validation errors (A2A error handling)
            self.logger.error(f"Validation error for task {task.id}: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(f"Invalid request: {str(e)}", task.contextId, task.id),
                final=True,
            )

        except Exception as e:
            # Handle unexpected errors (A2A error handling)
            self.logger.error(f"Execution failed for task {task.id}: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(f"Internal error: {str(e)}", task.contextId, task.id),
                final=True,
            )

    async def cancel(self, task_id: str) -> bool:
        """Cancel method required by AgentExecutor interface."""
        self.logger.info(f"Task cancellation requested for: {task_id}")
        # Simple implementation - in practice this would track and cancel running tasks
        return True
