from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import structlog
from a2a.types import Task

from agent.config import get_settings
from agent.middleware import with_middleware

if TYPE_CHECKING:
    from agent.core.models.iteration import FunctionExecutionResult
    from agent.mcp_support.model import MCPCapabilityInfo

# Load agent config to pull in project name
_project_name = get_settings().project_name

logger = structlog.get_logger(__name__)

# Capability registry - unified for all capability executors
_capabilities: dict[str, Callable[[Task], str] | Callable[[Task], Awaitable[str]]] = {}

# MCP capability tracking - stores metadata about MCP tools registered as capabilities
_mcp_capabilities: dict[str, "MCPCapabilityInfo"] = {}

# Capability feature tracking - track which capabilities have middleware/state applied
_capabilities_with_middleware: set[str] = set()
_capabilities_with_state: set[str] = set()


def register_system_capabilities() -> None:
    """Register system-level capabilities that are always available."""

    @register_capability("mark_goal_complete")  # type: ignore
    async def mark_goal_complete_capability(task: Task) -> "FunctionExecutionResult":
        """Mark an iterative goal as completed with structured information.

        This is an internal system capability called when the agent has fully achieved the user's goal.
        The agent should provide a comprehensive summary of what was accomplished.

        Note: This is an internal-only capability and does not require authentication.
        """
        from agent.core.models.iteration import CompletionData, FunctionExecutionResult

        # This is an internal system capability
        logger.debug("Processing internal goal completion request")

        # Security constants for input validation
        ALLOWED_COMPLETION_FIELDS = {"summary", "result_content", "confidence", "tasks_completed", "remaining_issues"}
        MAX_SUMMARY_LENGTH = 2000
        MAX_RESULT_CONTENT_LENGTH = 8000  # Allow longer content for substantive results
        MAX_TASK_DESCRIPTION_LENGTH = 200
        MAX_TASKS_ARRAY_LENGTH = 50
        MIN_CONFIDENCE = 0.0
        MAX_CONFIDENCE = 1.0

        # Default completion data with secure defaults
        completion_dict = {
            "summary": "Goal completed successfully",
            "result_content": "",  # The actual substantive result/answer
            "confidence": 1.0,
            "tasks_completed": [],
            "remaining_issues": [],
        }

        # Secure extraction and validation of parameters from task metadata
        if hasattr(task, "metadata") and task.metadata:
            for key, value in task.metadata.items():
                # Only process allowed fields to prevent injection
                if key not in ALLOWED_COMPLETION_FIELDS or key not in completion_dict:
                    logger.warning(f"Ignoring invalid completion field: {key}")
                    continue

                try:
                    # Field-specific validation and sanitization
                    if key == "summary" and isinstance(value, str):
                        # Sanitize and truncate summary
                        sanitized_summary = value.strip()[:MAX_SUMMARY_LENGTH]
                        if sanitized_summary:
                            completion_dict[key] = sanitized_summary

                    elif key == "result_content" and isinstance(value, str):
                        # Sanitize and truncate result content (substantive answer)
                        sanitized_content = value.strip()[:MAX_RESULT_CONTENT_LENGTH]
                        if sanitized_content:
                            completion_dict[key] = sanitized_content

                    elif key == "confidence" and isinstance(value, int | float):
                        # Validate and clamp confidence to safe range
                        confidence = float(value)
                        if MIN_CONFIDENCE <= confidence <= MAX_CONFIDENCE:
                            completion_dict[key] = confidence
                        else:
                            logger.warning(f"Confidence value {confidence} out of range, using default")

                    elif key in ["tasks_completed", "remaining_issues"] and isinstance(value, list):
                        # Validate array length and sanitize content
                        if len(value) <= MAX_TASKS_ARRAY_LENGTH:
                            validated_tasks = []
                            for item in value:
                                if isinstance(item, str):
                                    sanitized_item = item.strip()[:MAX_TASK_DESCRIPTION_LENGTH]
                                    if sanitized_item:
                                        validated_tasks.append(sanitized_item)
                                else:
                                    logger.warning(f"Invalid task item type: {type(item)}")
                            completion_dict[key] = validated_tasks
                        else:
                            logger.warning(f"Tasks array too long ({len(value)}), using default")

                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to validate completion field '{key}': {e}")
                    # Keep default value for invalid fields

            logger.debug(f"Validated completion data fields: {list(completion_dict.keys())}")

        # Create structured Pydantic model from validated dictionary
        completion_data = CompletionData(**completion_dict)

        logger.info("Goal marked as complete by internal system - returning structured completion result")

        return FunctionExecutionResult(
            success=True,
            result=completion_data.result_content or completion_data.summary,
            completed=True,
            completion_data=completion_data.model_dump(),
        )

    logger.info("System capabilities registered: mark_goal_complete")


