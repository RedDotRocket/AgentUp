from typing import Any

import structlog
from a2a.types import Task

from ..core.dispatcher import FunctionRegistry
from .manager import PluginManager, get_plugin_manager
from .models import SkillContext, SkillResult

logger = structlog.get_logger(__name__)


class PluginAdapter:
    """Adapts plugin system to work with existing AgentUp components."""

    def __init__(self, plugin_manager: PluginManager | None = None):
        """Initialize the adapter."""
        self.plugin_manager = plugin_manager or get_plugin_manager()
        self._function_registry: FunctionRegistry | None = None

    def integrate_with_function_registry(self, registry: FunctionRegistry) -> None:
        """Integrate plugins with the function registry."""
        self._function_registry = registry

        # Register all AI functions from plugins
        for skill_id, skill_info in self.plugin_manager.skills.items():
            # Skip if skill doesn't support AI functions
            if "ai_function" not in skill_info.capabilities:
                continue

            # Get AI functions from the skill
            ai_functions = self.plugin_manager.get_ai_functions(skill_id)

            for ai_func in ai_functions:
                # Create OpenAI-compatible function schema
                schema = {
                    "name": ai_func.name,
                    "description": ai_func.description,
                    "parameters": ai_func.parameters,
                }

                # Create a wrapper that converts Task to SkillContext
                handler = self._create_ai_function_handler(skill_id, ai_func)

                # Register with the function registry
                registry.register_function(ai_func.name, handler, schema)
                logger.info(f"Registered AI function '{ai_func.name}' from skill '{skill_id}'")

    def _create_ai_function_handler(self, skill_id: str, ai_func):
        """Create a handler that adapts AI function calls to plugin execution."""

        async def handler(task: Task) -> str:
            # Create skill context from task
            context = self._create_skill_context(task)

            # If the AI function has its own handler, use it
            if ai_func.handler:
                try:
                    # Call the AI function's specific handler
                    result = await ai_func.handler(task, context)
                    if isinstance(result, SkillResult):
                        return result.content
                    return str(result)
                except Exception as e:
                    logger.error(f"Error calling AI function handler: {e}")
                    return f"Error: {str(e)}"
            else:
                # Fallback to skill's main execute method
                result = self.plugin_manager.execute_skill(skill_id, context)
                return result.content

        return handler

    def _create_skill_context(self, task: Task) -> SkillContext:
        """Create a skill context from an A2A task."""
        # Extract metadata and configuration
        metadata = getattr(task, "metadata", {}) or {}

        # Get services if available
        try:
            from ..services import get_services

            services = get_services()
        except Exception:
            services = {}

        return SkillContext(
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

    def get_handler_for_skill(self, skill_id: str):
        """Get a handler function for a skill that's compatible with the old system."""

        async def handler(task: Task) -> str:
            context = self._create_skill_context(task)
            result = self.plugin_manager.execute_skill(skill_id, context)
            return result.content

        return handler

    def find_skills_for_task(self, task: Task) -> list[tuple[str, float]]:
        """Find skills that can handle a task, compatible with old routing."""
        context = self._create_skill_context(task)
        return self.plugin_manager.find_skills_for_task(context)

    def list_available_skills(self) -> list[str]:
        """List all available skill IDs."""
        return list(self.plugin_manager.skills.keys())

    def get_skill_info(self, skill_id: str) -> dict[str, Any]:
        """Get skill information in a format compatible with the old system."""
        skill = self.plugin_manager.get_skill(skill_id)
        if not skill:
            return {}

        return {
            "skill_id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "input_mode": skill.input_mode,
            "output_mode": skill.output_mode,
            "tags": skill.tags,
            "priority": skill.priority,
            "system_prompt": skill.system_prompt,
        }

    def get_ai_functions(self, skill_id: str):
        """Get AI functions for a skill."""
        return self.plugin_manager.get_ai_functions(skill_id)


def integrate_plugins_with_registry(registry: FunctionRegistry) -> PluginAdapter:
    """
    Integrate the plugin system with an existing function registry.

    This is the main entry point for adding plugin support to AgentUp.
    """
    adapter = PluginAdapter()
    adapter.integrate_with_function_registry(registry)
    return adapter


def replace_skill_loader() -> PluginAdapter:
    """
    Replace the current skill loading system with plugins.

    This returns an adapter that can be used as a drop-in replacement
    for the current skill loading mechanism.
    """
    return PluginAdapter()
