from collections.abc import Callable
from typing import Any

import structlog
from a2a.types import Task

from agent.config import load_config

# Import middleware decorators
from agent.middleware import rate_limited, retryable, timed

# Load agent config to pull in project name
config = load_config()
_project_name = config.get("agent", {}).get("name", "Agent")

# Import shared utilities (with fallbacks for testing)
try:
    from agent.utils.messages import ConversationContext, MessageProcessor
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
    from agent.utils.helpers import extract_parameter
except ImportError:

    def extract_parameter(text, param):
        return None


# Optional middleware decorators (no-ops if unavailable)
try:
    from agent.middleware import rate_limited, retryable, timed, with_middleware
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
    from agent.core.dispatcher import ai_function
except ImportError:

    def ai_function(description=None, parameters=None):
        def decorator(f):
            return f

        return decorator


logger = structlog.get_logger(__name__)

# Capability registry - unified for all capability executors
_capabilities: dict[str, Callable[[Task], str]] = {}


def register_plugin_capability(plugin_config: dict[str, Any]) -> None:
    """Register plugin capability with framework scope enforcement.

    This function implements the exact pattern specified in SCOPE_DESIGN.md.
    It wraps plugin capabilities with scope enforcement at the framework level.

    Args:
        plugin_config: Dictionary containing capability_id and required_scopes
    """
    from agent.security.context import create_capability_context

    capability_id = plugin_config["capability_id"]
    required_scopes = plugin_config.get("required_scopes", [])

    # Get plugin's base executor from the plugin system
    try:
        from agent.plugins.integration import get_plugin_adapter

        plugin_adapter = get_plugin_adapter()
        if not plugin_adapter:
            logger.error(f"No plugin adapter available for capability: {capability_id}")
            return

        base_executor = plugin_adapter.get_capability_executor_for_capability(capability_id)
        if not base_executor:
            logger.error(f"No executor found for capability: {capability_id}")
            return

    except Exception as e:
        logger.error(f"Failed to get plugin executor for {capability_id}: {e}")
        return

    # Framework wraps with scope enforcement
    async def scope_enforced_executor(task: Task, context=None) -> str:
        """Scope-enforced wrapper that implements framework security."""
        import time

        start_time = time.time()

        # Create capability context if not provided
        if context is None:
            from agent.security.context import get_current_auth

            auth_result = get_current_auth()
            context = create_capability_context(task, auth_result)

        # Check scope access with comprehensive audit logging
        access_granted = True
        for scope in required_scopes:
            if not context.has_scope(scope):
                access_granted = False
                break

        # Comprehensive audit logging
        from agent.security.context import log_capability_access

        log_capability_access(
            capability_id=capability_id,
            user_id=context.user_id or "anonymous",
            user_scopes=context.user_scopes,
            required_scopes=required_scopes,
            success=access_granted,
        )

        # Framework enforces what plugin declared
        if not access_granted:
            raise PermissionError("Insufficient permissions")

        # Only execute if scopes pass
        try:
            result = await base_executor(task, context)

            # Log execution time
            execution_time = int((time.time() - start_time) * 1000)
            log_capability_access(
                capability_id=capability_id,
                user_id=context.user_id or "anonymous",
                user_scopes=context.user_scopes,
                required_scopes=required_scopes,
                success=True,
                execution_time_ms=execution_time,
            )

            return result
        except Exception as e:
            logger.error(f"Capability execution failed: {capability_id} - {e}")
            raise

    # Register the wrapped executor
    register_capability_function(capability_id, scope_enforced_executor)
    logger.info(f"Registered plugin capability with scope enforcement: {capability_id} (scopes: {required_scopes})")


def register_mcp_tool_as_capability(tool_name: str, mcp_client, tool_scopes: list[str]) -> None:
    """Register MCP tool as capability with scope enforcement.

    This function implements the exact pattern specified in SCOPE_DESIGN.md.
    It registers external MCP tools as capabilities with the same scope enforcement
    as local plugin capabilities.

    Args:
        tool_name: Name of the MCP tool
        mcp_client: MCP client instance to call the tool
        tool_scopes: List of required scopes for this tool
    """
    from agent.security.context import create_capability_context, get_current_auth

    async def mcp_tool_executor(task: Task, context=None) -> str:
        """MCP tool executor with scope enforcement."""
        import time

        start_time = time.time()

        # Create capability context if not provided
        if context is None:
            auth_result = get_current_auth()
            context = create_capability_context(task, auth_result)

        # Check scope access with comprehensive audit logging
        access_granted = True
        for scope in tool_scopes:
            if not context.has_scope(scope):
                access_granted = False
                break

        # Comprehensive audit logging for MCP tools
        from agent.security.context import log_capability_access

        log_capability_access(
            capability_id=f"mcp:{tool_name}",
            user_id=context.user_id or "anonymous",
            user_scopes=context.user_scopes,
            required_scopes=tool_scopes,
            success=access_granted,
        )

        # Framework enforces scopes for MCP tools
        if not access_granted:
            raise PermissionError("Insufficient permissions")

        # Extract parameters from task
        params = {}
        if hasattr(task, "metadata") and task.metadata:
            params = task.metadata
        elif hasattr(context, "params"):
            params = context.params

        try:
            # Call external MCP tool
            result = await mcp_client.call_tool(tool_name, params)

            # Log successful execution with timing
            execution_time = int((time.time() - start_time) * 1000)
            log_capability_access(
                capability_id=f"mcp:{tool_name}",
                user_id=context.user_id or "anonymous",
                user_scopes=context.user_scopes,
                required_scopes=tool_scopes,
                success=True,
                execution_time_ms=execution_time,
            )

            return str(result)
        except Exception as e:
            logger.error(f"MCP tool execution failed: {tool_name} - {e}")
            raise

    # Register like any other capability
    register_capability_function(tool_name, mcp_tool_executor)
    logger.info(f"Registered MCP tool as capability: {tool_name} (scopes: {tool_scopes})")


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
        from agent.config import load_config

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
        from agent.config import load_config

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


