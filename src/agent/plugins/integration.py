from collections.abc import Callable
from typing import Any

import structlog
from a2a.types import Task

from agent.handlers.handlers import _handlers, register_handler_function

from .adapter import PluginAdapter, get_plugin_manager

logger = structlog.get_logger(__name__)


def integrate_plugins_with_handlers() -> None:
    """
    Integrate the plugin system with the existing handler registry.

    This function:
    1. Discovers and loads all plugins
    2. Registers only configured plugin capabilities as handlers
    3. Makes them available through the existing get_handler() mechanism
    """

    # Get the plugin manager and adapter
    plugin_manager = get_plugin_manager()
    adapter = PluginAdapter(plugin_manager)

    # Get configured plugins from the agent config
    try:
        from agent.config import load_config

        config = load_config()
        configured_plugins = {plugin.get("plugin_id") for plugin in config.get("plugins", [])}
    except Exception as e:
        logger.warning(f"Could not load agent config, registering all plugins: {e}")
        configured_plugins = set()

    registered_count = 0

    # Build a mapping of plugin names to their capabilities
    plugin_to_capabilities = {}
    for capability_id in adapter.list_available_capabilities():
        capability_info = adapter.get_capability_info(capability_id)
        if capability_info and "plugin_name" in capability_info:
            plugin_name = capability_info["plugin_name"]
            if plugin_name not in plugin_to_capabilities:
                plugin_to_capabilities[plugin_name] = []
            plugin_to_capabilities[plugin_name].append(capability_id)

    logger.debug(
        f"Discovered {len(plugin_to_capabilities)} plugins with capabilities: {plugin_to_capabilities}"
    )

    # Determine which capabilities to register
    capabilities_to_register = set()

    if not configured_plugins:
        # If no config loaded, register all capabilities
        capabilities_to_register = set(adapter.list_available_capabilities())
    else:
        for plugin_id in configured_plugins:
            # Case 1: plugin_id matches a plugin name (e.g., "system_tools")
            if plugin_id in plugin_to_capabilities:
                logger.debug(f"Enabling all capabilities from plugin '{plugin_id}'")
                capabilities_to_register.update(plugin_to_capabilities[plugin_id])

            # Case 2: plugin_id matches a specific capability ID (e.g., "read_file")
            elif plugin_id in adapter.list_available_capabilities():
                logger.debug(f"Enabling specific capability '{plugin_id}'")
                capabilities_to_register.add(plugin_id)

    # Register each capability as a handler
    for capability_id in capabilities_to_register:
        # Skip if handler already exists (don't override existing handlers)
        if capability_id in _handlers:
            logger.debug(f"Capability '{capability_id}' already registered as handler, skipping plugin")
            continue

        # Get the plugin-based handler
        handler = adapter.get_handler_for_capability(capability_id)

        # Register it using the function registration (applies middleware automatically)
        register_handler_function(capability_id, handler)
        logger.info(f"Registered plugin capability '{capability_id}' as handler with middleware")
        registered_count += 1

    # Store the adapter globally for other uses
    _plugin_adapter[0] = adapter
    if registered_count == 0:
        logger.debug("No plugin capabilities registered in Agents config, integration complete")
    logger.info(
        f"Plugin integration complete. Added {registered_count} plugin capabilities (out of {len(adapter.list_available_capabilities())} discovered)"
    )


# Store the adapter instance
_plugin_adapter: list[PluginAdapter | None] = [None]


def get_plugin_adapter() -> PluginAdapter | None:
    """Get the plugin adapter instance."""
    return _plugin_adapter[0]


def create_plugin_handler_wrapper(plugin_handler: Callable) -> Callable[[Task], str]:
    """
    Wrap a plugin handler to be compatible with the existing handler signature.

    This converts between the plugin's CapabilityContext and the simple Task parameter.
    """

    async def wrapped_handler(task: Task) -> str:
        # The adapter already handles this conversion
        return await plugin_handler(task)

    return wrapped_handler


def list_all_capabilities() -> list[str]:
    """
    List all available capabilities from both handlers and plugins.
    """
    # Get capabilities from existing handlers
    handler_capabilities = list(_handlers.keys())

    # Get capabilities from plugins if integrated
    plugin_capabilities = []
    adapter = get_plugin_adapter()
    if adapter:
        plugin_capabilities = adapter.list_available_capabilities()

    # Combine and deduplicate
    all_capabilities = list(set(handler_capabilities + plugin_capabilities))
    return sorted(all_capabilities)


def get_capability_info(capability_id: str) -> dict[str, Any]:
    """
    Get information about a capability from either handlers or plugins.
    """
    # Check if it's a plugin capability
    adapter = get_plugin_adapter()
    if adapter:
        info = adapter.get_capability_info(capability_id)
        if info:
            return info

    # Fallback to basic handler info
    if capability_id in _handlers:
        handler = _handlers[capability_id]
        return {
            "capability_id": capability_id,
            "name": capability_id.replace("_", " ").title(),
            "description": handler.__doc__ or "No description available",
            "source": "handler",
        }

    return {}


def enable_plugin_system() -> None:
    """
    Enable the plugin system and integrate it with existing handlers.

    This should be called during agent startup.
    """
    try:
        integrate_plugins_with_handlers()

        # Make multi-modal helper available to plugins
        try:
            # Store in global space for plugins to access
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

        logger.info("Plugin system enabled successfully")
    except Exception as e:
        logger.error(f"Failed to enable plugin system: {e}", exc_info=True)
        # Don't crash the agent if plugins fail to load
        pass
