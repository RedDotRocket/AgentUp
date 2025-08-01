"""
Base plugin class for the decorator-based plugin system.

This module provides the Plugin base class that automatically discovers
@capability decorated methods and handles plugin lifecycle.
"""

import inspect
from typing import Any

import structlog

from ..config.logging import get_plugin_logger
from .decorators import CapabilityMetadata, get_capability_metadata, validate_capability_metadata
from .models import (
    AIFunction,
    CapabilityContext,
    CapabilityDefinition,
    CapabilityResult,
)

logger = structlog.get_logger(__name__)


class Plugin:
    """
    Base class for all AgentUp plugins.

    This class automatically discovers @capability decorated methods
    and handles all plugin registration and lifecycle management.

    Example:
        class WeatherPlugin(Plugin):
            @capability("weather", scopes=["web:search"])
            async def get_weather(self, context: CapabilityContext) -> str:
                return "Sunny, 72°F"
    """

    def __init__(self):
        self._capabilities: dict[str, CapabilityMetadata] = {}
        self._services: dict[str, Any] = {}
        self._config: dict[str, Any] = {}
        self._state: dict[str, Any] = {}

        # Create plugin-aware logger
        self.logger = get_plugin_logger(
            plugin_id=self.plugin_id,
            plugin_name=getattr(self, "name", None) or self.__class__.__name__,
            plugin_version=getattr(self, "version", None),
        )

        # Auto-discover capabilities
        self._discover_capabilities()

    @property
    def plugin_id(self) -> str:
        """Get plugin ID from class name"""
        return self.__class__.__name__.lower().replace("plugin", "")

    def _discover_capabilities(self):
        """Automatically discover all @capability decorated methods"""
        for _name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            capabilities = get_capability_metadata(method)

            for capability_meta in capabilities:
                # Validate capability metadata
                errors = validate_capability_metadata(capability_meta)
                if errors:
                    self.logger.error("Invalid capability", capability_id=capability_meta.id, errors=errors)
                    continue

                # Bind the handler to this instance
                capability_meta.handler = method
                self._capabilities[capability_meta.id] = capability_meta

                self.logger.debug("Discovered capability", capability_id=capability_meta.id)

    # === Core Plugin Interface ===

    async def execute_capability(self, capability_id: str, context: CapabilityContext) -> CapabilityResult:
        """Execute a specific capability by ID"""
        if capability_id not in self._capabilities:
            return CapabilityResult(
                content=f"Capability '{capability_id}' not found", success=False, error="Capability not found"
            )

        capability = self._capabilities[capability_id]
        try:
            self.logger.debug("Executing capability", capability_id=capability_id)

            # Call the decorated method
            result = await capability.handler(context)

            # Handle different return types
            if isinstance(result, CapabilityResult):
                return result
            elif isinstance(result, str):
                return CapabilityResult(content=result, success=True)
            elif isinstance(result, dict):
                return CapabilityResult(
                    content=str(result), success=True, metadata=result if isinstance(result, dict) else {}
                )
            else:
                return CapabilityResult(content=str(result), success=True)

        except Exception as e:
            self.logger.error("Error executing capability", capability_id=capability_id, error=str(e), exc_info=True)
            return CapabilityResult(content=f"Error executing capability: {str(e)}", success=False, error=str(e))

    def can_handle_task(self, capability_id: str, context: CapabilityContext) -> bool | float:
        """Check if this plugin can handle a task"""
        # Base implementation - subclasses should override
        return capability_id in self._capabilities

    def get_capability_definitions(self) -> list[CapabilityDefinition]:
        """Get all capability definitions for this plugin"""
        definitions = []

        for cap_meta in self._capabilities.values():
            definition = CapabilityDefinition(
                id=cap_meta.id,
                name=cap_meta.name,
                version="1.0.0",  # Default version
                description=cap_meta.description,
                capabilities=cap_meta.to_capability_types(),
                required_scopes=cap_meta.scopes,
                tags=cap_meta.tags,
                config_schema=cap_meta.config_schema,
                plugin_name=self.plugin_id,
            )
            definitions.append(definition)

        return definitions

    def get_ai_functions(self, capability_id: str | None = None) -> list[AIFunction]:
        """Get AI functions from this plugin"""
        ai_functions = []

        capabilities_to_check = []
        if capability_id:
            if capability_id in self._capabilities:
                capabilities_to_check = [self._capabilities[capability_id]]
        else:
            capabilities_to_check = list(self._capabilities.values())

        for cap_meta in capabilities_to_check:
            if cap_meta.ai_function and cap_meta.ai_parameters:
                ai_func = AIFunction(
                    name=cap_meta.id,
                    description=cap_meta.description,
                    parameters=cap_meta.ai_parameters,
                    handler=cap_meta.handler,
                )
                ai_functions.append(ai_func)

        return ai_functions

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with settings"""
        self._config.update(config)

    def configure_services(self, services: dict[str, Any]) -> None:
        """Configure services available to the plugin"""
        self._services.update(services)

    async def get_health_status(self) -> dict[str, Any]:
        """Get plugin health status"""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": list(self._capabilities.keys()),
            "has_llm": "llm" in self._services or "llm_factory" in self._services,
            "configured": bool(self._config),
        }

    # === Optional Lifecycle Hooks ===
    # These methods can be overridden by plugins for custom behavior

    def on_install(self) -> None:
        """Called when plugin is installed (optional override)"""
        pass

    def on_uninstall(self) -> None:
        """Called when plugin is uninstalled (optional override)"""
        pass

    def on_enable(self) -> None:
        """Called when plugin is enabled (optional override)"""
        pass

    def on_disable(self) -> None:
        """Called when plugin is disabled (optional override)"""
        pass


class SimplePlugin(Plugin):
    """
    Convenience base class for simple text-based plugins.

    Provides helper methods for common plugin patterns.
    """

    def _extract_task_content(self, context: CapabilityContext) -> str:
        """Extract text content from task context"""
        task = context.task
        if hasattr(task, "content"):
            return task.content
        elif hasattr(task, "messages") and task.messages:
            return task.messages[0].content
        elif hasattr(task, "message"):
            return task.message
        else:
            return str(task)


class AIFunctionPlugin(Plugin):
    """
    Convenience base class for AI function plugins.

    Provides helper methods for AI function calling patterns.
    """

    def _extract_ai_parameters(self, context: CapabilityContext) -> dict:
        """Extract AI function parameters from context"""
        return context.metadata.get("parameters", {})

    def _validate_required_params(self, params: dict, required: list[str]) -> list[str]:
        """Validate that required parameters are present"""
        missing = []
        for param in required:
            if param not in params or params[param] is None:
                missing.append(param)
        return missing
