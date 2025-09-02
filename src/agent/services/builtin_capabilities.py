from collections.abc import Awaitable, Callable
from typing import Any

from a2a.types import Task

from .base import Service
from .config import ConfigurationManager


class CapabilityMetadata:
    def __init__(
        self,
        capability_id: str,
        plugin_name: str | None = None,
        required_scopes: list[str] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ):
        self.capability_id = capability_id
        self.plugin_name = plugin_name
        self.required_scopes = required_scopes or []
        self.description = description
        self.tags = tags or []
        self.middleware_applied = False
        self.state_applied = False
        self.auth_applied = False


class BuiltinCapabilityRegistry(Service):
    """Unified registry for all agent capabilities.

    This service manages all capability executors, providing:
    - Registration and discovery
    - Automatic middleware/state/auth wrapping
    - Execution with full stack applied
    - Metadata management
    """

    def __init__(self, config_manager: ConfigurationManager):
        super().__init__(config_manager)
        self._capabilities: dict[str, Callable[[Task], Awaitable[str]]] = {}
        self._metadata: dict[str, CapabilityMetadata] = {}
        self._core_capabilities = ["status", "capabilities", "echo"]

    async def initialize(self) -> None:
        # Register core capabilities
        await self._register_core_capabilities()

        # Load any existing capabilities from the old system
        # await self._migrate_existing_capabilities()

        self._initialized = True
        self.logger.info(f"Capability registry initialized with {len(self._capabilities)} capabilities")

    def register(
        self,
        capability_id: str,
        executor: Callable[[Task], Awaitable[str]],
        metadata: CapabilityMetadata | None = None,
    ) -> None:
        """Register a capability with optional metadata.

        Args:
            capability_id: Unique identifier for the capability
            executor: Async function that executes the capability
            metadata: Optional metadata for the capability
        """
        if capability_id in self._capabilities:
            self.logger.warning(f"Overwriting existing capability: {capability_id}")

        # Create default metadata if not provided
        if metadata is None:
            metadata = CapabilityMetadata(capability_id)

        # Apply wrappers based on configuration
        wrapped_executor = executor

        # Apply authentication wrapper if security is enabled
        security_enabled = getattr(self.config, "security", None) and getattr(self.config.security, "enabled", False)
        if security_enabled:
            wrapped_executor = self._wrap_with_auth(wrapped_executor, metadata)
            metadata.auth_applied = True

        # Apply middleware based on configuration
        wrapped_executor = self._wrap_with_middleware(wrapped_executor, capability_id)
        metadata.middleware_applied = True

        # Apply state management if enabled
        state_mgmt_enabled = getattr(self.config, "state_management", None) and getattr(
            self.config.state_management, "enabled", False
        )
        if state_mgmt_enabled:
            wrapped_executor = self._wrap_with_state(wrapped_executor, capability_id)
            metadata.state_applied = True

        self._capabilities[capability_id] = wrapped_executor
        self._metadata[capability_id] = metadata

        self.logger.debug(
            f"Registered BuiltIn Capability: {capability_id} "
            f"(auth={metadata.auth_applied}, "
            f"middleware={metadata.middleware_applied}, "
            f"state={metadata.state_applied})"
        )

    def unregister(self, capability_id: str) -> bool:
        """Unregister a capability.

        Args:
            capability_id: Capability to unregister

        Returns:
            True if capability was unregistered, False if not found
        """
        if capability_id in self._capabilities:
            del self._capabilities[capability_id]
            del self._metadata[capability_id]
            self.logger.debug(f"Unregistered Builtin Capability: {capability_id}")
            return True
        return False

    def get_executor(self, capability_id: str) -> Callable[[Task], Awaitable[str]] | None:
        """Get executor for a capability.

        Args:
            capability_id: Capability identifier

        Returns:
            Executor function or None if not found
        """
        return self._capabilities.get(capability_id)

    def get_metadata(self, capability_id: str) -> CapabilityMetadata | None:
        """Get metadata for a capability.

        Args:
            capability_id: Capability identifier

        Returns:
            Capability metadata or None if not found
        """
        return self._metadata.get(capability_id)

    def list_capabilities(self) -> list[str]:
        local_capabilities = list(self._capabilities.keys())
        return sorted(local_capabilities)

    def list_capabilities_with_metadata(self) -> dict[str, dict[str, Any]]:
        """List all capabilities with their metadata.

        Returns:
            Dictionary mapping capability IDs to metadata dictionaries
        """
        result = {}

        # Add capabilities from this registry with metadata
        for cap_id, metadata in self._metadata.items():
            result[cap_id] = {
                "plugin_name": metadata.plugin_name,
                "required_scopes": metadata.required_scopes,
                "description": metadata.description,
                "tags": metadata.tags,
                "is_core": cap_id in self._core_capabilities,
            }

        return result

    async def execute(self, capability_id: str, task: Task) -> str:
        """Execute a capability with the full stack applied.

        Args:
            capability_id: Capability to execute
            task: Task containing the request

        Returns:
            Execution result as string

        Raises:
            ValueError: If capability not found
            PermissionError: If authentication/authorization fails
            Exception: If execution fails
        """
        executor = self.get_executor(capability_id)
        if not executor:
            raise ValueError(f"Unknown capability: {capability_id}")

        self.logger.debug(f"Executing capability: {capability_id} (task_id={task.id})")

        try:
            result = await executor(task)
            self.logger.debug(f"Capability executed successfully: {capability_id}")
            return result
        except Exception as e:
            self.logger.error(f"Capability execution failed: {capability_id} - {e}")
            raise

    async def _register_core_capabilities(self) -> None:
        # Status capability
        async def status_executor(task: Task) -> str:
            agent_info = self.config.get_agent_info()
            return f"{agent_info['name']} is operational and ready to process tasks. Task ID: {task.id}"

        # Capabilities listing
        async def capabilities_executor(task: Task) -> str:
            capabilities = self.list_capabilities()
            agent_info = self.config.get_agent_info()
            lines = "\n".join(f"- {cap}" for cap in sorted(capabilities))
            return f"{agent_info['name']} capabilities:\n{lines}"

        # Echo capability
        async def echo_executor(task: Task) -> str:
            if hasattr(task, "metadata") and task.metadata and "message" in task.metadata:
                return f"Echo: {task.metadata['message']}"
            return "Echo: No message provided"

        # Register core capabilities
        self.register("status", status_executor, CapabilityMetadata("status", description="Get agent status"))
        self.register(
            "capabilities",
            capabilities_executor,
            CapabilityMetadata("capabilities", description="List agent capabilities"),
        )
        self.register("echo", echo_executor, CapabilityMetadata("echo", description="Echo test capability"))

    def _wrap_with_auth(self, executor: Callable, metadata: CapabilityMetadata) -> Callable:
        from functools import wraps

        @wraps(executor)
        async def auth_wrapped(task: Task) -> str:
            # Import here to avoid circular dependencies
            try:
                from agent.security.context import create_capability_context, get_current_auth

                # Get current authentication
                auth_result = get_current_auth()

                # Create capability context
                context = create_capability_context(task, auth_result)

                # Check required scopes
                for scope in metadata.required_scopes:
                    if not context.has_scope(scope):
                        self.logger.warning(
                            f"Access denied for capability {metadata.capability_id}: missing scope {scope}"
                        )
                        raise PermissionError(f"Insufficient permissions: missing scope '{scope}'")

                # Log access for audit
                self.logger.info(
                    f"Authorized access to {metadata.capability_id} for user {context.user_id or 'anonymous'}"
                )

            except ImportError:
                self.logger.debug("Security module not available, skipping auth")

            return await executor(task)

        return auth_wrapped

    def _wrap_with_middleware(self, executor: Callable, capability_id: str) -> Callable:
        try:
            # Get middleware configuration
            middleware_configs = self._get_middleware_config(capability_id)

            if not middleware_configs:
                return executor

            # Import middleware wrapper
            from agent.middleware import with_middleware

            wrapped = with_middleware(middleware_configs)(executor)
            middleware_names = [m.get("name") for m in middleware_configs]
            self.logger.debug(f"Applied middleware to {capability_id}: {middleware_names}")
            return wrapped

        except ImportError:
            self.logger.debug("Middleware module not available")
            return executor
        except Exception as e:
            self.logger.warning(f"Failed to apply middleware to {capability_id}: {e}")
            return executor

    def _wrap_with_state(self, executor: Callable, capability_id: str) -> Callable:
        try:
            # Get state configuration
            state_config = self._get_state_config(capability_id)

            if not state_config or not state_config.get("enabled", False):
                return executor

            # Import state wrapper
            from agent.state.decorators import with_state

            wrapped = with_state([state_config])(executor)
            backend = state_config.get("backend", "memory")
            self.logger.debug(f"Applied state management to {capability_id}: backend={backend}")
            return wrapped

        except ImportError:
            self.logger.debug("State module not available")
            return executor
        except Exception as e:
            self.logger.warning(f"Failed to apply state to {capability_id}: {e}")
            return executor

    def _get_middleware_config(self, capability_id: str) -> list[dict[str, Any]]:
        # Check for capability-specific override first
        plugin_config = self._get_plugin_config_for_capability(capability_id)
        if plugin_config and "plugin_override" in plugin_config:
            return plugin_config["plugin_override"]

        # Use global middleware configuration
        middleware_config = getattr(self.config, "middleware", None)
        if not middleware_config:
            middleware_config = {}

        # If it's already a list (old format), return as-is
        if isinstance(middleware_config, list):
            return middleware_config

        # Convert new dictionary format to list format expected by with_middleware
        middleware_list = []

        # Handle both Pydantic models and dictionaries
        if hasattr(middleware_config, "model_dump"):
            middleware_dict = middleware_config.model_dump()
        elif isinstance(middleware_config, dict):
            middleware_dict = middleware_config
        else:
            middleware_dict = {}

        # Check if middleware is enabled
        if not middleware_dict.get("enabled", True):
            return []

        # Convert rate_limiting config
        rate_limiting = middleware_dict.get("rate_limiting", {})
        if rate_limiting.get("enabled", False):
            middleware_list.append(
                {
                    "name": "rate_limited",
                    "params": {
                        "requests_per_minute": rate_limiting.get("requests_per_minute", 60),
                        "burst_limit": rate_limiting.get("burst_size", None),
                    },
                }
            )

        # Convert caching config
        caching = middleware_dict.get("caching", {})
        if caching.get("enabled", False):
            middleware_list.append(
                {
                    "name": "cached",
                    "params": {
                        "backend_type": caching.get("backend", "memory"),
                        "default_ttl": caching.get("default_ttl", 300),
                        "max_size": caching.get("max_size", 1000),
                    },
                }
            )

        # Convert retry config
        retry = middleware_dict.get("retry", {})
        if retry.get("enabled", False):
            middleware_list.append(
                {
                    "name": "retryable",
                    "params": {
                        "max_attempts": retry.get("max_attempts", 3),
                        "backoff_factor": retry.get("initial_delay", 1.0),
                        "max_delay": retry.get("max_delay", 60.0),
                    },
                }
            )

        return middleware_list

    def _get_state_config(self, capability_id: str) -> dict[str, Any]:
        # Check for capability-specific override first
        plugin_config = self._get_plugin_config_for_capability(capability_id)
        if plugin_config and "state_override" in plugin_config:
            return plugin_config["state_override"]

        # Use global state configuration
        state_config = getattr(self.config, "state_management", None)
        if state_config:
            return state_config.model_dump() if hasattr(state_config, "model_dump") else state_config
        return {}

    def _get_plugin_config_for_capability(self, capability_id: str) -> dict[str, Any] | None:
        # Try to find the plugin that provides this capability
        metadata = self._metadata.get(capability_id)
        if metadata and metadata.plugin_name:
            # Handle new dictionary-based plugin structure
            plugins = getattr(self.config, "plugins", None)
            if plugins and hasattr(plugins, "model_dump"):
                plugins_dict = plugins.model_dump()
            elif plugins and isinstance(plugins, dict):
                plugins_dict = plugins
            else:
                plugins_dict = {}

            if plugins_dict:
                # New structure: plugins is a dict with package names as keys
                for package_name, plugin_config in plugins_dict.items():
                    plugin_name = (
                        plugin_config.get("name")
                        if isinstance(plugin_config, dict)
                        else getattr(plugin_config, "name", None)
                    )
                    if package_name == metadata.plugin_name or plugin_name == metadata.plugin_name:
                        return plugin_config.model_dump() if hasattr(plugin_config, "model_dump") else plugin_config
            elif plugins and not isinstance(plugins, dict):
                # Legacy list structure - plugins is a list
                plugin_list = plugins.model_dump() if hasattr(plugins, "model_dump") else plugins
                for plugin in plugin_list:
                    plugin_name = plugin.get("name") if isinstance(plugin, dict) else getattr(plugin, "name", None)
                    if plugin_name == metadata.plugin_name:
                        return plugin

        # Fallback: check if capability_id matches a plugin name
        plugins = getattr(self.config, "plugins", None)
        if not plugins:
            return None

        plugins_dict = plugins.model_dump() if hasattr(plugins, "model_dump") else plugins
        if isinstance(plugins_dict, dict):
            # New structure
            for package_name, plugin_config in plugins_dict.items():
                plugin_name = (
                    plugin_config.get("name")
                    if isinstance(plugin_config, dict)
                    else getattr(plugin_config, "name", None)
                )
                if package_name == capability_id or plugin_name == capability_id:
                    return plugin_config.model_dump() if hasattr(plugin_config, "model_dump") else plugin_config
        else:
            # Legacy list structure
            for plugin in plugins_dict:
                plugin_name = plugin.get("name") if isinstance(plugin, dict) else getattr(plugin, "name", None)
                if plugin_name == capability_id:
                    return plugin

        return None
