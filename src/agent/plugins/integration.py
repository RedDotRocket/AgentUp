"""
Integration layer for the new decorator-based plugin system.

This module replaces the old Pluggy-based integration with direct
plugin management using the new PluginRegistry.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from agent.config.settings import Settings

import structlog
from a2a.types import Task

from agent.capabilities.manager import _capabilities
from agent.core.dispatcher import FunctionRegistry

from .adapter import PluginAdapter
from .manager import PluginRegistry, get_plugin_registry
from .models import CapabilityContext

logger = structlog.get_logger(__name__)


class PluginConfigWrapper:
    """Wrapper to make dict-based plugin config compatible with attribute access"""

    def __init__(self, data: dict):
        self.plugin_id = data["plugin_id"]
        self.package = data.get("package", "")
        self.enabled = data.get("enabled", True)
        self.config = data.get("config", {})
        self.capabilities = [CapabilityConfigWrapper(cap) for cap in data.get("capabilities", [])]


class CapabilityConfigWrapper:
    """Wrapper to make dict-based capability config compatible with attribute access"""

    def __init__(self, data: dict):
        self.capability_id = data["capability_id"]
        self.name = data.get("name", "")
        self.description = data.get("description", "")
        self.required_scopes = data.get("required_scopes", [])
        self.enabled = data.get("enabled", True)


def integrate_plugins_with_capabilities(
    config: Union["Settings", None] = None,
) -> dict[str, list[str]]:
    """
    Integrate the new plugin system with the existing capability registry.

    This function:
    1. Discovers and loads all plugins using the new PluginRegistry
    2. Registers configured plugin capabilities as capability executors
    3. Makes them available through the existing get_capability_executor() mechanism

    Args:
        config: Optional configuration object. If not provided,
                will be loaded when needed.

    Returns:
        Dict mapping capability_id to required_scopes for enabled capabilities.
    """
    logger.info("Starting plugin integration with capabilities system")

    # Get the plugin registry (replaces old plugin manager)
    plugin_registry = get_plugin_registry()
    logger.debug(f"Plugin registry obtained: {plugin_registry}")

    # If config is not provided, load it
    if config is None:
        from agent.config import Config

        config = Config

    registered_count = 0
    capabilities_to_register = {}  # capability_id -> scope_requirements

    # First, discover plugins
    logger.debug("Discovering plugins via entry points")
    plugin_registry.discover_plugins()
    logger.debug(
        f"Plugin registry now has {len(plugin_registry.plugins)} loaded plugins: {list(plugin_registry.plugins.keys())}"
    )

    # Get the set of plugins that are configured from settings
    _configured_plugin_ids = set()

    # Get configured capabilities from settings (regardless of enabled state)
    configured_capabilities = set()
    try:
        if hasattr(config, "plugins") and config.plugins:
            for plugin_config in config.plugins:
                for capability_config in plugin_config.capabilities:
                    configured_capabilities.add(capability_config.capability_id)
    except Exception as e:
        logger.debug(f"Could not load plugin configuration: {e}")
        configured_capabilities = set()

    # Process all discovered plugins - register those that are configured or have no lock file
    for plugin_id, plugin_instance in plugin_registry.plugins.items():
        logger.debug(f"Processing discovered plugin: {plugin_id}")

        # Process all discovered plugins (no lock file filtering)

        # Configure the plugin with default/empty config
        try:
            plugin_instance.configure({})
            logger.debug(f"Configured plugin '{plugin_id}' with empty config")
        except Exception as e:
            logger.warning(f"Failed to configure plugin '{plugin_id}': {e}")
            continue

        # Get the plugin's capabilities (defined via @capability decorators)
        try:
            plugin_capabilities = plugin_instance.get_capability_definitions()
            logger.debug(
                f"Plugin '{plugin_id}' provides {len(plugin_capabilities)} capabilities: {[cap.id for cap in plugin_capabilities]}"
            )
        except Exception as e:
            logger.warning(f"Failed to get capabilities for plugin '{plugin_id}': {e}")
            continue

        # Only register capabilities that are both provided by plugin AND configured in settings
        for capability_def in plugin_capabilities:
            capability_id = capability_def.id

            # Skip if capability is not configured in settings
            if configured_capabilities and capability_id not in configured_capabilities:
                logger.debug(f"Capability '{capability_id}' not configured in settings, skipping")
                continue

            # The @capability decorator defines the required scopes
            required_scopes = capability_def.required_scopes

            logger.debug(f"Registering capability '{capability_id}' with scopes: {required_scopes}")
            capabilities_to_register[capability_id] = required_scopes

    logger.debug(f"Total capabilities to register: {len(capabilities_to_register)}")

    # Configure services for all loaded plugins
    try:
        # Get available services (you may need to adjust this based on your service setup)
        services = _get_available_services()
        plugin_registry.configure_services(services)
        logger.debug(f"Configured services for {len(plugin_registry.plugins)} plugins")
    except Exception as e:
        logger.warning(f"Could not configure services for plugins: {e}")

    # Register capabilities with the existing capability system
    for capability_id, required_scopes in capabilities_to_register.items():
        # Skip if capability executor already exists (don't override existing executors)
        if capability_id in _capabilities:
            logger.debug(
                f"Capability '{capability_id}' already registered as executor, skipping plugin"
            )
            continue

        try:
            from agent.capabilities.manager import register_plugin_capability

            plugin_config = {"capability_id": capability_id, "required_scopes": required_scopes}

            # Register using the framework's scope enforcement pattern
            register_plugin_capability(plugin_config)
            logger.info(f"Capability Registered: '{capability_id}' with scopes: {required_scopes}")
            registered_count += 1

        except Exception as e:
            logger.error(f"Failed to register plugin capability '{capability_id}': {e}")
            import traceback

            logger.error(f"Registration error traceback: {traceback.format_exc()}")
            raise ValueError(
                f"Plugin capability '{capability_id}' requires proper scope enforcement configuration."
            ) from e

    # Store the registry globally for other components to access
    _plugin_registry_instance[0] = plugin_registry

    return capabilities_to_register


def _get_available_services() -> dict[str, Any]:
    """Get available services to configure for plugins"""
    services = {}

    try:
        # Add LLM service if available
        from agent.llm_providers import create_llm_provider

        services["llm_factory"] = create_llm_provider
    except ImportError:
        pass

    try:
        # Add multimodal helper if available
        from agent.utils.multimodal import MultiModalHelper

        services["multimodal"] = MultiModalHelper()
    except ImportError:
        pass

    # Add more services as needed
    return services


# Store the registry instance globally
_plugin_registry_instance: list[PluginRegistry | None] = [None]


def get_plugin_registry_instance() -> PluginRegistry | None:
    """Get the plugin registry instance"""
    return _plugin_registry_instance[0]


_plugin_adapter_instance = None


def get_plugin_adapter():
    """Get the plugin adapter instance."""
    global _plugin_adapter_instance
    if _plugin_adapter_instance is None:
        from agent.config import Config

        _plugin_adapter_instance = PluginAdapter(Config)
    return _plugin_adapter_instance


def create_plugin_capability_wrapper(capability_id: str) -> Callable[[Task], str]:
    """
    Create a wrapper function that executes a plugin capability.

    This converts between the plugin's CapabilityContext and the simple Task parameter
    used by the existing capability system.

    Args:
        capability_id: ID of the capability to wrap

    Returns:
        Async function that can be called with a Task
    """

    async def wrapped_executor(task: Task) -> str:
        """Execute plugin capability with Task converted to CapabilityContext"""
        registry = get_plugin_registry_instance()

        if not registry:
            return "Plugin system not initialized"

        # Convert Task to CapabilityContext
        context = CapabilityContext(
            task=task,
            config={},  # Will be populated by plugin configuration
            services=registry.plugins[registry.capability_to_plugin[capability_id]]._services,
            state={},  # Will be managed by the plugin
            metadata={"executor_type": "capability_wrapper"},
        )

        # Execute the capability
        result = await registry.execute_capability(capability_id, context)

        # Return content as string (expected by existing system)
        return result.content

    return wrapped_executor


def integrate_with_function_registry(
    registry: FunctionRegistry, enabled_capabilities: dict[str, list[str]] | None = None
) -> None:
    """
    Integrate plugins with the function registry for AI function calling.

    Args:
        registry: The function registry to integrate with
        enabled_capabilities: Dict mapping capability_id to required_scopes.
                            If None, will use all available AI functions.
    """
    plugin_registry = get_plugin_registry_instance()

    if not plugin_registry:
        logger.warning("Plugin registry not available for function integration")
        return

    # Determine which capabilities are enabled
    if enabled_capabilities is None:
        # Use all available capabilities that support AI functions
        enabled_capabilities = {}
        for capability_id, capability_meta in plugin_registry.capabilities.items():
            if capability_meta.ai_function:
                enabled_capabilities[capability_id] = capability_meta.scopes

    # Register AI functions for enabled capabilities
    ai_function_count = 0

    for capability_id in enabled_capabilities.keys():
        if capability_id not in plugin_registry.capabilities:
            continue

        capability_meta = plugin_registry.capabilities[capability_id]

        # Skip if capability doesn't support AI functions
        if not capability_meta.ai_function:
            continue

        # Get AI functions from the capability
        plugin_id = plugin_registry.capability_to_plugin[capability_id]
        plugin = plugin_registry.plugins[plugin_id]
        ai_functions = plugin.get_ai_functions(capability_id)

        for ai_func in ai_functions:
            # Create OpenAI-compatible function schema
            schema = {
                "name": ai_func.name,
                "description": ai_func.description,
                "parameters": ai_func.parameters,
            }

            # Create a wrapper that works with the function registry
            handler = _create_ai_function_handler(capability_id, ai_func, plugin_registry)

            # Register with the function registry
            registry.register_function(ai_func.name, handler, schema)
            ai_function_count += 1

            logger.debug(f"Registered AI function '{ai_func.name}' from plugin '{plugin_id}'")

    logger.info(f"Registered {ai_function_count} AI functions from plugins")


def _create_ai_function_handler(capability_id: str, ai_func, plugin_registry: PluginRegistry):
    """Create handler for AI function calls"""

    async def handler(task, context):
        """Handle AI function call"""
        # Extract parameters from the function call
        parameters = context.get("parameters", {}) if isinstance(context, dict) else {}

        # Create CapabilityContext for the plugin
        plugin_context = CapabilityContext(
            task=task,
            config={},
            services={},
            state={},
            metadata={
                "parameters": parameters,
                "capability_id": capability_id,
                "ai_function_call": True,
                "function_name": ai_func.name,
            },
        )

        # Execute the capability
        result = await plugin_registry.execute_capability(capability_id, plugin_context)

        return result

    return handler


def list_all_capabilities() -> list[str]:
    """
    List all available capabilities from both executors and plugins.
    """
    # Get capabilities from existing executors
    executor_capabilities = list(_capabilities.keys())

    # Get capabilities from plugins
    plugin_capabilities = []
    registry = get_plugin_registry_instance()
    if registry:
        plugin_capabilities = list(registry.capabilities.keys())

    # Combine and deduplicate
    all_capabilities = list(set(executor_capabilities + plugin_capabilities))
    return sorted(all_capabilities)


def get_capability_info(capability_id: str) -> dict[str, Any]:
    """
    Get information about a capability from either executors or plugins.
    """
    # Check plugin capabilities first
    registry = get_plugin_registry_instance()
    if registry:
        capability_def = registry.get_capability(capability_id)
        if capability_def:
            return {
                "capability_id": capability_def.id,
                "name": capability_def.name,
                "description": capability_def.description,
                "plugin_name": capability_def.plugin_name,
                "source": "plugin",
                "scopes": capability_def.required_scopes,
                "ai_function": CapabilityType.AI_FUNCTION in capability_def.capabilities,
                "tags": capability_def.tags,
            }

    # Fallback to basic executor info
    if capability_id in _capabilities:
        executor = _capabilities[capability_id]
        return {
            "capability_id": capability_id,
            "name": capability_id.replace("_", " ").title(),
            "description": executor.__doc__ or "No description available",
            "source": "executor",
        }

    return {}


def enable_plugin_system() -> None:
    """
    Enable the plugin system and integrate it with existing capability executors.

    This should be called during agent startup to replace the old Pluggy-based system.
    """
    try:
        # Integrate plugins with capabilities
        enabled_capabilities = integrate_plugins_with_capabilities()

        # Integrate plugins with the function registry for AI function calling
        try:
            from agent.core.dispatcher import get_function_registry

            # Get the global function registry
            function_registry = get_function_registry()

            # Integrate plugins with function registry
            integrate_with_function_registry(function_registry, enabled_capabilities)
            logger.info("Plugin system integrated with function registry for AI function calling")

        except Exception as e:
            logger.error(f"Failed to integrate plugins with function registry: {e}")
            # Continue without AI function integration

        # Make multimodal helper available to plugins (if needed)
        try:
            import sys

            from agent.utils.multimodal import MultiModalHelper

            if "agentup.multimodal" not in sys.modules:
                import types

                module = types.ModuleType("agentup.multimodal")
                module.MultiModalHelper = MultiModalHelper
                sys.modules["agentup.multimodal"] = module
                logger.debug("Multi-modal helper made available to plugins")
        except Exception as e:
            logger.warning(f"Could not make multi-modal helper available to plugins: {e}")

        logger.info("New plugin system initialized successfully")

    except Exception as e:
        logger.error(f"Failed to enable new plugin system: {e}", exc_info=True)
        # Don't crash the agent if plugins fail to load
        pass


# Re-export important classes for backward compatibility
from .models import CapabilityType  # noqa: E402
