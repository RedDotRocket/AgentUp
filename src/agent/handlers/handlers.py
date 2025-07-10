from collections.abc import Callable
from typing import Any

import structlog
from a2a.types import Task

from ..config import load_config

# Import middleware decorators
from ..middleware import rate_limited, retryable, timed

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
    from ..middleware import rate_limited, retryable, timed, with_middleware
except ImportError:

    def rate_limited(requests_per_minute=60):
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


logger = structlog.get_logger(__name__)

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


def _get_plugin_config(plugin_id: str) -> dict | None:
    """Get configuration for a specific plugin."""
    try:
        from ..config import load_config

        config = load_config()
        plugins = config.get("plugins", [])

        for plugin in plugins:
            if plugin.get("plugin_id") == plugin_id:
                return plugin
        return None
    except Exception as e:
        logger.debug(f"Could not load plugin config for '{plugin_id}': {e}")
        return None


def _resolve_state_config(plugin_id: str) -> dict:
    """Resolve state configuration for a plugin (global or plugin-specific)."""
    global_state_config = _load_state_config()
    plugin_config = _get_plugin_config(plugin_id)

    if plugin_config and "state_override" in plugin_config:
        logger.info(f"Using plugin-specific state override for '{plugin_id}'")
        return plugin_config["state_override"]

    return global_state_config


def _apply_auth_to_handler(handler: Callable, plugin_id: str) -> Callable:
    """Apply authentication context to a handler."""
    from functools import wraps

    from ..security.context import create_capability_context, get_current_auth

    @wraps(handler)
    async def auth_wrapped_handler(task):
        # Get current authentication information
        auth_result = get_current_auth()

        # Create plugin context with authentication info
        plugin_context = create_capability_context(task, auth_result)

        # Check if handler accepts context parameter
        import inspect

        sig = inspect.signature(handler)

        if len(sig.parameters) > 1:
            # Handler accepts context parameter
            return await handler(task, plugin_context)
        else:
            # Legacy handler - just pass task
            return await handler(task)

    return auth_wrapped_handler


def _apply_state_to_handler(handler: Callable, plugin_id: str) -> Callable:
    """Apply configured state management to a handler."""
    state_config = _resolve_state_config(plugin_id)

    if not state_config.get("enabled", False):
        logger.debug(f"State management disabled for {plugin_id}")
        return handler

    try:
        from ..state.decorators import with_state

        # Mark the original handler as having state applied before wrapping
        handler._agentup_state_applied = True
        wrapped_handler = with_state([state_config])(handler)
        backend = state_config.get("backend", "memory")
        logger.info(f"Applied state management to handler '{plugin_id}': backend={backend}")
        return wrapped_handler
    except Exception as e:
        logger.error(f"Failed to apply state management to handler '{plugin_id}': {e}")
        return handler


def _resolve_middleware_config(plugin_id: str) -> list[dict[str, Any]]:
    """Resolve middleware configuration for a plugin (global or plugin-specific)."""
    global_middleware_configs = _load_middleware_config()
    plugin_config = _get_plugin_config(plugin_id)

    if plugin_config and "middleware_override" in plugin_config:
        logger.info(f"Using plugin-specific middleware override for '{plugin_id}'")
        return plugin_config["middleware_override"]

    return global_middleware_configs


def _apply_middleware_to_handler(handler: Callable, plugin_id: str) -> Callable:
    """Apply configured middleware to a handler."""
    middleware_configs = _resolve_middleware_config(plugin_id)

    if not middleware_configs:
        logger.debug(f"No middleware to apply to {plugin_id}")
        return handler

    try:
        # Mark the original handler as having middleware applied before wrapping
        handler._agentup_middleware_applied = True
        wrapped_handler = with_middleware(middleware_configs)(handler)
        middleware_names = [m.get("name") for m in middleware_configs]
        logger.info(f"Applied middleware to handler '{plugin_id}': {middleware_names}")
        return wrapped_handler
    except Exception as e:
        logger.error(f"Failed to apply middleware to handler '{plugin_id}': {e}")
        return handler


