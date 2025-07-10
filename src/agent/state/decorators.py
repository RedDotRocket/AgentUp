import inspect
from collections.abc import Callable
from typing import Any

import structlog
from a2a.types import Task

from .context import get_context_manager

logger = structlog.get_logger(__name__)


def _preserve_ai_attributes(wrapper: Callable, original: Callable) -> None:
    """Preserve AI function attributes and middleware/state flags on the wrapper."""
    if hasattr(original, "_is_ai_function"):
        wrapper._is_ai_function = original._is_ai_function
    if hasattr(original, "_ai_function_schema"):
        wrapper._ai_function_schema = original._ai_function_schema
    if hasattr(original, "_agentup_middleware_applied"):
        wrapper._agentup_middleware_applied = original._agentup_middleware_applied
    if hasattr(original, "_agentup_state_applied"):
        wrapper._agentup_state_applied = original._agentup_state_applied


def _inject_state_if_supported(
    func: Callable, task: Task, backend: str, backend_config: dict, context_id: str, kwargs: dict
) -> None:
    """Inject state context into kwargs if the function supports it."""
    sig = inspect.signature(func)
    accepts_context = "context" in sig.parameters
    accepts_context_id = "context_id" in sig.parameters

    if accepts_context or accepts_context_id:
        context = get_context_manager(backend, **backend_config)

        if accepts_context:
            kwargs["context"] = context
        if accepts_context_id:
            kwargs["context_id"] = context_id


def _create_state_wrapper(
    func: Callable, backend: str, backend_config: dict, context_id_generator: Callable[[Task], str], error_prefix: str
) -> Callable:
    """Create a state management wrapper for a function."""

    async def wrapper(task: Task, *args, **kwargs):
        try:
            context_id = context_id_generator(task)
            _inject_state_if_supported(func, task, backend, backend_config, context_id, kwargs)
            return await func(task, *args, **kwargs)
        except Exception as e:
            logger.error(f"{error_prefix} error in {func.__name__}: {e}")
            return await func(task, *args, **kwargs)

    _preserve_ai_attributes(wrapper, func)
    return wrapper


def with_state(state_configs: list[dict[str, Any]]):
    """Apply state management based on configuration."""

    def decorator(func: Callable) -> Callable:
        if not state_configs:
            return func

        primary_config = state_configs[0]
        if not primary_config.get("enabled", True):
            return func

        backend = primary_config.get("backend", "memory")
        backend_config = primary_config.get("config", {})

        def context_id_generator(task: Task) -> str:
            # Check metadata for context_id first, then contextId, then fall back to task id
            context_id = task.id
            if hasattr(task, "metadata") and task.metadata:
                context_id = task.metadata.get("context_id", getattr(task, "contextId", task.id))
            else:
                context_id = getattr(task, "contextId", task.id)
            return context_id

        return _create_state_wrapper(func, backend, backend_config, context_id_generator, "State management")

    return decorator


def stateful_conversation(backend: str = "memory", **backend_config):
    """Decorator for conversation-specific state management."""

    def decorator(func: Callable) -> Callable:
        def context_id_generator(task: Task) -> str:
            # Check metadata for conversation_id first, then contextId, then fall back to task.id
            conversation_id = None
            if hasattr(task, "metadata") and task.metadata:
                conversation_id = task.metadata.get("conversation_id")
            if not conversation_id:
                conversation_id = getattr(task, "contextId", task.id)
            return f"conversation:{conversation_id}"

        return _create_state_wrapper(func, backend, backend_config, context_id_generator, "Conversation state")

    return decorator


def stateful_user(backend: str = "memory", **backend_config):
    """Decorator for user-specific state management."""

    def decorator(func: Callable) -> Callable:
        def context_id_generator(task: Task) -> str:
            # Check metadata for user_id first, then fall back to anonymous
            user_id = "anonymous"
            if hasattr(task, "metadata") and task.metadata:
                user_id = task.metadata.get("user_id", "anonymous")
            return f"user:{user_id}"

        return _create_state_wrapper(func, backend, backend_config, context_id_generator, "User state")

    return decorator


def stateful_session(backend: str = "memory", **backend_config):
    """Decorator for session-specific state management."""

    def decorator(func: Callable) -> Callable:
        def context_id_generator(task: Task) -> str:
            # Check metadata for session_id first, then fall back to task id
            session_id = task.id
            if hasattr(task, "metadata") and task.metadata:
                session_id = task.metadata.get("session_id", task.id)
            return f"session:{session_id}"

        return _create_state_wrapper(func, backend, backend_config, context_id_generator, "Session state")

    return decorator


def stateful(storage: str = "memory", **storage_kwargs):
    """Legacy decorator to add state management to handlers."""

    def decorator(func: Callable) -> Callable:
        def context_id_generator(task: Task) -> str:
            # Check metadata for context_id first, then contextId, then fall back to task id
            context_id = task.id
            if hasattr(task, "metadata") and task.metadata:
                context_id = task.metadata.get("context_id", getattr(task, "contextId", task.id))
            else:
                context_id = getattr(task, "contextId", task.id)
            return context_id

        return _create_state_wrapper(func, storage, storage_kwargs, context_id_generator, "State management")

    return decorator
