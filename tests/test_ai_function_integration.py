"""
Test suite for AI function integration.

Tests the integration between @ai_function decorator, Plugin system, and AI function calling.
"""

from unittest.mock import Mock

import pytest

from src.agent.plugins.base import AIFunctionPlugin, Plugin
from src.agent.plugins.decorators import ai_function, capability
from src.agent.plugins.models import CapabilityContext, CapabilityResult


class TestAIFunctionIntegration:
    """Test AI function integration with the plugin system."""

    def test_ai_function_decorator_creates_capability(self):
        """Test that @ai_function decorator creates a proper capability."""

        class AITestPlugin(Plugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": ["query"],
                },
                name="search_function",
                description="Search for information",
            )
            async def search_data(self, context: CapabilityContext) -> str:
                return "search results"

        plugin = AITestPlugin()

        # Should create a capability with AI function properties
        assert "search_data" in plugin._capabilities
        capability_meta = plugin._capabilities["search_data"]

        assert capability_meta.ai_function is True
        assert capability_meta.name == "search_function"
        assert capability_meta.description == "Search for information"
        assert capability_meta.ai_parameters["type"] == "object"
        assert "query" in capability_meta.ai_parameters["properties"]

    def test_ai_function_vs_capability_ai_function_flag(self):
        """Test the relationship between @ai_function and @capability(ai_function=True)."""

        class ComparisonPlugin(Plugin):
            @ai_function(
                parameters={"type": "object", "properties": {"input": {"type": "string"}}},
                name="method1",
                description="Method 1",
            )
            async def method_with_ai_function_decorator(self, context: CapabilityContext) -> str:
                return "result1"

            @capability(
                "method2",
                name="Method 2",
                description="Method 2",
                ai_function=True,
                ai_parameters={"type": "object", "properties": {"input": {"type": "string"}}},
            )
            async def method_with_ai_flag(self, context: CapabilityContext) -> str:
                return "result2"

        plugin = ComparisonPlugin()

        # Both should be marked as AI functions
        method1_meta = plugin._capabilities["method_with_ai_function_decorator"]
        method2_meta = plugin._capabilities["method2"]

        assert method1_meta.ai_function is True
        assert method2_meta.ai_function is True

        # Both should have AI parameters
        assert method1_meta.ai_parameters is not None
        assert method2_meta.ai_parameters is not None

    def test_get_ai_functions_from_plugin(self):
        """Test getting AI functions from a plugin."""

        class AIPlugin(Plugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "Text to analyze"}},
                    "required": ["text"],
                }
            )
            async def analyze_text(self, context: CapabilityContext) -> str:
                return "analysis result"

            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {"data": {"type": "array", "description": "Data to process"}},
                }
            )
            async def process_data(self, context: CapabilityContext) -> str:
                return "processed data"

            @capability("regular_capability")
            async def regular_method(self, context: CapabilityContext) -> str:
                return "regular result"

        plugin = AIPlugin()

        # Get all AI functions
        all_ai_functions = plugin.get_ai_functions()
        assert len(all_ai_functions) == 2

        function_names = [func.name for func in all_ai_functions]
        assert "analyze_text" in function_names
        assert "process_data" in function_names

        # Get specific AI function
        specific_functions = plugin.get_ai_functions("analyze_text")
        assert len(specific_functions) == 1
        assert specific_functions[0].name == "analyze_text"

    def test_ai_function_openai_compatibility(self):
        """Test OpenAI function calling format compatibility."""

        class OpenAICompatiblePlugin(Plugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"},
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit",
                        },
                    },
                    "required": ["location"],
                },
                name="get_current_weather",
                description="Get the current weather in a given location",
            )
            async def get_weather(self, context: CapabilityContext) -> str:
                return "weather data"

        plugin = OpenAICompatiblePlugin()
        ai_functions = plugin.get_ai_functions()

        assert len(ai_functions) == 1
        weather_func = ai_functions[0]

        # Check OpenAI-compatible structure
        assert weather_func.name == "get_weather"  # Uses method name as AI function name
        assert weather_func.description == "Get the current weather in a given location"

        params = weather_func.parameters
        assert params["type"] == "object"
        assert "location" in params["properties"]
        assert "unit" in params["properties"]
        assert params["required"] == ["location"]
        assert params["properties"]["unit"]["enum"] == ["celsius", "fahrenheit"]

    def test_ai_function_parameter_validation(self):
        """Test AI function parameter schema validation."""

        class ValidationPlugin(Plugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer", "minimum": 0, "maximum": 100},
                        "text": {"type": "string", "maxLength": 50},
                        "flag": {"type": "boolean"},
                    },
                    "required": ["number"],
                }
            )
            async def validate_params(self, context: CapabilityContext) -> str:
                params = self._extract_ai_parameters(context)

                # Validate required parameters
                missing = self._validate_required_params(params, ["number"])
                if missing:
                    return f"Missing required parameters: {missing}"

                # Basic type validation (in real implementation)
                number = params.get("number")
                if not isinstance(number, int) or not (0 <= number <= 100):
                    return "Invalid number parameter"

                return "validation passed"

        plugin = ValidationPlugin()
        ai_functions = plugin.get_ai_functions()

        # Check parameter schema
        func = ai_functions[0]
        params = func.parameters

        assert params["properties"]["number"]["minimum"] == 0
        assert params["properties"]["number"]["maximum"] == 100
        assert params["properties"]["text"]["maxLength"] == 50
        assert params["required"] == ["number"]

    @pytest.mark.asyncio
    async def test_ai_function_parameter_extraction(self):
        """Test AI function parameter extraction from context."""

        class ExtractionPlugin(AIFunctionPlugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {"param1": {"type": "string"}, "param2": {"type": "integer"}},
                }
            )
            async def extract_test(self, context: CapabilityContext) -> str:
                params = self._extract_ai_parameters(context)

                param1 = params.get("param1", "default")
                param2 = params.get("param2", 0)

                return f"param1={param1}, param2={param2}"

        plugin = ExtractionPlugin()

        # Create context with AI parameters
        context = Mock(spec=CapabilityContext)
        context.metadata = {"parameters": {"param1": "test_value", "param2": 42}}

        result = await plugin.execute_capability("extract_test", context)

        assert result.success is True
        assert "param1=test_value" in result.content
        assert "param2=42" in result.content

    def test_ai_function_handler_binding(self):
        """Test that AI function handlers are properly bound to methods."""

        class HandlerPlugin(Plugin):
            @ai_function(parameters={"type": "object"})
            async def test_handler(self, context: CapabilityContext) -> str:
                return "handler result"

        plugin = HandlerPlugin()
        ai_functions = plugin.get_ai_functions()

        func = ai_functions[0]
        assert func.handler == plugin.test_handler
        assert callable(func.handler)

    def test_capability_definition_includes_ai_function_info(self):
        """Test that capability definitions include AI function information."""

        class DefPlugin(Plugin):
            @ai_function(
                parameters={"type": "object", "properties": {"input": {"type": "string"}}},
                name="ai_function_name",
                description="AI function description",
            )
            async def ai_method(self, context: CapabilityContext) -> str:
                return "result"

            @capability("regular_cap", name="Regular Capability")
            async def regular_method(self, context: CapabilityContext) -> str:
                return "regular"

        plugin = DefPlugin()
        capability_defs = plugin.get_capability_definitions()

        # Find the AI function capability
        ai_cap = next(cap for cap in capability_defs if cap.id == "ai_method")
        regular_cap = next(cap for cap in capability_defs if cap.id == "regular_cap")

        # AI capability should include AI_FUNCTION in capabilities
        from src.agent.plugins.models import CapabilityType

        assert CapabilityType.AI_FUNCTION in ai_cap.capabilities
        assert CapabilityType.AI_FUNCTION not in regular_cap.capabilities

    def test_ai_function_with_complex_schema(self):
        """Test AI function with complex JSON schema."""

        class ComplexSchemaPlugin(Plugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {
                        "user": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "age": {"type": "integer", "minimum": 0}},
                            "required": ["name"],
                        },
                        "preferences": {"type": "array", "items": {"type": "string", "enum": ["email", "sms", "push"]}},
                        "metadata": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["user"],
                }
            )
            async def complex_function(self, context: CapabilityContext) -> str:
                return "complex result"

        plugin = ComplexSchemaPlugin()
        ai_functions = plugin.get_ai_functions()

        func = ai_functions[0]
        params = func.parameters

        # Verify complex schema structure
        assert params["properties"]["user"]["type"] == "object"
        assert params["properties"]["user"]["required"] == ["name"]
        assert params["properties"]["preferences"]["type"] == "array"
        assert params["properties"]["preferences"]["items"]["enum"] == ["email", "sms", "push"]
        assert params["properties"]["metadata"]["additionalProperties"] is True

    def test_ai_function_without_parameters_fails_validation(self):
        """Test that AI functions without parameters fail validation."""
        from src.agent.plugins.decorators import CapabilityMetadata, validate_capability_metadata

        # Create metadata for AI function without parameters
        metadata = CapabilityMetadata(
            id="invalid_ai_func",
            name="Invalid AI Function",
            description="AI function without parameters",
            method_name="invalid_method",
            ai_function=True,  # AI function but no ai_parameters
        )

        errors = validate_capability_metadata(metadata)

        # Should have validation error
        assert len(errors) > 0
        assert any("AI functions must specify ai_parameters" in error for error in errors)

    @pytest.mark.asyncio
    async def test_ai_function_execution_with_parameters(self):
        """Test executing AI function with parameter handling."""

        class ExecutionPlugin(AIFunctionPlugin):
            @ai_function(
                parameters={
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["add", "multiply"]},
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["operation", "a", "b"],
                }
            )
            async def calculate(self, context: CapabilityContext) -> CapabilityResult:
                params = self._extract_ai_parameters(context)

                # Validate required parameters
                missing = self._validate_required_params(params, ["operation", "a", "b"])
                if missing:
                    return CapabilityResult(
                        content=f"Missing parameters: {missing}", success=False, error="Missing required parameters"
                    )

                operation = params["operation"]
                a = params["a"]
                b = params["b"]

                if operation == "add":
                    result = a + b
                elif operation == "multiply":
                    result = a * b
                else:
                    return CapabilityResult(content="Invalid operation", success=False, error="Invalid operation")

                return CapabilityResult(
                    content=f"Result: {result}", success=True, metadata={"operation": operation, "result": result}
                )

        plugin = ExecutionPlugin()

        # Test successful execution
        context = Mock(spec=CapabilityContext)
        context.metadata = {"parameters": {"operation": "add", "a": 5, "b": 3}}

        result = await plugin.execute_capability("calculate", context)

        assert result.success is True
        assert "Result: 8" in result.content
        assert result.metadata["result"] == 8

        # Test missing parameters
        context.metadata = {"parameters": {"operation": "add", "a": 5}}  # Missing 'b'

        result = await plugin.execute_capability("calculate", context)

        assert result.success is False
        assert "Missing parameters" in result.content

    def test_multiple_ai_functions_in_single_plugin(self):
        """Test plugin with multiple AI functions."""

        class MultiAIPlugin(Plugin):
            @ai_function(parameters={"type": "object", "properties": {"text": {"type": "string"}}})
            async def function1(self, context: CapabilityContext) -> str:
                return "result1"

            @ai_function(parameters={"type": "object", "properties": {"number": {"type": "integer"}}})
            async def function2(self, context: CapabilityContext) -> str:
                return "result2"

            @ai_function(parameters={"type": "object", "properties": {"flag": {"type": "boolean"}}})
            async def function3(self, context: CapabilityContext) -> str:
                return "result3"

        plugin = MultiAIPlugin()

        # Should have 3 AI functions
        ai_functions = plugin.get_ai_functions()
        assert len(ai_functions) == 3

        function_names = [func.name for func in ai_functions]
        assert "function1" in function_names
        assert "function2" in function_names
        assert "function3" in function_names

        # Each should have different parameter schemas
        func1 = next(func for func in ai_functions if func.name == "function1")
        func2 = next(func for func in ai_functions if func.name == "function2")
        func3 = next(func for func in ai_functions if func.name == "function3")

        assert "text" in func1.parameters["properties"]
        assert "number" in func2.parameters["properties"]
        assert "flag" in func3.parameters["properties"]