def _apply_auth_to_capability(executor: Callable, capability_id: str) -> Callable:
    """Apply authentication context to a capability executor."""
    from functools import wraps

    from agent.security.context import create_capability_context, get_current_auth

    @wraps(executor)
    async def auth_wrapped_executor(task):
        # Get current authentication information
        auth_result = get_current_auth()

        # Create capability context with authentication info
        capability_context = create_capability_context(task, auth_result)

        # Check if executor accepts context parameter
        import inspect

        sig = inspect.signature(executor)

        if len(sig.parameters) > 1:
            # Executor accepts context parameter
            return await executor(task, capability_context)
        else:
            # Legacy executor - just pass task
            return await executor(task)

    return auth_wrapped_executor


def _apply_state_to_capability(executor: Callable, capability_id: str) -> Callable:
    """Apply configured state management to a capability executor."""
    state_config = _resolve_state_config(capability_id)

    if not state_config.get("enabled", False):
        logger.debug(f"State management disabled for {capability_id}")
        return executor

    try:
        from agent.state.decorators import with_state

        # Mark the original executor as having state applied before wrapping
        executor._agentup_state_applied = True
        wrapped_executor = with_state([state_config])(executor)
        backend = state_config.get("backend", "memory")
        logger.debug(f"Applied state management to capability '{capability_id}': backend={backend}")
        return wrapped_executor
    except Exception as e:
        logger.error(f"Failed to apply state management to capability '{capability_id}': {e}")
        return executor


def _resolve_middleware_config(capability_id: str) -> list[dict[str, Any]]:
    """Resolve middleware configuration for a capability."""
    global_middleware_configs = _load_middleware_config()

    # Get the actual plugin name that provides this capability
    plugin_name = capability_id  # Default fallback
    try:
        from agent.plugins.integration import get_plugin_adapter

        adapter = get_plugin_adapter()
        if adapter:
            capability_info = adapter.get_capability_info(capability_id)
            if capability_info and "plugin_name" in capability_info:
                plugin_name = capability_info["plugin_name"]
                logger.debug(f"Resolved capability '{capability_id}' to plugin '{plugin_name}'")
    except Exception as e:
        logger.debug(f"Could not resolve plugin name for capability '{capability_id}': {e}")

    plugin_config = _get_plugin_config(plugin_name)

    # Check for plugin-specific middleware override
    if plugin_config and "middleware_override" in plugin_config:
        logger.info(f"Using plugin-specific middleware override for '{capability_id}'")
        return plugin_config["middleware_override"]

    # Use global middleware configuration
    return global_middleware_configs


def _apply_middleware_to_capability(executor: Callable, capability_id: str) -> Callable:
    """Apply configured middleware to a capability executor."""
    middleware_configs = _resolve_middleware_config(capability_id)

    if not middleware_configs:
        logger.debug(f"No middleware to apply to {capability_id}")
        return executor

    try:
        # Mark the original executor as having middleware applied before wrapping
        executor._agentup_middleware_applied = True
        wrapped_executor = with_middleware(middleware_configs)(executor)
        middleware_names = [m.get("name") for m in middleware_configs]
        logger.debug(f"Applied middleware to capability '{capability_id}': {middleware_names}")
        return wrapped_executor
    except Exception as e:
        logger.error(f"Failed to apply middleware to capability '{capability_id}': {e}")
        return executor


def register_capability(capability_id: str):
    """Decorator to register a capability executor by ID with automatic middleware, state, and auth application."""

    def decorator(func: Callable[[Task], str]):
        # Apply authentication context first
        wrapped_func = _apply_auth_to_capability(func, capability_id)
        # Apply middleware automatically based on agent config
        wrapped_func = _apply_middleware_to_capability(wrapped_func, capability_id)
        # Apply state management automatically based on agent config
        wrapped_func = _apply_state_to_capability(wrapped_func, capability_id)
        _capabilities[capability_id] = wrapped_func
        logger.debug(f"Registered capability with auth, middleware and state: {capability_id}")
        return wrapped_func

    return decorator


