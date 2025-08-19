"""
Test suite for Plugin base class and capability discovery.

Tests the base Plugin class that automatically discovers @capability decorated methods.
"""

from unittest.mock import Mock, patch

import pytest

from src.agent.plugins.base import AIFunctionPlugin, Plugin, SimplePlugin
from src.agent.plugins.decorators import ai_function, capability
from src.agent.plugins.models import CapabilityContext, CapabilityDefinition, CapabilityResult


class TestPluginBaseClass:
    """Test the Plugin base class functionality."""

    def test_plugin_initialization(self):
        """Test Plugin base class initialization."""
        plugin = Plugin()

        assert plugin._capabilities == {}
        assert plugin._services == {}
        assert plugin._config == {}
        assert plugin._state == {}
        assert hasattr(plugin, "plugin_name")

    def test_plugin_name_generation(self):
        """Test plugin ID generation from class name."""

        class TestPlugin(Plugin):
            pass

        class WeatherPlugin(Plugin):
            pass

        class DataProcessingPlugin(Plugin):
            pass

        test_plugin = TestPlugin()
        weather_plugin = WeatherPlugin()
        data_plugin = DataProcessingPlugin()

        assert test_plugin.plugin_name == "test"
        assert weather_plugin.plugin_name == "weather"
        assert data_plugin.plugin_name == "dataprocessing"

    def test_capability_discovery_basic(self):
        """Test basic capability discovery from decorated methods."""

        class TestPlugin(Plugin):
            @capability("test_cap", name="Test Capability")
            async def test_method(self, context: CapabilityContext) -> str:
                return "test result"

        plugin = TestPlugin()

        assert "test_cap" in plugin._capabilities
        cap_meta = plugin._capabilities["test_cap"]
        assert cap_meta.id == "test_cap"
        assert cap_meta.name == "Test Capability"
        assert cap_meta.method_name == "test_method"
        assert cap_meta.handler == plugin.test_method

    def test_capability_discovery_multiple(self):
        """Test discovery of multiple capabilities in one plugin."""

        class MultiCapabilityPlugin(Plugin):
            @capability("first", name="First Capability")
            async def first_method(self, context: CapabilityContext) -> str:
                return "first"

            @capability("second", name="Second Capability")
            async def second_method(self, context: CapabilityContext) -> str:
                return "second"

            @ai_function(parameters={"type": "object"})
            async def ai_method(self, context: CapabilityContext) -> str:
                return "ai result"

        plugin = MultiCapabilityPlugin()

        assert len(plugin._capabilities) == 3
        assert "first" in plugin._capabilities
        assert "second" in plugin._capabilities
        assert "ai_method" in plugin._capabilities  # AI function creates capability with method name

        # Check AI function is properly configured
        ai_cap = plugin._capabilities["ai_method"]
        assert ai_cap.ai_function is True

    def test_capability_discovery_validation(self):
        """Test that invalid capabilities are rejected during discovery."""

        class InvalidPlugin(Plugin):
            @capability("", name="Invalid Empty ID")  # Empty ID should be invalid
            async def invalid_method(self, context: CapabilityContext) -> str:
                return "invalid"

            @capability("valid", name="Valid Capability")
            async def valid_method(self, context: CapabilityContext) -> str:
                return "valid"

        plugin = InvalidPlugin()

        # Only valid capability should be discovered
        assert "valid" in plugin._capabilities
        assert "" not in plugin._capabilities
        assert len(plugin._capabilities) == 1

    def test_capability_discovery_inheritance(self):
        """Test capability discovery works with inheritance."""

        class BasePlugin(Plugin):
            @capability("base_cap", name="Base Capability")
            async def base_method(self, context: CapabilityContext) -> str:
                return "base"

        class ChildPlugin(BasePlugin):
            @capability("child_cap", name="Child Capability")
            async def child_method(self, context: CapabilityContext) -> str:
                return "child"

        plugin = ChildPlugin()

        assert len(plugin._capabilities) == 2
        assert "base_cap" in plugin._capabilities
        assert "child_cap" in plugin._capabilities

    @pytest.mark.asyncio
    async def test_execute_capability_success(self):
        """Test successful capability execution."""

        class TestPlugin(Plugin):
            @capability("test", name="Test")
            async def test_method(self, context: CapabilityContext) -> str:
                return "success"

        plugin = TestPlugin()
        context = Mock(spec=CapabilityContext)

        result = await plugin.execute_capability("test", context)

        assert isinstance(result, CapabilityResult)
        assert result.success is True
        assert result.content == "success"

    @pytest.mark.asyncio
    async def test_execute_capability_not_found(self):
        """Test execution of non-existent capability."""
        plugin = Plugin()
        context = Mock(spec=CapabilityContext)

        result = await plugin.execute_capability("nonexistent", context)

        assert isinstance(result, CapabilityResult)
        assert result.success is False
        assert "not found" in result.content
        assert result.error == "Capability not found"

    @pytest.mark.asyncio
    async def test_execute_capability_return_types(self):
        """Test different return types from capability execution."""

        class TestPlugin(Plugin):
            @capability("string_result")
            async def string_method(self, context: CapabilityContext) -> str:
                return "string result"

            @capability("dict_result")
            async def dict_method(self, context: CapabilityContext) -> dict:
                return {"key": "value", "status": "ok"}

            @capability("result_object")
            async def result_method(self, context: CapabilityContext) -> CapabilityResult:
                return CapabilityResult(content="custom result", success=True, metadata={"custom": True})

            @capability("other_type")
            async def other_method(self, context: CapabilityContext) -> int:
                return 42

        plugin = TestPlugin()
        context = Mock(spec=CapabilityContext)

        # Test string return
        result = await plugin.execute_capability("string_result", context)
        assert result.success is True
        assert result.content == "string result"

        # Test dict return
        result = await plugin.execute_capability("dict_result", context)
        assert result.success is True
        assert result.content == "{'key': 'value', 'status': 'ok'}"
        assert result.metadata == {"key": "value", "status": "ok"}

        # Test CapabilityResult return
        result = await plugin.execute_capability("result_object", context)
        assert result.success is True
        assert result.content == "custom result"
        assert result.metadata == {"custom": True}

        # Test other type return
        result = await plugin.execute_capability("other_type", context)
        assert result.success is True
        assert result.content == "42"

    @pytest.mark.asyncio
    async def test_execute_capability_exception_handling(self):
        """Test exception handling during capability execution."""

        class TestPlugin(Plugin):
            @capability("error_cap")
            async def error_method(self, context: CapabilityContext) -> str:
                raise ValueError("Test error")

        plugin = TestPlugin()
        context = Mock(spec=CapabilityContext)
        # Ensure context has proper attributes to avoid Mock iteration issues
        context.task = Mock()
        context.metadata = {}

        with patch("src.agent.plugins.base.logger"):  # Mock logger to avoid rich formatting issues
            result = await plugin.execute_capability("error_cap", context)

        assert isinstance(result, CapabilityResult)
        assert result.success is False
        assert "Test error" in result.content
        assert "Test error" in result.error

    def test_can_handle_task_default(self):
        """Test default can_handle_task implementation."""

        class TestPlugin(Plugin):
            @capability("test")
            async def test_method(self, context: CapabilityContext) -> str:
                return "test"

        plugin = TestPlugin()
        context = Mock(spec=CapabilityContext)

        # Should return True for existing capability
        assert plugin.can_handle_task("test", context) is True

        # Should return False for non-existent capability
        assert plugin.can_handle_task("nonexistent", context) is False

    def test_can_handle_task_custom_override(self):
        """Test custom can_handle_task implementation."""

        class TestPlugin(Plugin):
            @capability("test")
            async def test_method(self, context: CapabilityContext) -> str:
                return "test"

            def can_handle_task(self, capability_id: str, context: CapabilityContext) -> bool | float:
                if capability_id == "test":
                    return 0.8  # Return confidence score
                return False

        plugin = TestPlugin()
        context = Mock(spec=CapabilityContext)

        assert plugin.can_handle_task("test", context) == 0.8
        assert plugin.can_handle_task("other", context) is False

    def test_get_capability_definitions(self):
        """Test getting capability definitions."""

        class TestPlugin(Plugin):
            @capability(
                "test_cap", name="Test Capability", description="A test capability", scopes=["test:read"], tags=["test"]
            )
            async def test_method(self, context: CapabilityContext) -> str:
                return "test"

        plugin = TestPlugin()
        definitions = plugin.get_capability_definitions()

        assert len(definitions) == 1
        definition = definitions[0]

        assert isinstance(definition, CapabilityDefinition)
        assert definition.id == "test_cap"
        assert definition.name == "Test Capability"
        assert definition.description == "A test capability"
        assert definition.required_scopes == ["test:read"]
        assert definition.tags == ["test"]
        assert definition.plugin_name == plugin.plugin_name

    def test_get_ai_functions_all(self):
        """Test getting all AI functions from plugin."""

        class TestPlugin(Plugin):
            @ai_function(parameters={"type": "object", "properties": {"param": {"type": "string"}}})
            async def ai_method1(self, context: CapabilityContext) -> str:
                return "ai1"

            @ai_function(parameters={"type": "object"})
            async def ai_method2(self, context: CapabilityContext) -> str:
                return "ai2"

            @capability("regular")
            async def regular_method(self, context: CapabilityContext) -> str:
                return "regular"

        plugin = TestPlugin()
        ai_functions = plugin.get_ai_functions()

        assert len(ai_functions) == 2
        ai_names = [f.name for f in ai_functions]
        assert "ai_method1" in ai_names
        assert "ai_method2" in ai_names

        # Check function details
        ai_func1 = next(f for f in ai_functions if f.name == "ai_method1")
        assert ai_func1.parameters["properties"]["param"]["type"] == "string"

    def test_get_ai_functions_specific(self):
        """Test getting specific AI function by capability ID."""

        class TestPlugin(Plugin):
            @ai_function(parameters={"type": "object"})
            async def target_method(self, context: CapabilityContext) -> str:
                return "target"

            @ai_function(parameters={"type": "object"})
            async def other_method(self, context: CapabilityContext) -> str:
                return "other"

        plugin = TestPlugin()
        ai_functions = plugin.get_ai_functions("target_method")

        assert len(ai_functions) == 1
        assert ai_functions[0].name == "target_method"

    def test_configure_plugin(self):
        """Test plugin configuration."""
        plugin = Plugin()
        config = {"setting1": "value1", "setting2": 42}

        plugin.configure(config)

        assert plugin._config == config

    def test_configure_services(self):
        """Test service configuration."""
        plugin = Plugin()
        services = {"llm": Mock(), "database": Mock()}

        plugin.configure_services(services)

        assert plugin._services == services

    @pytest.mark.asyncio
    async def test_get_health_status(self):
        """Test plugin health status."""

        class TestPlugin(Plugin):
            @capability("test")
            async def test_method(self, context: CapabilityContext) -> str:
                return "test"

        plugin = TestPlugin()
        plugin.configure_services({"llm": Mock()})
        plugin.configure({"some": "config"})

        health = await plugin.get_health_status()

        assert health["status"] == "healthy"
        assert health["version"] == "1.0.0"
        assert health["capabilities"] == ["test"]
        assert health["has_llm"] is True
        assert health["configured"] is True

    def test_lifecycle_hooks(self):
        """Test plugin lifecycle hooks."""

        class TestPlugin(Plugin):
            def __init__(self):
                super().__init__()
                self.install_called = False
                self.uninstall_called = False
                self.enable_called = False
                self.disable_called = False

            def on_install(self):
                self.install_called = True

            def on_uninstall(self):
                self.uninstall_called = True

            def on_enable(self):
                self.enable_called = True

            def on_disable(self):
                self.disable_called = True

        plugin = TestPlugin()

        # Test hooks are callable
        plugin.on_install()
        plugin.on_uninstall()
        plugin.on_enable()
        plugin.on_disable()

        assert plugin.install_called is True
        assert plugin.uninstall_called is True
        assert plugin.enable_called is True
        assert plugin.disable_called is True