def register_handler(plugin_id: str):
    """Decorator to register a plugin handler by ID with automatic middleware, state, and auth application."""

    def decorator(func: Callable[[Task], str]):
        # Apply authentication context first
        wrapped_func = _apply_auth_to_handler(func, plugin_id)
        # Apply middleware automatically based on agent config
        wrapped_func = _apply_middleware_to_handler(wrapped_func, plugin_id)
        # Apply state management automatically based on agent config
        wrapped_func = _apply_state_to_handler(wrapped_func, plugin_id)
        _handlers[plugin_id] = wrapped_func
        logger.debug(f"Registered handler with auth, middleware and state: {plugin_id}")
        return wrapped_func

    return decorator


def register_handler_function(plugin_id: str, handler: Callable[[Task], str]) -> None:
    """Register a handler function directly (for plugins and dynamic registration)."""
    wrapped_handler = _apply_auth_to_handler(handler, plugin_id)
    wrapped_handler = _apply_middleware_to_handler(wrapped_handler, plugin_id)
    wrapped_handler = _apply_state_to_handler(wrapped_handler, plugin_id)
    _handlers[plugin_id] = wrapped_handler
    logger.debug(f"Registered handler function with auth, middleware and state: {plugin_id}")


def get_handler(plugin_id: str) -> Callable[[Task], str] | None:
    """Retrieve a registered handler by ID from unified registry, demo handlers, and registry plugins."""
    # First check unified handlers registry (includes core and individual handlers)
    handler = _handlers.get(plugin_id)
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
    """list agent capabilities and available plugins."""
    plugins = list(_handlers.keys())
    lines = "\n".join(f"- {plugin}" for plugin in plugins)
    return f"{_project_name} capabilities:\n{lines}"


def get_all_handlers() -> dict[str, Callable[[Task], str]]:
    """Return a copy of the plugin handler registry."""
    return _handlers.copy()


def list_plugins() -> list[str]:
    """list all available plugin IDs."""
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

    # Count handlers that already have middleware applied
    handlers_with_middleware = []
    handlers_needing_middleware = []

    for plugin_id, handler in _handlers.items():
        has_middleware_flag = hasattr(handler, "_agentup_middleware_applied")
        logger.debug(f"Handler '{plugin_id}' has middleware flag: {has_middleware_flag}")
        if has_middleware_flag:
            handlers_with_middleware.append(plugin_id)
        else:
            handlers_needing_middleware.append(plugin_id)

    logger.debug(f"Handlers with middleware: {handlers_with_middleware}")
    logger.debug(f"Handlers needing middleware: {handlers_needing_middleware}")

    # Only apply middleware to handlers that don't already have it
    for plugin_id in handlers_needing_middleware:
        handler = _handlers[plugin_id]
        try:
            wrapped_handler = _apply_middleware_to_handler(handler, plugin_id)
            _handlers[plugin_id] = wrapped_handler
            logger.debug(f"Applied global middleware to existing handler: {plugin_id}")
        except Exception as e:
            logger.error(f"Failed to apply global middleware to {plugin_id}: {e}")

    _global_middleware_applied = True

    if handlers_needing_middleware:
        logger.info(f"Applied global middleware to {len(handlers_needing_middleware)} handlers: {handlers_needing_middleware}")
    else:
        logger.debug("All handlers already have middleware applied during registration - no additional work needed")


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
    for plugin_id, handler in list(_handlers.items()):
        try:
            # Only apply if not already wrapped (simple check)
            if not hasattr(handler, "_agentup_state_applied"):
                wrapped_handler = _apply_state_to_handler(handler, plugin_id)
                _handlers[plugin_id] = wrapped_handler
                logger.debug(f"Applied global state management to existing handler: {plugin_id}")
            else:
                logger.debug(f"Handler '{plugin_id}' already has state management applied, skipping")
        except Exception as e:
            logger.error(f"Failed to apply global state management to {plugin_id}: {e}")

    _global_state_applied = True

    # Count handlers that actually needed global state management
    handlers_needing_state = [
        plugin_id for plugin_id, handler in _handlers.items()
        if not hasattr(handler, "_agentup_state_applied")
    ]

    if handlers_needing_state:
        logger.info(f"Applied global state management to {len(handlers_needing_state)} handlers: {handlers_needing_state}")
    else:
        logger.debug("All handlers already have state management applied during registration")


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