def register_capability_function(capability_id: str, executor: Callable[[Task], str]) -> None:
    """Register a capability executor function directly (for plugins and dynamic registration)."""
    wrapped_executor = _apply_auth_to_capability(executor, capability_id)
    wrapped_executor = _apply_middleware_to_capability(wrapped_executor, capability_id)
    wrapped_executor = _apply_state_to_capability(wrapped_executor, capability_id)
    _capabilities[capability_id] = wrapped_executor
    logger.debug(f"Registered capability function with auth, middleware and state: {capability_id}")


def get_capability_executor(capability_id: str) -> Callable[[Task], str] | None:
    """Retrieve a registered capability executor by ID from unified registry."""
    # Check unified capabilities registry
    executor = _capabilities.get(capability_id)
    if executor:
        return executor

    # No executor found
    return None


async def execute_status(task: Task) -> str:
    """Get agent status and information."""
    return f"{_project_name} is operational and ready to process tasks. Task ID: {task.id}"


async def execute_capabilities(task: Task) -> str:
    """List agent capabilities and available plugins."""
    capabilities = list(_capabilities.keys())
    lines = "\n".join(f"- {capability}" for capability in capabilities)
    return f"{_project_name} capabilities:\n{lines}"


def get_all_capabilities() -> dict[str, Callable[[Task], str]]:
    """Return a copy of the capability executor registry."""
    return _capabilities.copy()


def list_capabilities() -> list[str]:
    """List all available capability IDs."""
    return list(_capabilities.keys())


def apply_global_middleware() -> None:
    """Apply middleware to all existing registered capability executors (for retroactive application)."""
    global _global_middleware_applied

    if _global_middleware_applied:
        logger.debug("Global middleware already applied, skipping")
        return

    middleware_configs = _load_middleware_config()
    if not middleware_configs:
        logger.debug("No global middleware to apply")
        _global_middleware_applied = True
        return

    logger.info(f"Applying global middleware to {_project_name} capability executors: {middleware_configs}")

    # Count executors that already have middleware applied
    executors_with_middleware = []
    executors_needing_middleware = []

    for capability_id, executor in _capabilities.items():
        has_middleware_flag = hasattr(executor, "_agentup_middleware_applied")
        logger.debug(f"Capability executor '{capability_id}' has middleware flag: {has_middleware_flag}")
        if has_middleware_flag:
            executors_with_middleware.append(capability_id)
        else:
            executors_needing_middleware.append(capability_id)
    # TODO: This is coming up with an empty list, why?
    # Executors with middleware: [] [agent.capabilities.executors]
    logger.debug(f"Executors with middleware: {executors_with_middleware}")

    # Only apply middleware to executors that don't already have it
    for capability_id in executors_needing_middleware:
        executor = _capabilities[capability_id]
        try:
            wrapped_executor = _apply_middleware_to_capability(executor, capability_id)
            _capabilities[capability_id] = wrapped_executor
            logger.debug(f"Applied global middleware to existing capability executor: {capability_id}")
        except Exception as e:
            logger.error(f"Failed to apply global middleware to {capability_id}: {e}")

    _global_middleware_applied = True

    if executors_needing_middleware:
        logger.info(
            f"Applied global middleware to {len(executors_needing_middleware)} capability executors: {executors_needing_middleware}"
        )
    else:
        logger.debug(
            "All capability executors already have middleware applied during registration - no additional work needed"
        )


def apply_global_state_management() -> None:
    """Apply state management to all existing registered capability executors (for retroactive application)."""
    global _global_state_applied

    if _global_state_applied:
        logger.debug("Global state already applied, skipping")
        return

    state_config = _load_state_config()
    if not state_config.get("enabled", False):
        logger.debug("State management disabled globally")
        _global_state_applied = True
        return

    # Re-wrap all existing capability executors with state management
    for capability_id, executor in list(_capabilities.items()):
        try:
            # Only apply if not already wrapped (simple check)
            if not hasattr(executor, "_agentup_state_applied"):
                wrapped_executor = _apply_state_to_capability(executor, capability_id)
                _capabilities[capability_id] = wrapped_executor
                logger.debug(f"Applied global state management to existing capability executor: {capability_id}")
            else:
                logger.debug(f"Capability executor '{capability_id}' already has state management applied, skipping")
        except Exception as e:
            logger.error(f"Failed to apply global state management to {capability_id}: {e}")

    _global_state_applied = True

    # Count executors that actually needed global state management
    executors_needing_state = [
        capability_id
        for capability_id, executor in _capabilities.items()
        if not hasattr(executor, "_agentup_state_applied")
    ]

    if executors_needing_state:
        logger.info(
            f"Applied global state management to {len(executors_needing_state)} capability executors: {executors_needing_state}"
        )
    else:
        logger.debug("All capability executors already have state management applied during registration")


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
        "total_capabilities": len(_capabilities),
        "middleware_names": [m.get("name") for m in middleware_configs],
    }


def get_state_info() -> dict[str, Any]:
    """Get information about current state configuration and application status."""
    state_config = _load_state_config()
    return {
        "config": state_config,
        "applied_globally": _global_state_applied,
        "total_capabilities": len(_capabilities),
        "enabled": state_config.get("enabled", False),
        "backend": state_config.get("backend", "memory"),
    }
