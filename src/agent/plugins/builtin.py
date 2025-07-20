"""
Built-in plugin system for AgentUp core capabilities.

Built-in plugins are capabilities that ship with AgentUp core and don't require
external packages. They can be configured like any other plugin with capabilities,
scopes, middleware, etc.

These are mostly used for testing, examples, and basic functionality that
TODO: Make sure these can be turned off in production if needed.
"""

from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BuiltinPlugin:
    """Base class for built-in plugins."""

    def __init__(self, plugin_id: str, name: str, description: str):
        self.plugin_id = plugin_id
        self.name = name
        self.description = description
        self.capabilities: dict[str, Callable] = {}

    def register_capability(self, capability_id: str, handler: Callable):
        """Register a capability handler for this plugin."""
        self.capabilities[capability_id] = handler
        logger.debug(f"Built-in plugin '{self.plugin_id}' registered capability '{capability_id}'")

    def get_capabilities(self) -> list[str]:
        """Get list of capability IDs this plugin provides."""
        return list(self.capabilities.keys())

    def get_capability_handler(self, capability_id: str) -> Callable | None:
        """Get handler for a specific capability."""
        return self.capabilities.get(capability_id)


class BuiltinPluginRegistry:
    """Registry for built-in plugins."""

    def __init__(self):
        self._plugins: dict[str, BuiltinPlugin] = {}

    def register_plugin(self, plugin: BuiltinPlugin):
        """Register a built-in plugin."""
        self._plugins[plugin.plugin_id] = plugin
        logger.info(f"Registered built-in plugin: {plugin.plugin_id} ({plugin.name})")

    def get_plugin(self, plugin_id: str) -> BuiltinPlugin | None:
        """Get a built-in plugin by ID."""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[str]:
        """List all registered built-in plugin IDs."""
        return list(self._plugins.keys())

    def get_all_capabilities(self) -> dict[str, str]:
        """Get mapping of capability_id -> plugin_id for all built-in capabilities."""
        capabilities = {}
        for plugin_id, plugin in self._plugins.items():
            for capability_id in plugin.get_capabilities():
                capabilities[capability_id] = plugin_id
        return capabilities

    def integrate_with_capability_system(self, plugin_configs: list[dict[str, Any]]):
        """
        Integrate built-in plugins with the capability system based on agent config.

        Args:
            plugin_configs: List of plugin configurations from agentup.yml
        """
        builtin_configs = [config for config in plugin_configs if config.get("plugin_id") in self._plugins]

        for plugin_config in builtin_configs:
            plugin_id = plugin_config["plugin_id"]
            plugin = self._plugins[plugin_id]

            # Get capabilities configuration for this plugin
            capabilities_config = plugin_config.get("capabilities", [])

            if not capabilities_config:
                # If no capabilities config provided, enable all with default scopes
                logger.warning(f"Built-in plugin '{plugin_id}' has no capabilities config, skipping")
                continue

            # Register each configured capability
            for capability_config in capabilities_config:
                capability_id = capability_config["capability_id"]
                required_scopes = capability_config.get("required_scopes", [])
                enabled = capability_config.get("enabled", True)

                if not enabled:
                    logger.debug(f"Capability '{capability_id}' is disabled for plugin '{plugin_id}'")
                    continue

                handler = plugin.get_capability_handler(capability_id)
                if not handler:
                    logger.error(f"Built-in plugin '{plugin_id}' has no handler for capability '{capability_id}'")
                    continue

                # Register directly with capability system for built-in plugins
                # Built-in plugins don't need the plugin adapter path
                from agent.capabilities.executors import register_capability_function

                # Create scope-enforced wrapper for built-in plugin handler
                def create_builtin_executor(cap_id: str, req_scopes: list[str], handler_func):
                    """Create a scope-enforced executor with proper variable binding."""

                    async def builtin_scope_enforced_executor(task, context=None):
                        """Scope-enforced wrapper for built-in plugin."""
                        import time

                        start_time = time.time()

                        # Create capability context if not provided
                        if context is None:
                            from agent.security.context import create_capability_context, get_current_auth

                            auth_result = get_current_auth()
                            context = create_capability_context(task, auth_result)

                        # Check scope access with comprehensive audit logging
                        access_granted = True
                        for scope in req_scopes:
                            if not context.has_scope(scope):
                                access_granted = False
                                break

                        # Comprehensive audit logging
                        from agent.security.context import log_capability_access

                        log_capability_access(
                            capability_id=cap_id,
                            user_id=context.user_id or "anonymous",
                            user_scopes=context.user_scopes,
                            required_scopes=req_scopes,
                            success=access_granted,
                        )

                        # Framework enforces what plugin declared
                        if not access_granted:
                            raise PermissionError("Insufficient permissions")

                        # Execute built-in handler
                        try:
                            result = await handler_func(task, context)

                            # Log execution time
                            execution_time = int((time.time() - start_time) * 1000)
                            log_capability_access(
                                capability_id=cap_id,
                                user_id=context.user_id or "anonymous",
                                user_scopes=context.user_scopes,
                                required_scopes=req_scopes,
                                success=True,
                                execution_time_ms=execution_time,
                            )

                            return result
                        except Exception as e:
                            logger.error(f"Built-in capability execution failed: {cap_id} - {e}")
                            raise

                    return builtin_scope_enforced_executor

                # Create and register the wrapped executor
                wrapped_executor = create_builtin_executor(capability_id, required_scopes, handler)
                register_capability_function(capability_id, wrapped_executor)

                logger.info(
                    f"Registered built-in capability '{capability_id}' from plugin '{plugin_id}' with scopes: {required_scopes}"
                )


# Global registry instance
_builtin_registry = BuiltinPluginRegistry()


def get_builtin_registry() -> BuiltinPluginRegistry:
    """Get the global built-in plugin registry."""
    return _builtin_registry


def register_builtin_plugin(plugin: BuiltinPlugin):
    """Register a built-in plugin with the global registry."""
    _builtin_registry.register_plugin(plugin)
