from collections.abc import Callable
from typing import Any

import structlog
from a2a.types import Task

from ..handlers.handlers import _handlers, register_handler_function
from .adapter import PluginAdapter, get_plugin_manager

logger = structlog.get_logger(__name__)


def integrate_plugins_with_handlers() -> None:
    """
    Integrate the plugin system with the existing handler registry.

    This function:
    1. Discovers and loads all plugins
    2. Registers only configured plugin skills as handlers
    3. Makes them available through the existing get_handler() mechanism
    """
    logger.info("Integrating plugin system with existing handlers...")

    # Get the plugin manager and adapter
    plugin_manager = get_plugin_manager()
    adapter = PluginAdapter(plugin_manager)

    # Get configured skills from the agent config
    try:
        from ..config import load_config

        config = load_config()
        configured_skills = {skill.get("skill_id") for skill in config.get("skills", [])}
    except Exception as e:
        logger.warning(f"Could not load agent config, registering all plugins: {e}")
        configured_skills = set(adapter.list_available_skills())

    registered_count = 0

    # Register each configured plugin skill as a handler
    for skill_id in adapter.list_available_skills():
        # Only register skills that are configured in agent_config.yaml
        if skill_id not in configured_skills:
            logger.debug(f"Skill '{skill_id}' not in agent config, skipping registration")
            continue

        # Skip if handler already exists (don't override existing handlers)
        if skill_id in _handlers:
            logger.debug(f"Skill '{skill_id}' already registered as handler, skipping plugin")
            continue

        # Get the plugin-based handler
        handler = adapter.get_handler_for_skill(skill_id)

        # Register it using the function registration (applies middleware automatically)
        register_handler_function(skill_id, handler)
        logger.info(f"Registered plugin skill '{skill_id}' as handler with middleware")
        registered_count += 1

    # Store the adapter globally for other uses
    _plugin_adapter[0] = adapter

    logger.info(
        f"Plugin integration complete. Added {registered_count} plugin skills (out of {len(adapter.list_available_skills())} discovered)"
    )


# Store the adapter instance
_plugin_adapter: list[PluginAdapter | None] = [None]


def get_plugin_adapter() -> PluginAdapter | None:
    """Get the plugin adapter instance."""
    return _plugin_adapter[0]


def create_plugin_handler_wrapper(plugin_handler: Callable) -> Callable[[Task], str]:
    """
    Wrap a plugin handler to be compatible with the existing handler signature.

    This converts between the plugin's SkillContext and the simple Task parameter.
    """

    async def wrapped_handler(task: Task) -> str:
        # The adapter already handles this conversion
        return await plugin_handler(task)

    return wrapped_handler


def list_all_skills() -> list[str]:
    """
    List all available skills from both handlers and plugins.
    """
    # Get skills from existing handlers
    handler_skills = list(_handlers.keys())

    # Get skills from plugins if integrated
    plugin_skills = []
    adapter = get_plugin_adapter()
    if adapter:
        plugin_skills = adapter.list_available_skills()

    # Combine and deduplicate
    all_skills = list(set(handler_skills + plugin_skills))
    return sorted(all_skills)


def get_skill_info(skill_id: str) -> dict[str, Any]:
    """
    Get information about a skill from either handlers or plugins.
    """
    # Check if it's a plugin skill
    adapter = get_plugin_adapter()
    if adapter:
        info = adapter.get_skill_info(skill_id)
        if info:
            return info

    # Fallback to basic handler info
    if skill_id in _handlers:
        handler = _handlers[skill_id]
        return {
            "skill_id": skill_id,
            "name": skill_id.replace("_", " ").title(),
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

            from ..utils.multimodal import MultiModalHelper

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
