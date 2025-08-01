"""
Base plugin class for the decorator-based plugin system.

This module provides the Plugin base class that automatically discovers
@capability decorated methods and handles plugin lifecycle.
"""

import inspect
from typing import Any

import structlog

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

        # Auto-discover capabilities
        self._discover_capabilities()

    def _discover_capabilities(self):
        """Automatically discover all @capability decorated methods"""
        for _name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            capabilities = get_capability_metadata(method)

            for capability_meta in capabilities:
                # Validate capability metadata
                errors = validate_capability_metadata(capability_meta)
                if errors:
                    logger.error(f"Invalid capability {capability_meta.id} in {self.__class__.__name__}: {errors}")
                    continue

                # Bind the handler to this instance
                capability_meta.handler = method
                self._capabilities[capability_meta.id] = capability_meta

                logger.debug(f"Discovered capability '{capability_meta.id}' in {self.__class__.__name__}")

    # === Core Plugin Interface ===

    async def execute_capability(self, capability_id: str, context: CapabilityContext) -> CapabilityResult:
        """Execute a specific capability by ID"""
        if capability_id not in self._capabilities:
            return CapabilityResult(
                content=f"Capability '{capability_id}' not found",
                success=False,
                error="Capability not found"
            )

        capability = self._capabilities[capability_id]
        try:
            logger.debug(f"Executing capability '{capability_id}' via method '{capability.method_name}'")

            # Call the decorated method
            result = await capability.handler(context)

            # Handle different return types
            if isinstance(result, CapabilityResult):
                return result
            elif isinstance(result, str):
                return CapabilityResult(content=result, success=True)
            elif isinstance(result, dict):
                return CapabilityResult(
                    content=str(result),
                    success=True,
                    metadata=result if isinstance(result, dict) else {}
                )
            else:
                return CapabilityResult(content=str(result), success=True)

        except Exception as e:
            logger.error(f"Error executing capability {capability_id}: {e}", exc_info=True)
            return CapabilityResult(
                content=f"Error executing capability: {str(e)}",
                success=False,
                error=str(e)
            )

    def get_capability_definitions(self) -> list[CapabilityDefinition]:
        """Get all capability definitions for this plugin"""
        definitions = []

        for capability_meta in self._capabilities.values():
            # Convert metadata to CapabilityDefinition
            definition = CapabilityDefinition(
                id=capability_meta.id,
                name=capability_meta.name,
                version="1.0.0",  # TODO: Get from plugin metadata
                description=capability_meta.description,
                plugin_name=self.__class__.__name__.lower().replace("plugin", ""),
                capabilities=capability_meta.to_capability_types(),
                input_mode=capability_meta.input_mode,
                output_mode=capability_meta.output_mode,
                tags=capability_meta.tags,
                priority=capability_meta.priority,
                config_schema=capability_meta.config_schema,
                required_scopes=capability_meta.scopes,
                system_prompt=None,  # TODO: Add system_prompt to decorator
                metadata={"method_name": capability_meta.method_name}
            )
            definitions.append(definition)

        return definitions

    def get_ai_functions(self, capability_id: str | None = None) -> list[AIFunction]:
        """Get AI functions for capabilities"""
        functions = []

        # Filter capabilities
        if capability_id:
            if capability_id not in self._capabilities:
                return []
            capabilities = [self._capabilities[capability_id]]
        else:
            capabilities = self._capabilities.values()

        # Generate AI functions for capabilities that support it
        for capability_meta in capabilities:
            if capability_meta.ai_function:
                ai_func = AIFunction(
                    name=capability_meta.id,
                    description=capability_meta.description,
                    parameters=capability_meta.ai_parameters,
                    handler=self._create_ai_function_wrapper(capability_meta)
                )
                functions.append(ai_func)

        return functions

    def _create_ai_function_wrapper(self, capability_meta: CapabilityMetadata):
        """Create wrapper for AI function calls"""
        async def wrapper(task, context: CapabilityContext):
            # Extract AI function parameters from context
            params = context.metadata.get("parameters", {})

            # Create new context with parameters for the capability
            ai_context = CapabilityContext(
                task=task,
                config=context.config,
                services=context.services,
                state=context.state,
                metadata={
                    "parameters": params,
                    "capability_id": capability_meta.id,
                    "ai_function_call": True
                }
            )

            # Execute the capability
            result = await capability_meta.handler(ai_context)

            # Convert result to expected format for AI functions
            if isinstance(result, CapabilityResult):
                return result
            else:
                return CapabilityResult(content=str(result), success=True)

        return wrapper

    def can_handle_task(self, capability_id: str, context: CapabilityContext) -> bool | float:
        """Check if this plugin can handle a task for a specific capability"""
        if capability_id not in self._capabilities:
            return False

        capability_meta = self._capabilities[capability_id]

        # Default routing based on tags and priority
        if capability_meta.tags:
            # Simple keyword matching against task content
            task_content = self._extract_task_content(context)

            # Check if any tags match the task content
            matches = sum(1 for tag in capability_meta.tags if tag.lower() in task_content.lower())

            if matches > 0:
                # Calculate confidence based on matches and priority
                base_confidence = min(matches * 0.3, 0.9)  # Max 0.9 from tag matches
                priority_bonus = capability_meta.priority / 1000  # Small priority bonus
                return min(base_confidence + priority_bonus, 1.0)

        # Default confidence for capabilities without tags
        return 0.1 if capability_meta.priority >= 50 else 0.05

    # === Service and Configuration Management ===

    def configure_services(self, services: dict[str, Any]):
        """Store services for use by capabilities"""
        self._services.update(services)
        logger.debug(f"Configured {len(services)} services for {self.__class__.__name__}")

    def configure(self, config: dict[str, Any]):
        """Configure the plugin"""
        self._config.update(config)
        logger.debug(f"Configured plugin {self.__class__.__name__} with {len(config)} settings")

    def get_service(self, name: str) -> Any:
        """Get a service by name"""
        return self._services.get(name)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)

    def update_state(self, updates: dict[str, Any]):
        """Update plugin state"""
        self._state.update(updates)

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value"""
        return self._state.get(key, default)

    """
    Luke: Plugin Lifecycle Hooks (Optional Override)
    The following lifecycle methods are as marked as abstract since so they can be optionally
    overridden by subclasses. However, since they are lifecycle hooks that not all plugins need to implement,
    we should use @abstractmethod only if we want to force implementation, or provide default implementations
    as they currently do.
    """

    async def on_install(self, install_path: str):  # noqa: B027
        """Called when plugin is installed (override in subclass if needed)"""
        pass

    async def on_uninstall(self):  # noqa: B027
        """Called when plugin is uninstalled (override in subclass if needed)"""
        pass

    async def on_enable(self):  # noqa: B027
        """Called when plugin is enabled (override in subclass if needed)"""
        pass

    async def on_disable(self):  # noqa: B027
        """Called when plugin is disabled (override in subclass if needed)"""
        pass

    async def get_health_status(self) -> dict:
        """Return plugin health information (override in subclass if needed)"""
        return {
            "status": "healthy",
            "capabilities": len(self._capabilities),
            "services_configured": len(self._services),
            "config_items": len(self._config)
        }

    # === Helper Methods ===

    def _extract_task_content(self, context: CapabilityContext) -> str:
        """Extract text content from task for routing analysis"""
        try:
            if hasattr(context.task, "history") and context.task.history:
                last_msg = context.task.history[-1]
                if hasattr(last_msg, "parts") and last_msg.parts:
                    return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
            return ""
        except Exception:
            return ""

    # === Plugin Information ===

    @property
    def plugin_id(self) -> str:
        """Get plugin ID (derived from class name)"""
        return self.__class__.__name__.lower().replace("plugin", "")

    @property
    def plugin_name(self) -> str:
        """Get plugin display name"""
        return self.__class__.__name__

    @property
    def capability_count(self) -> int:
        """Get number of capabilities provided by this plugin"""
        return len(self._capabilities)

    @property
    def capability_ids(self) -> list[str]:
        """Get list of capability IDs provided by this plugin"""
        return list(self._capabilities.keys())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(capabilities={self.capability_count})"


class SimplePlugin(Plugin):
    """
    Simplified base class for plugins with a single capability.

    This class is for plugins that only provide one capability and want
    a simpler interface.

    Example:
        class GreetingPlugin(SimplePlugin):
            capability_id = "greet"
            capability_name = "Greeting"
            scopes = ["api:read"]

            async def execute(self, context: CapabilityContext) -> str:
                return "Hello!"
    """

    # Override these in subclasses
    capability_id: str = "simple"
    capability_name: str = "Simple Capability"
    capability_description: str = "A simple capability"
    scopes: list[str] = []
    ai_function: bool = False
    ai_parameters: dict = {}

    def __init__(self):
        # Auto-register the single capability using decorator
        if hasattr(self, 'execute'):
            from .decorators import capability

            # Apply the capability decorator to the execute method
            decorated_execute = capability(
                id=self.capability_id,
                name=self.capability_name,
                description=self.capability_description,
                scopes=self.scopes,
                ai_function=self.ai_function,
                ai_parameters=self.ai_parameters
            )(self.execute)

            # Replace the execute method with the decorated version
            self.execute = decorated_execute.__get__(self, self.__class__)

        super().__init__()

    async def execute(self, context: CapabilityContext) -> str:
        """Override this method in subclasses"""
        raise NotImplementedError("SimplePlugin subclasses must implement execute()")


class AIFunctionPlugin(Plugin):
    """
    Base class for plugins that primarily provide AI-callable functions.

    This class provides helpers for plugins that focus on AI function calling.

    Example:
        class CalculatorPlugin(AIFunctionPlugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression"}
                    }
                }
            )
            async def calculate(self, context: CapabilityContext) -> str:
                expr = context.metadata.get("parameters", {}).get("expression")
                return str(eval(expr))  # Don't do this in real code!
    """

    def __init__(self):
        super().__init__()

    def get_ai_function_schemas(self) -> list[dict]:
        """Get OpenAI-compatible function schemas for all AI functions"""
        schemas = []

        for ai_func in self.get_ai_functions():
            schema = {
                "name": ai_func.name,
                "description": ai_func.description,
                "parameters": ai_func.parameters
            }
            schemas.append(schema)

        return schemas

    async def call_ai_function(self, function_name: str, parameters: dict, task, context: CapabilityContext) -> CapabilityResult:
        """Call an AI function by name with parameters"""
        # Find the capability that provides this AI function
        for capability_id, capability_meta in self._capabilities.items():
            if capability_meta.ai_function and capability_meta.id == function_name:
                # Create context with AI function parameters
                ai_context = CapabilityContext(
                    task=task,
                    config=context.config,
                    services=context.services,
                    state=context.state,
                    metadata={
                        "parameters": parameters,
                        "capability_id": capability_id,
                        "ai_function_call": True
                    }
                )

                return await self.execute_capability(capability_id, ai_context)

        return CapabilityResult(
            content=f"AI function '{function_name}' not found",
            success=False,
            error="Function not found"
        )
