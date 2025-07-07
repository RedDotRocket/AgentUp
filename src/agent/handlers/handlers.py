import logging
from collections.abc import Callable
from typing import Any

from a2a.types import Task

from ..config import load_config

# Import middleware decorators
from ..middleware import cached, logged, rate_limited, retryable, timed

# Load agent config to pull in project name
_config = load_config()
_project_name = _config.get("agent", {}).get("name", "Agent")

# Import shared utilities (with fallbacks for testing)
try:
    from ..utils.messages import ConversationContext, MessageProcessor
except ImportError:

    class ConversationContext:
        @classmethod
        def increment_message_count(cls, task_id):
            return 1

        @classmethod
        def get_message_count(cls, task_id):
            return 1

    class MessageProcessor:
        @staticmethod
        def extract_messages(task):
            return []

        @staticmethod
        def get_latest_user_message(messages):
            return None


# Separate import for extract_parameter with fallback
try:
    from ..utils.helpers import extract_parameter
except ImportError:

    def extract_parameter(text, param):
        return None


# Optional middleware decorators (no-ops if unavailable)
try:
    from ..middleware import cached, logged, rate_limited, retryable, timed, with_middleware
except ImportError:

    def cached(ttl=300):
        def decorator(f):
            return f

        return decorator

    def rate_limited(requests_per_minute=60):
        def decorator(f):
            return f

        return decorator

    def logged(level=None):
        def decorator(f):
            return f

        return decorator

    def retryable(max_attempts=3):
        def decorator(f):
            return f

        return decorator

    def timed():
        def decorator(f):
            return f

        return decorator

    def with_middleware(configs=None):
        def decorator(f):
            return f

        return decorator


# Optional AI decorator (no-op if unavailable)
try:
    from ..core.dispatcher import ai_function
except ImportError:

    def ai_function(description=None, parameters=None):
        def decorator(f):
            return f

        return decorator


logger = logging.getLogger(__name__)

# Handler registry - unified for all handlers (core, user, and individual)
_handlers: dict[str, Callable[[Task], str]] = {}

# Middleware configuration cache
_middleware_config: list[dict[str, Any]] | None = None
_global_middleware_applied = False

# State management configuration cache
_state_config: dict[str, Any] | None = None
_global_state_applied = False


def _load_middleware_config() -> list[dict[str, Any]]:
    """Load middleware configuration from agent config."""
    global _middleware_config
    if _middleware_config is not None:
        return _middleware_config

    try:
        from ..config import load_config

        config = load_config()
        _middleware_config = config.get("middleware", [])
        logger.debug(f"Loaded middleware config: {_middleware_config}")
        return _middleware_config
    except Exception as e:
        logger.warning(f"Could not load middleware config: {e}")
        _middleware_config = []
        return _middleware_config


def _load_state_config() -> dict[str, Any]:
    """Load state management configuration from agent config."""
    global _state_config
    if _state_config is not None:
        return _state_config

    try:
        from ..config import load_config

        config = load_config()
        _state_config = config.get("state_management", {})
        logger.debug(f"Loaded state config: {_state_config}")
        return _state_config
    except Exception as e:
        logger.warning(f"Could not load state config: {e}")
        _state_config = {}
        return _state_config


def _get_skill_config(skill_id: str) -> dict | None:
    """Get configuration for a specific skill."""
    try:
        from ..config import load_config

        config = load_config()
        skills = config.get("skills", [])

        for skill in skills:
            if skill.get("skill_id") == skill_id:
                return skill
        return None
    except Exception as e:
        logger.debug(f"Could not load skill config for '{skill_id}': {e}")
        return None


def _resolve_state_config(skill_id: str) -> dict:
    """Resolve state configuration for a skill (global or skill-specific)."""
    global_state_config = _load_state_config()
    skill_config = _get_skill_config(skill_id)

    if skill_config and "state_override" in skill_config:
        logger.info(f"Using skill-specific state override for '{skill_id}'")
        return skill_config["state_override"]

    return global_state_config


def _apply_state_to_handler(handler: Callable, skill_id: str) -> Callable:
    """Apply configured state management to a handler."""
    state_config = _resolve_state_config(skill_id)

    if not state_config.get("enabled", False):
        logger.debug(f"State management disabled for {skill_id}")
        return handler

    try:
        from ..state.decorators import with_state

        wrapped_handler = with_state([state_config])(handler)
        backend = state_config.get("backend", "memory")
        logger.info(f"Applied state management to handler '{skill_id}': backend={backend}")
        return wrapped_handler
    except Exception as e:
        logger.error(f"Failed to apply state management to handler '{skill_id}': {e}")
        return handler


def _resolve_middleware_config(skill_id: str) -> list[dict[str, Any]]:
    """Resolve middleware configuration for a skill (global or skill-specific)."""
    global_middleware_configs = _load_middleware_config()
    skill_config = _get_skill_config(skill_id)

    if skill_config and "middleware_override" in skill_config:
        logger.info(f"Using skill-specific middleware override for '{skill_id}'")
        return skill_config["middleware_override"]

    return global_middleware_configs