class TestSimplePlugin:
    """Test SimplePlugin convenience class."""

    def test_extract_task_content_variants(self):
        """Test _extract_task_content with different task structures."""
        plugin = SimplePlugin()

        # Mock task with content attribute
        task_with_content = Mock()
        task_with_content.content = "direct content"
        context1 = Mock(spec=CapabilityContext)
        context1.task = task_with_content

        result = plugin._extract_task_content(context1)
        assert result == "direct content"

        # Mock task with messages
        message = Mock()
        message.content = "message content"
        task_with_messages = Mock()
        task_with_messages.messages = [message]
        # Ensure hasattr works correctly
        del task_with_messages.content  # Remove content attribute
        context2 = Mock(spec=CapabilityContext)
        context2.task = task_with_messages

        result = plugin._extract_task_content(context2)
        assert result == "message content"

        # Mock task with message attribute
        task_with_message = Mock()
        task_with_message.message = "single message"
        # Ensure other attributes don't exist
        del task_with_message.content
        task_with_message.messages = []  # Empty messages
        context3 = Mock(spec=CapabilityContext)
        context3.task = task_with_message

        result = plugin._extract_task_content(context3)
        assert result == "single message"

        # Mock task with no recognized attributes
        basic_task = Mock()
        # Remove all the attributes that would be checked
        del basic_task.content
        basic_task.messages = []
        del basic_task.message
        basic_task.__str__ = lambda self: "string representation"
        context4 = Mock(spec=CapabilityContext)
        context4.task = basic_task

        result = plugin._extract_task_content(context4)
        assert result == "string representation"


