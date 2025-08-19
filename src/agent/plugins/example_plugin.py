"""
Example plugin for testing and demonstration purposes.

This plugin shows how to create a basic AgentUp plugin using the decorator-based system.
"""

from typing import Any

from agent.plugins.base import Plugin
from agent.plugins.decorators import capability
from agent.plugins.models import (
    AIFunction,
    CapabilityContext,
    CapabilityDefinition,
    CapabilityResult,
    PluginValidationResult,
)


class ExamplePlugin(Plugin):
    """Example plugin demonstrating the plugin system capabilities."""

    def __init__(self):
        super().__init__()
        self.plugin_id = "example"
        self.greeting = "Hello"
        self.excited = False

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with settings."""
        self.greeting = config.get("greeting", "Hello")
        self.excited = config.get("excited", False)

    def register_capability(self) -> CapabilityDefinition:
        """Register capability and return definition."""
        # This is needed for backward compatibility with tests
        # The decorator already registered the capability, so we just return the definition
        for cap_def in self.get_capability_definitions():
            if cap_def.id == "example":
                return cap_def
        raise ValueError("Example capability not found")

    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Synchronous wrapper for execute_capability - for backward compatibility with tests."""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(super().execute_capability("example", context))
        finally:
            loop.close()

    @capability(
        id="example",
        name="Example Capability",
        description="A simple example capability that greets users",
        ai_function=True,
    )
    async def example_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute the example capability."""
        # Extract task content
        task_content = self._extract_task_content(context)

        # Create response
        response = f"{self.greeting}, you said: {task_content}"
        if self.excited:
            response += "!"

        return CapabilityResult(content=response, success=True, metadata={"processed_by": "example_plugin"})

    def can_handle_task(self, capability_id: str, context: CapabilityContext) -> bool | float:
        """Check if this plugin can handle the task."""
        if capability_id != "example":
            return False

        task_content = self._extract_task_content(context)

        # Check for keywords that indicate this plugin should handle the task
        keywords = ["example", "test", "demo", "greeting", "hello"]
        task_lower = task_content.lower()

        for keyword in keywords:
            if keyword in task_lower:
                return 1.0  # High confidence

        return 0.0  # Cannot handle

    def get_ai_functions(self, capability_id: str | None = None) -> list[AIFunction]:
        """Get AI functions for this capability."""
        if capability_id and capability_id != "example":
            return []

        return [
            AIFunction(
                name="greet_user",
                description="Greet a user with a custom message",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name of the user to greet"},
                        "style": {
                            "type": "string",
                            "enum": ["formal", "casual", "excited"],
                            "description": "The greeting style",
                        },
                    },
                    "required": ["name"],
                },
            ),
            AIFunction(
                name="echo_message",
                description="Echo back a message with the configured greeting",
                parameters={
                    "type": "object",
                    "properties": {"message": {"type": "string", "description": "The message to echo"}},
                    "required": ["message"],
                },
            ),
        ]

    def validate_config(self, config: dict[str, Any]) -> PluginValidationResult:
        """Validate plugin configuration."""
        errors = []
        warnings = []

        # Check greeting length
        greeting = config.get("greeting", "")
        if len(greeting) > 50:
            errors.append("Greeting must be 50 characters or less")

        # Check excited is boolean
        excited = config.get("excited")
        if excited is not None and not isinstance(excited, bool):
            errors.append("Excited must be a boolean value")

        return PluginValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def get_middleware_config(self) -> list[dict[str, Any]]:
        """Get middleware configuration for this plugin."""
        return [
            {"type": "rate_limit", "config": {"requests_per_minute": 60, "burst_size": 72}},
            {"type": "logging", "config": {"log_level": "INFO"}},
        ]

    async def get_health_status(self) -> dict[str, Any]:
        """Get plugin health status."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "has_llm": hasattr(self, "_llm") and self._llm is not None,
            "capabilities": ["example"],
            "configured": True,
        }

    def _extract_task_content(self, context: CapabilityContext) -> str:
        """Extract content from task in context."""
        task = context.task
        if hasattr(task, "content"):
            return task.content
        elif hasattr(task, "messages") and task.messages:
            return task.messages[0].content
        elif hasattr(task, "message"):
            return task.message
        else:
            return str(task)