def _apply_middleware_to_handler(handler: Callable, skill_id: str) -> Callable:
    """Apply configured middleware to a handler."""
    middleware_configs = _resolve_middleware_config(skill_id)

    if not middleware_configs:
        logger.debug(f"No middleware to apply to {skill_id}")
        return handler

    try:
        wrapped_handler = with_middleware(middleware_configs)(handler)
        middleware_names = [m.get("name") for m in middleware_configs]
        logger.info(f"Applied middleware to handler '{skill_id}': {middleware_names}")
        return wrapped_handler
    except Exception as e:
        logger.error(f"Failed to apply middleware to handler '{skill_id}': {e}")
        return handler


def register_handler(skill_id: str):
    """Decorator to register a skill handler by ID with automatic middleware and state application."""

    def decorator(func: Callable[[Task], str]):
        # Apply middleware automatically based on agent config
        wrapped_func = _apply_middleware_to_handler(func, skill_id)
        # Apply state management automatically based on agent config
        wrapped_func = _apply_state_to_handler(wrapped_func, skill_id)
        _handlers[skill_id] = wrapped_func
        logger.debug(f"Registered handler with middleware and state: {skill_id}")
        return wrapped_func

    return decorator


def register_handler_function(skill_id: str, handler: Callable[[Task], str]) -> None:
    """Register a handler function directly (for plugins and dynamic registration)."""
    wrapped_handler = _apply_middleware_to_handler(handler, skill_id)
    wrapped_handler = _apply_state_to_handler(wrapped_handler, skill_id)
    _handlers[skill_id] = wrapped_handler
    logger.debug(f"Registered handler function with middleware and state: {skill_id}")


def get_handler(skill_id: str) -> Callable[[Task], str] | None:
    """Retrieve a registered handler by ID from unified registry, demo handlers, and registry skills."""
    # First check unified handlers registry (includes core and individual handlers)
    handler = _handlers.get(skill_id)
    if handler:
        return handler

    # No handler found
    return None


@register_handler("status")
async def handle_status(task: Task) -> str:
    """Get agent status and information."""
    return f"{_project_name} is operational and ready to process tasks. Task ID: {task.id}"


@register_handler("capabilities")
async def handle_capabilities(task: Task) -> str:
    """list agent capabilities and available skills."""
    skills = list(_handlers.keys())
    lines = "\n".join(f"- {skill}" for skill in skills)
    return f"{_project_name} capabilities:\n{lines}"


def get_all_handlers() -> dict[str, Callable[[Task], str]]:
    """Return a copy of the skill handler registry."""
    return _handlers.copy()


def list_skills() -> list[str]:
    """list all available skill IDs."""
    return list(_handlers.keys())


def apply_global_middleware() -> None:
    """Apply middleware to all existing registered handlers (for retroactive application)."""
    global _global_middleware_applied

    if _global_middleware_applied:
        logger.debug("Global middleware already applied, skipping")
        return

    middleware_configs = _load_middleware_config()
    if not middleware_configs:
        logger.debug("No global middleware to apply")
        _global_middleware_applied = True
        return

    # Re-wrap all existing handlers with middleware
    for skill_id, handler in list(_handlers.items()):
        try:
            # Only apply if not already wrapped (simple check)
            if not hasattr(handler, "_agentup_middleware_applied"):
                wrapped_handler = _apply_middleware_to_handler(handler, skill_id)
                wrapped_handler._agentup_middleware_applied = True
                _handlers[skill_id] = wrapped_handler
                logger.debug(f"Applied global middleware to existing handler: {skill_id}")
        except Exception as e:
            logger.error(f"Failed to apply global middleware to {skill_id}: {e}")

    _global_middleware_applied = True
    logger.info(f"Applied global middleware to {len(_handlers)} handlers")


def apply_global_state() -> None:
    """Apply state management to all existing registered handlers (for retroactive application)."""
    global _global_state_applied

    if _global_state_applied:
        logger.debug("Global state already applied, skipping")
        return

    state_config = _load_state_config()
    if not state_config.get("enabled", False):
        logger.debug("State management disabled globally")
        _global_state_applied = True
        return

    # Re-wrap all existing handlers with state management
    for skill_id, handler in list(_handlers.items()):
        try:
            # Only apply if not already wrapped (simple check)
            if not hasattr(handler, "_agentup_state_applied"):
                wrapped_handler = _apply_state_to_handler(handler, skill_id)
                wrapped_handler._agentup_state_applied = True
                _handlers[skill_id] = wrapped_handler
                logger.debug(f"Applied global state management to existing handler: {skill_id}")
        except Exception as e:
            logger.error(f"Failed to apply global state management to {skill_id}: {e}")

    _global_state_applied = True
    logger.info(f"Applied global state management to {len(_handlers)} handlers")


def reset_middleware_cache() -> None:
    """Reset middleware configuration cache (useful for testing or config reloading)."""
    global _middleware_config, _global_middleware_applied
    _middleware_config = None
    _global_middleware_applied = False
    logger.debug("Reset middleware configuration cache")


def reset_state_cache() -> None:
    """Reset state configuration cache (useful for testing or config reloading)."""
    global _state_config, _global_state_applied
    _state_config = None
    _global_state_applied = False
    logger.debug("Reset state configuration cache")


