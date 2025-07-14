"""
Belongs in tree as used for unit tests
"""

import pluggy

from .models import AIFunction, CapabilityContext, CapabilityInfo, CapabilityResult, CapabilityType, ValidationResult

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("agentup")


class ExamplePlugin:
    """Example capability plugin for testing and demonstration."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "example"
        self.llm_service = None

    @hookimpl
    def register_capability(self) -> CapabilityInfo:
        """Register the example capability."""
        return CapabilityInfo(
            id="example",
            name="Example Capability",
            version="1.0.0",
            description="A simple example capability demonstrating the plugin system",
            capabilities=[CapabilityType.TEXT, CapabilityType.AI_FUNCTION],
            tags=["example", "demo", "test"],
            config_schema={
                "type": "object",
                "properties": {
                    "greeting": {"type": "string", "default": "Hello", "description": "Greeting to use"},
                    "excited": {"type": "boolean", "default": False, "description": "Whether to add excitement"},
                },
            },
        )

    @hookimpl
    def validate_config(self, config: dict) -> ValidationResult:
        """Validate the configuration."""
        errors = []
        warnings = []

        # Check greeting length
        greeting = config.get("greeting", "Hello")
        if len(greeting) > 50:
            errors.append("Greeting is too long (max 50 characters)")
        elif len(greeting) < 2:
            warnings.append("Greeting is very short")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    @hookimpl
    def can_handle_task(self, context: CapabilityContext) -> float:
        """Check if we can handle this task."""
        # Get the task content
        content = ""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                content = last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""

        # Simple keyword matching for demonstration
        keywords = ["example", "demo", "test", "hello", "greet"]
        content_lower = content.lower()

        # Calculate confidence based on keyword matches
        matches = sum(1 for keyword in keywords if keyword in content_lower)
        confidence = min(matches * 0.3, 1.0)

        return confidence

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute the example skill."""
        # Get configuration
        config = context.config
        greeting = config.get("greeting", "Hello")
        excited = config.get("excited", False)

        # Get user input
        user_input = self._extract_user_input(context)

        # Generate response
        response = f"{greeting}, you said: {user_input}"
        if excited:
            response += "!!!"

        return CapabilityResult(
            content=response, success=True, metadata={"capability": "example", "processed_by": "example_plugin"}
        )

    @hookimpl
    def get_ai_functions(self) -> list[AIFunction]:
        """Provide AI functions for LLM function calling."""
        return [
            AIFunction(
                name="greet_user",
                description="Greet the user with a custom message",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the person to greet"},
                        "style": {
                            "type": "string",
                            "enum": ["formal", "casual", "excited"],
                            "description": "Greeting style",
                        },
                    },
                    "required": ["name"],
                },
                handler=self._greet_user,
            ),
            AIFunction(
                name="echo_message",
                description="Echo a message back to the user",
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to echo"},
                        "uppercase": {"type": "boolean", "description": "Whether to convert to uppercase"},
                    },
                    "required": ["message"],
                },
                handler=self._echo_message,
            ),
        ]

    async def _greet_user(self, task, context: CapabilityContext) -> CapabilityResult:
        """Handle the greet_user function."""
        # Extract parameters from task metadata
        params = context.metadata.get("parameters", {})
        name = params.get("name", "Friend")
        style = params.get("style", "casual")

        # Generate greeting based on style
        if style == "formal":
            greeting = f"Good day, {name}. How may I assist you?"
        elif style == "excited":
            greeting = f"Hey {name}!!! So great to see you!!!"
        else:  # casual
            greeting = f"Hi {name}, how's it going?"

        return CapabilityResult(content=greeting, success=True)

    async def _echo_message(self, task, context: CapabilityContext) -> CapabilityResult:
        """Handle the echo_message function."""
        params = context.metadata.get("parameters", {})
        message = params.get("message", "")
        uppercase = params.get("uppercase", False)

        result = message.upper() if uppercase else message
        return CapabilityResult(content=f"Echo: {result}", success=True)

    @hookimpl
    def configure_services(self, services: dict) -> None:
        """Configure services for the plugin."""
        # Store reference to LLM service if available
        if "llm" in services:
            self.llm_service = services["llm"]

    @hookimpl
    def get_middleware_config(self) -> list[dict]:
        """Request middleware for this capability."""
        return [{"type": "rate_limit", "requests_per_minute": 100}, {"type": "logging", "level": "INFO"}]

    @hookimpl
    def get_health_status(self) -> dict:
        """Report health status."""
        return {"status": "healthy", "version": "1.0.0", "has_llm": self.llm_service is not None}

    def _extract_user_input(self, context: CapabilityContext) -> str:
        """Extract user input from the task."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""