class TestAIFunctionPlugin:
    """Test AIFunctionPlugin convenience class."""

    def test_extract_ai_parameters(self):
        """Test _extract_ai_parameters method."""
        plugin = AIFunctionPlugin()

        context = Mock(spec=CapabilityContext)
        context.metadata = {"parameters": {"param1": "value1", "param2": 42}}

        params = plugin._extract_ai_parameters(context)
        assert params == {"param1": "value1", "param2": 42}

        # Test with no parameters
        context.metadata = {}
        params = plugin._extract_ai_parameters(context)
        assert params == {}

    def test_validate_required_params(self):
        """Test _validate_required_params method."""
        plugin = AIFunctionPlugin()

        # All required params present
        params = {"param1": "value1", "param2": "value2", "param3": None}
        required = ["param1", "param2"]
        missing = plugin._validate_required_params(params, required)
        assert missing == []

        # Some params missing
        params = {"param1": "value1"}
        required = ["param1", "param2", "param3"]
        missing = plugin._validate_required_params(params, required)
        assert set(missing) == {"param2", "param3"}

        # Params with None values are considered missing
        params = {"param1": "value1", "param2": None}
        required = ["param1", "param2"]
        missing = plugin._validate_required_params(params, required)
        assert missing == ["param2"]


class TestPluginDiscoveryEdgeCases:
    """Test edge cases in plugin capability discovery."""

    def test_discovery_skips_non_methods(self):
        """Test that discovery only looks at methods, not other attributes."""

        class TestPlugin(Plugin):
            # This should be ignored - it's not a method
            some_attribute = "not a method"

            @capability("valid")
            async def valid_method(self, context: CapabilityContext) -> str:
                return "valid"

        plugin = TestPlugin()
        assert len(plugin._capabilities) == 1
        assert "valid" in plugin._capabilities

    def test_discovery_with_no_capabilities(self):
        """Test plugin with no capability decorators."""

        class EmptyPlugin(Plugin):
            def regular_method(self):
                return "not a capability"

        plugin = EmptyPlugin()
        assert plugin._capabilities == {}

    def test_discovery_logs_validation_errors(self):
        """Test that validation errors are logged during discovery."""
        # Mock the get_plugin_logger to return a mock logger
        mock_logger = Mock()
        with patch("src.agent.plugins.base.get_plugin_logger", return_value=mock_logger):

            class TestPlugin(Plugin):
                @capability("", name="Invalid")  # Empty ID
                async def invalid_method(self, context: CapabilityContext) -> str:
                    return "invalid"

            plugin = TestPlugin()

            # Should have called logger.error
            mock_logger.error.assert_called_once()
            args, kwargs = mock_logger.error.call_args
            assert args[0] == "Invalid capability"
            assert kwargs["capability_id"] == ""
            assert "errors" in kwargs
            assert "" not in plugin._capabilities