def register_plugin_capability(plugin_config: dict[str, Any]) -> None:
    """Register plugin capability with framework scope enforcement.
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
        import time

        start_time = time.time()

        # Create capability context if not provided
        if context is None:
            from agent.security.context import get_current_auth

            auth_result = get_current_auth()
            context = create_capability_context(task, auth_result)

        # Resolve effective scopes using the plugin resolver if available
        effective_scopes = required_scopes
        try:
            from agent.config import get_plugin_resolver

            resolver = get_plugin_resolver()
            if resolver:
                # Get the actual plugin name that provides this capability
                plugin_name = capability_id  # Default fallback
                try:
                    capability_info = plugin_adapter.get_capability_info(capability_id)
                    if capability_info and "plugin_name" in capability_info:
                        plugin_name = capability_info["plugin_name"]
                except (KeyError, AttributeError, TypeError, ImportError):
                    # Plugin adapter or capability info not available - use fallback
                    pass

                # Get effective scopes from the resolver
                effective_scopes = resolver.get_effective_scopes(plugin_name, capability_id, required_scopes)
                logger.debug(f"Using plugin resolver for effective scopes: {effective_scopes}")
            else:
                logger.debug(f"Plugin resolver not available, using decorator scopes: {required_scopes}")

        except Exception as e:
            logger.debug(f"Error getting effective scopes, using decorator scopes: {e}")
            effective_scopes = required_scopes

        # Check scope access with comprehensive audit logging
        access_granted = True
        for scope in effective_scopes:
            if not context.has_scope(scope):
                access_granted = False
                break

        # Comprehensive audit logging
        from agent.security.context import log_capability_access

        log_capability_access(
            capability_id=capability_id,
            user_id=context.user_id or "anonymous",
            user_scopes=context.user_scopes,
            required_scopes=effective_scopes,
            success=access_granted,
        )

        # Framework enforces what plugin declared
        if not access_granted:
            raise PermissionError("Insufficient permissions")

        # Only execute if scopes pass
        try:
            result = await base_executor(task)

            # Log execution time
            execution_time = int((time.time() - start_time) * 1000)
            log_capability_access(
                capability_id=capability_id,
                user_id=context.user_id or "anonymous",
                user_scopes=context.user_scopes,
                required_scopes=effective_scopes,
                success=True,
                execution_time_ms=execution_time,
            )

            return result
        except Exception as e:
            logger.error(f"Capability execution failed: {capability_id} - {e}")
            raise

    # Register the wrapped executor
    try:
        register_capability_function(capability_id, scope_enforced_executor)
        logger.debug(
            f"Registered plugin capability with scope enforcement: {capability_id} (scopes: {required_scopes})"
        )
    except Exception as e:
        logger.error(f"Failed to register plugin capability: {capability_id} - {e}")


async def register_mcp_tool_as_capability(
    tool_name: str,
    mcp_client,
    tool_scopes: list[str],
    server_name: str = "unknown",
    tool_data: dict | None = None,
) -> None:
    """Register MCP tool as capability with scope enforcement.

    It registers external MCP tools as capabilities with the same scope enforcement
    as local plugin capabilities.

    Args:
        tool_name: Name of the MCP tool
        mcp_client: MCP client instance to call the tool
        tool_scopes: List of required scopes for this tool
    """
    from agent.security.context import create_capability_context, get_current_auth

    async def mcp_tool_executor(task: Task, context=None) -> str:
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

    # Track this as an MCP capability with Pydantic model
    from agent.mcp_support.model import MCPCapabilityInfo

    # Use tool data passed directly from registration (rich MCP tool info)
    if tool_data:
        original_name = tool_data["name"]  # Clean original name from MCP server
        description = tool_data.get("description", "")  # Rich description from MCP server
        input_schema = tool_data.get("inputSchema", {})  # Parameter schema from MCP server
    else:
        original_name = tool_name
        description = ""
        input_schema = {}

    # Create capability info with rich MCP tool data
    _mcp_capabilities[tool_name] = MCPCapabilityInfo(
        name=tool_name,
        original_name=original_name,
        description=description,
        server_name=server_name,
        scopes=tool_scopes,
        parameters=input_schema,  # Use inputSchema from MCP
        input_schema=input_schema,
        output_schema={},  # MCP doesn't provide output schema
    )

    logger.debug(f"Registered MCP tool as capability: {tool_name} (scopes: {tool_scopes})")


# Middleware configuration cache
_middleware_config: list[dict[str, Any]] | None = None
_global_middleware_applied = False

# State management configuration cache
_state_config: dict[str, Any] | None = None
_global_state_applied = False


def _load_middleware_config() -> list[dict[str, Any]]:
    global _middleware_config
    if _middleware_config is not None:
        return _middleware_config

    try:
        middleware_config = get_settings().middleware.model_dump()
        # If it's already a list (old format), use as-is
        if isinstance(middleware_config, list):
            _middleware_config = middleware_config
        else:
            # Convert new dictionary format to list format expected by with_middleware
            _middleware_config = []

            if isinstance(middleware_config, dict):
                # Check if middleware is enabled
                if not middleware_config.get("enabled", True):
                    _middleware_config = []
                else:
                    # Convert rate_limiting config
                    if middleware_config.get("rate_limiting", {}).get("enabled", False):
                        rate_config = middleware_config["rate_limiting"]
                        _middleware_config.append(
                            {
                                "name": "rate_limited",
                                "params": {
                                    "requests_per_minute": rate_config.get("requests_per_minute", 60),
                                    "burst_limit": rate_config.get("burst_size", None),
                                },
                            }
                        )

                    # Convert caching config - use shared global cache config
                    if middleware_config.get("caching", {}).get("enabled", False):
                        # Import and use the global cache configuration
                        try:
                            from agent.middleware.implementation import get_global_cache_config

                            shared_cache_config = get_global_cache_config()

                            _middleware_config.append(
                                {
                                    "name": "cached",
                                    "params": {
                                        "backend_type": shared_cache_config.backend_type,
                                        "default_ttl": shared_cache_config.default_ttl,
                                        "max_size": shared_cache_config.max_size,
                                        "key_prefix": shared_cache_config.key_prefix,
                                    },
                                }
                            )
                        except Exception as e:
                            logger.warning(f"Could not use global cache config, falling back to local config: {e}")
                            # Fallback to original behavior
                            cache_config = middleware_config["caching"]
                            _middleware_config.append(
                                {
                                    "name": "cached",
                                    "params": {
                                        "backend_type": cache_config.get("backend", "memory"),
                                        "default_ttl": cache_config.get("default_ttl", 300),
                                        "max_size": cache_config.get("max_size", 1000),
                                    },
                                }
                            )

                    # Convert retry config
                    if middleware_config.get("retry", {}).get("enabled", False):
                        retry_config = middleware_config["retry"]
                        _middleware_config.append(
                            {
                                "name": "retryable",
                                "params": {
                                    "max_attempts": retry_config.get("max_attempts", 3),
                                    "backoff_factor": retry_config.get("initial_delay", 1.0),
                                    "max_delay": retry_config.get("max_delay", 60.0),
                                },
                            }
                        )
        if not _middleware_config:
            logger.debug("No middleware configured for capability")
        else:
            # Log the loaded middleware configuration
            logger.debug(f"Loaded middleware config: {_middleware_config}")
        return _middleware_config
    except Exception as e:
        logger.warning(f"Could not load middleware config: {e}")
        _middleware_config = []
        return _middleware_config


def _load_state_config() -> dict[str, Any]:
    global _state_config
    if _state_config is not None:
        return _state_config

    try:
        _state_config = get_settings().state_management
        if isinstance(_state_config, dict):
            logger.debug(f"Loaded state config: {_state_config}")
            return _state_config
        else:
            _state_config = {}
            return _state_config
    except Exception as e:
        logger.warning(f"Could not load state config: {e}")
        _state_config = {}
        return _state_config


def _get_plugin_config(plugin_name: str) -> dict | None:
    try:
        settings = get_settings()
        # Handle new dictionary-based plugin structure
        if hasattr(settings, "plugins") and isinstance(settings.plugins, dict):
            # New structure: plugins is a dict with package names as keys
            plugin_config = settings.plugins.get(plugin_name)
            if plugin_config:
                return plugin_config.model_dump() if hasattr(plugin_config, "model_dump") else dict(plugin_config)
        else:
            # Fallback: old list structure with name or package fields
            for plugin in getattr(get_settings(), "plugins", []):
                # Try to match by name or package field
                plugin_dict = plugin.model_dump() if hasattr(plugin, "model_dump") else dict(plugin)
                if plugin_dict.get("name") == plugin_name or plugin_dict.get("package") == plugin_name:
                    return plugin_dict
        return None
    except Exception as e:
        logger.debug(f"Could not load plugin config for '{plugin_name}': {e}")
        return None


def _resolve_state_config(plugin_name: str) -> dict:
    global_state_config = _load_state_config()
    plugin_config = _get_plugin_config(plugin_name)

    if plugin_config and "state_override" in plugin_config:
        logger.info(f"Using plugin-specific state override for '{plugin_name}'")
        return plugin_config["state_override"]

    return global_state_config


def _apply_auth_to_capability(executor: Callable, capability_id: str) -> Callable:
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
    state_config = _resolve_state_config(capability_id)

    if not state_config.get("enabled", False):
        logger.debug(f"State management disabled for {capability_id}")
        return executor

    try:
        from agent.state.decorators import with_state

        # Mark the capability as having state applied in global registry
        _capabilities_with_state.add(capability_id)
        wrapped_executor = with_state([state_config])(executor)
        backend = state_config.get("backend", "memory")
        logger.debug(f"Applied state management to capability '{capability_id}': backend={backend}")
        return wrapped_executor
    except Exception as e:
        logger.error(f"Failed to apply state management to capability '{capability_id}': {e}")
        return executor


def _resolve_middleware_config(capability_id: str) -> list[dict[str, Any]]:
    # Try to use the new plugin resolver if available
    try:
        from agent.config import get_plugin_resolver

        resolver = get_plugin_resolver()
        if resolver:
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

            # Use the new resolver to get effective middleware
            effective_middleware = resolver.get_effective_middleware(plugin_name, capability_id)
            logger.debug(f"Using plugin resolver for middleware config: {effective_middleware}")
            return effective_middleware

    except Exception as e:
        logger.debug(f"Plugin resolver not available, falling back to legacy config: {e}")

    # Fallback to legacy configuration loading
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
    if plugin_config and "plugin_override" in plugin_config:
        logger.info(f"Using plugin-specific middleware override for '{capability_id}'")
        return plugin_config["plugin_override"]
    elif plugin_config and "middleware_override" in plugin_config:
        # Legacy fallback for old field name
        logger.info(f"Using legacy middleware override for '{capability_id}'")
        return plugin_config["middleware_override"]

    # Use global middleware configuration
    return global_middleware_configs


def _apply_middleware_to_capability(executor: Callable, capability_id: str) -> Callable:
    middleware_configs = _resolve_middleware_config(capability_id)

    try:
        # Mark the capability as having middleware applied in global registry
        _capabilities_with_middleware.add(capability_id)
        wrapped_executor = with_middleware(middleware_configs)(executor)
        logger.debug(f"Applied middleware to plugin '{capability_id}': {middleware_configs}")
        return wrapped_executor
    except Exception as e:
        logger.error(f"Failed to apply middleware to capability '{capability_id}': {e}")
        return executor


def register_capability(capability_id: str):
    def decorator(func: Callable[[Task], str] | Callable[[Task], Callable[[], str]]):
        features_applied = []

        # Apply authentication context first
        wrapped_func = _apply_auth_to_capability(func, capability_id)
        features_applied.append("auth")

        # Apply middleware automatically based on agent config
        middleware_configs = _resolve_middleware_config(capability_id)
        if middleware_configs:
            wrapped_func = _apply_middleware_to_capability(wrapped_func, capability_id)
            features_applied.append("middleware")

        # Apply state management automatically based on agent config
        state_config = _resolve_state_config(capability_id)
        if state_config.get("enabled", False):
            wrapped_func = _apply_state_to_capability(wrapped_func, capability_id)
            features_applied.append("state")

        _capabilities[capability_id] = wrapped_func
        logger.debug(f"Registered capability '{capability_id}' with: {', '.join(features_applied)}")
        return wrapped_func

    return decorator


def register_capability_function(
    capability_id: str, executor: Callable[[Task], str] | Callable[[Task], Awaitable[str]]
) -> None:
    features_applied = []

    # Apply authentication context first
    wrapped_executor = _apply_auth_to_capability(executor, capability_id)
    features_applied.append("auth")

    # Apply middleware automatically based on agent config
    middleware_configs = _resolve_middleware_config(capability_id)
    if middleware_configs:
        wrapped_executor = _apply_middleware_to_capability(wrapped_executor, capability_id)
        features_applied.append("middleware")

    # Apply state management automatically based on agent config
    state_config = _resolve_state_config(capability_id)
    if state_config.get("enabled", False):
        wrapped_executor = _apply_state_to_capability(wrapped_executor, capability_id)
        features_applied.append("state")

    _capabilities[capability_id] = wrapped_executor
    logger.debug(f"Registered capability '{capability_id}' with: {', '.join(features_applied)}")


def get_capability_executor(capability_id: str) -> Callable[[Task], str] | Callable[[Task], Awaitable[str]] | None:
    # Check unified capabilities registry
    logger.debug(f"Available capabilities: {list(_capabilities.keys())}")
    executor = _capabilities.get(capability_id)
    if executor is None:
        logger.warning(f"Capability '{capability_id}' not found in unified capabilities registry")
        return None
    logger.debug(f"Retrieved capability executor for '{capability_id}': {executor}")
    return executor


async def execute_status(task: Task) -> str:
    return f"{_project_name} is operational and ready to process tasks. Task ID: {task.id}"


async def execute_capabilities(task: Task) -> str:
    capabilities = list(_capabilities.keys())
    lines = "\n".join(f"- {capability}" for capability in capabilities)
    return f"{_project_name} capabilities:\n{lines}"


def get_all_capabilities() -> dict[str, Callable[[Task], str] | Callable[[Task], Awaitable[str]]]:
    return _capabilities.copy()


def list_capabilities() -> list[str]:
    return list(_capabilities.keys())


def get_mcp_capabilities() -> dict[str, "MCPCapabilityInfo"]:
    """Get all MCP capabilities registered as agent capabilities.

    Returns:
        Dictionary mapping capability name to MCPCapabilityInfo model
    """
    return _mcp_capabilities.copy()


def apply_global_middleware() -> None:
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

    # Count executors that already have middleware applied using global registry
    executors_with_middleware = []
    executors_needing_middleware = []

    for capability_id, _executor in _capabilities.items():
        has_middleware_flag = capability_id in _capabilities_with_middleware
        logger.debug(f"Capability executor '{capability_id}' has middleware flag: {has_middleware_flag}")
        if has_middleware_flag:
            executors_with_middleware.append(capability_id)
        else:
            executors_needing_middleware.append(capability_id)

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
            # Only apply if not already wrapped using global registry
            if capability_id not in _capabilities_with_state:
                wrapped_executor = _apply_state_to_capability(executor, capability_id)
                _capabilities[capability_id] = wrapped_executor
                logger.debug(f"Applied global state management to existing capability executor: {capability_id}")
            else:
                logger.debug(f"Capability executor '{capability_id}' already has state management applied, skipping")
        except Exception as e:
            logger.error(f"Failed to apply global state management to {capability_id}: {e}")

    _global_state_applied = True

    # Count executors that actually needed global state management using global registry
    executors_needing_state = [
        capability_id for capability_id in _capabilities.keys() if capability_id not in _capabilities_with_state
    ]

    if executors_needing_state:
        logger.info(
            f"Applied global state management to {len(executors_needing_state)} capability executors: {executors_needing_state}"
        )
    else:
        logger.debug("All capability executors already have state management applied during registration")


def reset_middleware_cache() -> None:
    global _middleware_config, _global_middleware_applied
    _middleware_config = None
    _global_middleware_applied = False
    logger.debug("Reset middleware configuration cache")


def reset_state_cache() -> None:
    global _state_config, _global_state_applied
    _state_config = None
    _global_state_applied = False
    logger.debug("Reset state configuration cache")


def get_middleware_info() -> dict[str, Any]:
    middleware_configs = _load_middleware_config()
    return {
        "config": middleware_configs,
        "applied_globally": _global_middleware_applied,
        "total_capabilities": len(_capabilities),
        "middleware_names": [m.get("name") for m in middleware_configs],
    }


def get_state_info() -> dict[str, Any]:
    state_config = _load_state_config()
    return {
        "config": state_config,
        "applied_globally": _global_state_applied,
        "total_capabilities": len(_capabilities),
        "enabled": state_config.get("enabled", False),
        "backend": state_config.get("backend", "memory"),
    }


# Auto-register system capabilities when this module is imported
# This ensures they're available when the function registry is created
try:
    register_system_capabilities()
except Exception as e:
    logger.debug(f"Failed to auto-register system capabilities during import: {e}")
