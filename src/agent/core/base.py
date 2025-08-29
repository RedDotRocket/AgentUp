"""Base executor with core primitives for AgentUp execution system."""

import threading
from abc import ABC, abstractmethod

import structlog
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCard, InvalidParamsError, Task, TaskState
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError

from agent.config.model import BaseAgent

logger = structlog.get_logger(__name__)

# Thread-local storage for auth context
_thread_local = threading.local()


def set_current_auth_for_executor(auth_result) -> None:
    """Store auth result in thread-local storage for executor access."""
    _thread_local.auth_result = auth_result


def get_current_auth_for_executor():
    """Retrieve auth result from thread-local storage."""
    return getattr(_thread_local, "auth_result", None)


class AgentExecutorBase(AgentExecutor, ABC):
    """Base executor containing only core A2A and authentication primitives.

    This class provides the shared infrastructure for all agent execution types:
    - A2A protocol integration
    - Authentication context management
    - Event queue and streaming infrastructure
    - Basic task validation and error handling

    Concrete execution strategies inherit from this base and implement
    the specific execution patterns (reactive, iterative, etc.).
    """

    def __init__(self, agent: BaseAgent | AgentCard) -> None:
        self.agent = agent

        # Determine agent name
        if isinstance(agent, AgentCard):
            self.agent_name = agent.name
        else:
            self.agent_name = agent.agent_name

        # Check streaming support
        if hasattr(agent, "supports_streaming"):
            self.supports_streaming = getattr(agent, "supports_streaming", False)
        elif hasattr(agent, "capabilities") and getattr(agent, "capabilities", None):
            capabilities = getattr(agent, "capabilities", None)
            self.supports_streaming = getattr(capabilities, "streaming", False) if capabilities else False
        else:
            self.supports_streaming = False

    def _validate_request(self, context: RequestContext) -> str | None:
        """Validate the incoming request context.

        Returns:
            Error message if validation fails, None if valid.
        """
        # Basic validation - can be extended by subclasses
        return None

    def _ensure_task_exists(self, context: RequestContext, event_queue: EventQueue) -> Task:
        """Ensure a task exists in the context, creating one if needed.

        Args:
            context: Request context
            event_queue: Event queue for task creation

        Returns:
            The task from context or newly created task

        Raises:
            ServerError: If no task or message is available
        """
        task = context.current_task

        if not task:
            if context.message:
                task = new_task(context.message)
                # Note: In real implementation, would need to properly add task to context
                # This is a simplified version for the base class
            else:
                raise ServerError(error=InvalidParamsError(data={"reason": "No task or message provided"}))

        return task

    def _create_task_updater(self, task: Task, event_queue: EventQueue) -> TaskUpdater:
        """Create a task updater for the given task.

        Args:
            task: The task to create updater for
            event_queue: Event queue for updates

        Returns:
            TaskUpdater instance
        """
        return TaskUpdater(event_queue, task.id, task.context_id)

    async def _transition_to_working(self, task: Task, updater: TaskUpdater) -> None:
        """Transition task to working state with standard message.

        Args:
            task: The task being processed
            updater: Task updater for state changes
        """
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                f"Processing request for task {task.id} using {self.agent_name}.",
                task.context_id,
                task.id,
            ),
            final=False,
        )

    async def _handle_execution_error(self, error: Exception, task: Task, updater: TaskUpdater) -> None:
        """Handle execution errors with appropriate task state updates.

        Args:
            error: The exception that occurred
            task: The task being processed
            updater: Task updater for state changes
        """
        if isinstance(error, ValueError) and "unsupported" in str(error).lower():
            logger.warning(f"Unsupported operation requested: {error}")
            await updater.update_status(
                TaskState.rejected,
                new_agent_text_message(
                    f"This operation is not supported: {str(error)}",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )
        else:
            logger.error(f"Error processing task: {error}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    f"I encountered an error processing your request: {str(error)}",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )

    @abstractmethod
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute the agent with the given context.

        This method must be implemented by concrete execution strategies.

        Args:
            context: Request context containing task and message data
            event_queue: Event queue for status updates and results
        """
        pass

    async def execute_streaming(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute task with streaming support.

        Default implementation delegates to regular execute method.
        Subclasses can override for specialized streaming behavior.

        Args:
            context: Request context
            event_queue: Event queue for streaming updates
        """
        await self.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current task.

        Default implementation provides basic cancellation logic.
        Subclasses can override for specialized cancellation behavior.

        Args:
            context: Request context
            event_queue: Event queue for cancellation updates
        """
        task = context.current_task

        if not task:
            raise ServerError(error=InvalidParamsError(data={"reason": "No task to cancel"}))

        # Check if task can be canceled
        if task.status.state in [
            TaskState.completed,
            TaskState.failed,
            TaskState.canceled,
            TaskState.rejected,
        ]:
            from a2a.types import UnsupportedOperationError

            raise ServerError(
                error=UnsupportedOperationError(
                    data={"reason": f"Task in state '{task.status.state}' cannot be canceled"}
                )
            )

        # Update task status to canceled
        updater = self._create_task_updater(task, event_queue)
        await updater.update_status(
            TaskState.canceled,
            new_agent_text_message(
                "Task has been canceled by user request.",
                task.context_id,
                task.id,
            ),
            final=True,
        )