def get_middleware_info() -> dict[str, Any]:
    """Get information about current middleware configuration and application status."""
    middleware_configs = _load_middleware_config()
    return {
        "config": middleware_configs,
        "applied_globally": _global_middleware_applied,
        "total_handlers": len(_handlers),
        "middleware_names": [m.get("name") for m in middleware_configs],
    }


def get_state_info() -> dict[str, Any]:
    """Get information about current state configuration and application status."""
    state_config = _load_state_config()
    return {
        "config": state_config,
        "applied_globally": _global_state_applied,
        "total_handlers": len(_handlers),
        "enabled": state_config.get("enabled", False),
        "backend": state_config.get("backend", "memory"),
    }


"""
The echo handler is an out of the box, simple handler that echoes back user messages.
It's used for testing and demonstration purposes.
"""


@register_handler("echo")
@ai_function(
    description="Echo back user messages with optional modifications",
    parameters={
        "message": {"type": "string", "description": "Message to echo back"},
        "format": {"type": "string", "description": "Format style (uppercase, lowercase, title)"},
    },
)
@rate_limited(requests_per_minute=120)
@timed()
async def handle_echo(task: Task) -> str:
    """Enhanced echo handler with formatting options."""
    messages = MessageProcessor.extract_messages(task)
    latest = MessageProcessor.get_latest_user_message(messages)
    metadata = getattr(task, "metadata", {}) or {}

    echo_msg = metadata.get("message")
    style = metadata.get("format", "normal")

    if not echo_msg and latest:
        echo_msg = latest.get("content") if isinstance(latest, dict) else getattr(latest, "content", "")

    if not echo_msg:
        return "Echo: No message to echo back!"

    if style == "uppercase":
        echo_msg = echo_msg.upper()
    elif style == "lowercase":
        echo_msg = echo_msg.lower()
    elif style == "title":
        echo_msg = echo_msg.title()

    ConversationContext.increment_message_count(task.id)
    return f"Echo: {echo_msg}"


@register_handler("ai_assistant")
@ai_function(
    description="AI-powered assistant for various tasks with state management",
    parameters={
        "query": {"type": "string", "description": "User query or request"},
        "context": {"type": "string", "description": "Additional context for the request"},
    },
)
async def handle_ai_assistant(task: Task, context=None, context_id=None) -> str:
    """AI-powered assistant handler with state management capabilities."""

    # Extract user message using proper A2A Part structure
    user_message = "No message provided"
    if task.history and len(task.history) > 0:
        latest_message = task.history[-1]
        if latest_message.parts and len(latest_message.parts) > 0:
            for part in latest_message.parts:
                if hasattr(part, "root") and hasattr(part.root, "kind"):
                    if part.root.kind == "text" and hasattr(part.root, "text"):
                        user_message = part.root.text
                        break

    response_parts = []

    # Use state management if available
    if context and context_id:
        try:
            # Get conversation count
            conversation_count = await context.get_variable(context_id, "conversation_count", 0)
            conversation_count += 1
            await context.set_variable(context_id, "conversation_count", conversation_count)

            # Store user preferences if mentioned
            if "favorite" in user_message.lower() or "prefer" in user_message.lower():
                preferences = await context.get_variable(context_id, "preferences", {})
                # Simple preference extraction (you could make this more sophisticated)
                if "color" in user_message.lower():
                    colors = ["red", "blue", "green", "yellow", "purple", "orange", "pink", "black", "white"]
                    for color in colors:
                        if color in user_message.lower():
                            preferences["favorite_color"] = color
                            break
                await context.set_variable(context_id, "preferences", preferences)
                logger.info(f"Updated preferences for {context_id}: {preferences}")

            # Add to conversation history
            await context.add_to_history(context_id, "user", user_message, {"count": conversation_count})

            # Get recent conversation history
            recent_history = await context.get_history(context_id, limit=5)
            preferences = await context.get_variable(context_id, "preferences", {})

            # Build context-aware response
            if "remember" in user_message.lower() or "what" in user_message.lower():
                if preferences:
                    response_parts.append(f"I remember your preferences: {preferences}")
                if len(recent_history) > 1:
                    response_parts.append(f"We've had {len(recent_history)} exchanges in this conversation.")
            else:
                response_parts.append(f"Hello! I'm your AI assistant (conversation #{conversation_count}).")
                if preferences:
                    response_parts.append(
                        f"I remember you like: {', '.join(f'{k}: {v}' for k, v in preferences.items())}"
                    )
                response_parts.append(f"You said: {user_message}")
                response_parts.append("I'm here to help with various tasks. Try asking me to remember something!")

            logger.info(f"AI Assistant used state - Context: {context_id}, Count: {conversation_count}")

        except Exception as e:
            logger.error(f"AI Assistant state error: {e}")
            response_parts.append(f"I'm having trouble with my memory right now: {e}")
    else:
        # Fallback without state
        response_parts.append("Something went wrong with the conversation context.")
        response_parts.append(f"You said: {user_message}")
        logger.info("AI Assistant running without state management")

    return " ".join(response_parts)
