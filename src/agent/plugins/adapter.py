from typing import Any

import structlog
from a2a.types import Task

from agent.core.dispatcher import FunctionRegistry

from .manager import PluginManager, get_plugin_manager
from .models import CapabilityContext, CapabilityResult

logger = structlog.get_logger(__name__)


class PluginAdapter:
    """Adapts plugin system to work with existing AgentUp components."""

    def __init__(self, plugin_manager: PluginManager | None = None):
        """Initialize the adapter."""
        self.plugin_manager = plugin_manager or get_plugin_manager()
        self._function_registry: FunctionRegistry | None = None

    def integrate_with_function_registry(
        self, registry: FunctionRegistry, enabled_capabilities: dict[str, list[str]] | None = None
    ) -> None:
        """Integrate plugins with the function registry.

        Args:
            registry: The function registry to integrate with
            enabled_capabilities: Optional dict mapping capability_id to required_scopes.
                                If provided, only AI functions for these capabilities will be registered.
                                If None, will load config to determine enabled capabilities.
        """
        self._function_registry = registry

        # Determine which capabilities are enabled
        if enabled_capabilities is None:
            enabled_capabilities = self._load_enabled_capabilities()

        # Register AI functions only for enabled capabilities
        for capability_id, capability_info in self.plugin_manager.capabilities.items():
            # Skip if capability is not enabled in configuration
            if capability_id not in enabled_capabilities:
                logger.debug(f"Skipping AI function registration for disabled capability '{capability_id}'")
                continue

            # Skip if capability doesn't support AI functions
            if "ai_function" not in capability_info.capabilities:
                continue

            # Get AI functions from the capability
            ai_functions = self.plugin_manager.get_ai_functions(capability_id)

            for ai_func in ai_functions:
                # Create OpenAI-compatible function schema
                schema = {
                    "name": ai_func.name,
                    "description": ai_func.description,
                    "parameters": ai_func.parameters,
                }

                # Create a wrapper that converts Task to CapabilityContext
                handler = self._create_ai_function_handler(capability_id, ai_func)

                # Register with the function registry
                registry.register_function(ai_func.name, handler, schema)
                logger.info(f"Registered AI function '{ai_func.name}' from capability '{capability_id}'")

    def _load_enabled_capabilities(self) -> dict[str, list[str]]:
        """Load enabled capabilities from agent configuration.

        Returns:
            Dict mapping capability_id to required_scopes for enabled capabilities.
        """
        try:
            from agent.config import load_config

            config = load_config()
            configured_plugins = config.get("plugins", [])

            enabled_capabilities = {}

            for plugin_config in configured_plugins:
                # Check if this uses the new capability-based structure
                if "capabilities" in plugin_config:
                    for capability_config in plugin_config["capabilities"]:
                        capability_id = capability_config["capability_id"]
                        required_scopes = capability_config.get("required_scopes", [])
                        enabled = capability_config.get("enabled", True)

                        if enabled:
                            enabled_capabilities[capability_id] = required_scopes

            logger.debug(f"Loaded {len(enabled_capabilities)} enabled capabilities from config")
            return enabled_capabilities

        except Exception as e:
            logger.warning(f"Could not load enabled capabilities from config: {e}")
            return {}

    def _create_ai_function_handler(self, capability_id: str, ai_func):
        """Create a handler that adapts AI function calls to plugin execution."""

        async def handler(task: Task) -> str:
            # Create capability context from task
            context = self._create_capability_context(task)

            # If the AI function has its own handler, use it
            if ai_func.handler:
                try:
                    # Call the AI function's specific handler
                    result = await ai_func.handler(task, context)
                    if isinstance(result, CapabilityResult):
                        return result.content
                    return str(result)
                except Exception as e:
                    logger.error(f"Error calling AI function handler: {e}")
                    return f"Error: {str(e)}"
            else:
                # Fallback to capability's main execute method
                result = self.plugin_manager.execute_capability(capability_id, context)
                return result.content

        return handler

    def _create_capability_context(self, task: Task) -> CapabilityContext:
        """Create a skill context from an A2A task."""
        # Extract metadata and configuration
        metadata = getattr(task, "metadata", {}) or {}

        # Get services if available
        try:
            from agent.services import get_services

            services = get_services()
        except Exception:
            services = {}

        return CapabilityContext(
            task=task,
            config=metadata.get("config", {}),
            services=services,
            metadata=metadata,
        )

    def register_legacy_handlers(self, handlers: dict[str, Any]) -> None:
        """Register legacy handlers as plugins for backward compatibility."""
        # This would wrap existing handlers in a plugin interface
        # For now, we'll just log that we could do this
        logger.info(f"Could register {len(handlers)} legacy handlers as plugins")

    def get_capability_executor_for_capability(self, capability_id: str):
        """Get a capability executor function for a capability that's compatible with the system."""

        # Check if this is a built-in capability first
        builtin_executor = self._get_builtin_capability_executor(capability_id)
        if builtin_executor:
            return builtin_executor

        async def executor(task: Task) -> str:
            context = self._create_capability_context(task)
            result = self.plugin_manager.execute_capability(capability_id, context)
            return result.content

        return executor

    def _get_builtin_capability_executor(self, capability_id: str):
        """Get built-in capability executor if available."""
        try:
            from .builtin import get_builtin_registry

            builtin_registry = get_builtin_registry()

            # Find which built-in plugin provides this capability
            for plugin_id in builtin_registry.list_plugins():
                plugin = builtin_registry.get_plugin(plugin_id)
                if plugin and capability_id in plugin.get_capabilities():
                    handler = plugin.get_capability_handler(capability_id)
                    if handler:
                        # Return the handler directly - it's already an async function
                        return handler

            return None

        except ImportError:
            return None

    def find_capabilities_for_task(self, task: Task) -> list[tuple[str, float]]:
        """Find capabilities that can handle a task, compatible with old routing."""
        context = self._create_capability_context(task)
        return self.plugin_manager.find_capabilities_for_task(context)

    def list_available_capabilities(self) -> list[str]:
        """List all available capability IDs."""
        return list(self.plugin_manager.capabilities.keys())

    def get_capability_info(self, capability_id: str) -> dict[str, Any]:
        """Get capability information in a format compatible with the old system."""
        capability = self.plugin_manager.get_capability(capability_id)
        if not capability:
            return {}

        # Get the plugin name that provides this capability
        plugin_name = self.plugin_manager.capability_to_plugin.get(capability_id, "unknown")

        return {
            "capability_id": capability.id,
            "name": capability.name,
            "description": capability.description,
            "plugin_name": plugin_name,
            "input_mode": capability.input_mode,
            "output_mode": capability.output_mode,
            "tags": capability.tags,
            "priority": capability.priority,
            "system_prompt": capability.system_prompt,
        }

    def get_ai_functions(self, capability_id: str):
        """Get AI functions for a capability."""
        return self.plugin_manager.get_ai_functions(capability_id)


# TODO: I think this is dead code, but commenting for noew
# def integrate_plugins_with_registry(registry: FunctionRegistry) -> PluginAdapter:
#     """
#     Integrate the plugin system with an existing function registry.

#     This is the main entry point for adding plugin support to AgentUp.
#     """
#     adapter = PluginAdapter()
#     adapter.integrate_with_function_registry(registry)
#     return adapter


def replace_capability_loader() -> PluginAdapter:
    """
    Replace the current capability loading system with plugins.

    This returns an adapter that can be used as a drop-in replacement
    for the current capability loading mechanism.
    """
    return PluginAdapter()
