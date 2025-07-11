import pytest

from agent.plugins import CapabilityContext, CapabilityInfo, CapabilityResult, PluginManager
from agent.plugins.example_plugin import ExamplePlugin
from tests.utils.plugin_testing import MockTask, create_test_plugin


class TestPluginSystem:
    """Test the plugin system functionality."""

    def test_plugin_manager_creation(self):
        """Test that plugin manager can be created."""
        manager = PluginManager()
        assert manager is not None
        assert hasattr(manager, "pm")
        assert hasattr(manager, "plugins")
        assert hasattr(manager, "capabilities")

    def test_example_plugin_registration(self):
        """Test that the example plugin registers correctly."""
        plugin = ExamplePlugin()
        capability_info = plugin.register_capability()

        assert isinstance(capability_info, CapabilityInfo)
        assert capability_info.id == "example"
        assert capability_info.name == "Example Capability"
        assert "text" in [cap.value for cap in capability_info.capabilities]
        assert "ai_function" in [cap.value for cap in capability_info.capabilities]

    def test_example_plugin_execution(self):
        """Test that the example plugin can execute."""
        plugin = ExamplePlugin()

        # Create test context
        task = MockTask("Hello, world!")
        context = CapabilityContext(task=task)

        # Execute capability
        result = plugin.execute_capability(context)

        assert isinstance(result, CapabilityResult)
        assert result.success
        assert "Hello, you said: Hello, world!" in result.content

    def test_example_plugin_routing(self):
        """Test that the example plugin routing works."""
        plugin = ExamplePlugin()

        # Test with matching keywords
        task1 = MockTask("This is an example test")
        context1 = CapabilityContext(task=task1)
        confidence1 = plugin.can_handle_task(context1)
        assert confidence1 > 0

        # Test without matching keywords
        task2 = MockTask("Unrelated content")
        context2 = CapabilityContext(task=task2)
        confidence2 = plugin.can_handle_task(context2)
        assert confidence2 == 0

    def test_example_plugin_ai_functions(self):
        """Test that the example plugin provides AI functions."""
        plugin = ExamplePlugin()
        ai_functions = plugin.get_ai_functions()

        assert len(ai_functions) == 2
        assert any(f.name == "greet_user" for f in ai_functions)
        assert any(f.name == "echo_message" for f in ai_functions)

    def test_plugin_manager_capability_registration(self):
        """Test registering a capability with the plugin manager."""
        manager = PluginManager()

        # Create and register a test plugin
        TestPlugin = create_test_plugin("test_capability", "Test Skill")
        plugin = TestPlugin()

        # Manually register the plugin properly
        manager.pm.register(plugin, name="test_plugin")

        # Get capability info directly and store it
        capability_info = plugin.register_capability()
        manager.capabilities[capability_info.id] = capability_info
        manager.capability_to_plugin[capability_info.id] = "test_plugin"
        manager.capability_hooks[capability_info.id] = plugin

        # Check capability was registered
        assert "test_capability" in manager.capabilities
        capability = manager.get_capability("test_capability")
        assert capability is not None
        assert capability.name == "Test Skill"

    def test_plugin_manager_execution(self):
        """Test executing a capability through the plugin manager."""
        manager = PluginManager()

        # Register example plugin
        plugin = ExamplePlugin()
        manager.pm.register(plugin, name="example_plugin")
        manager._register_plugin_capability("example_plugin", plugin)

        # Execute capability
        task = MockTask("Test input")
        context = CapabilityContext(task=task)
        result = manager.execute_capability("example", context)

        assert result.success
        assert result.content

    def test_plugin_adapter_integration(self):
        """Test the plugin adapter integration."""
        from src.agent.plugins.adapter import PluginAdapter

        # Create adapter with a manager
        manager = PluginManager()

        # Register example plugin
        plugin = ExamplePlugin()
        manager.pm.register(plugin, name="example_plugin")
        manager._register_plugin_capability("example_plugin", plugin)

        adapter = PluginAdapter(manager)

        # Test listing capabilitys
        capabilitys = adapter.list_available_capabilities()
        assert "example" in capabilitys

        # Test getting capability info
        info = adapter.get_capability_info("example")
        assert info["capability_id"] == "example"
        assert info["name"] == "Example Capability"

    @pytest.mark.asyncio
    async def test_plugin_async_execution(self):
        """Test async plugin execution."""
        from tests.utils.plugin_testing import test_plugin_async

        plugin = ExamplePlugin()
        results = await test_plugin_async(plugin)

        assert results["registration"]["success"]
        assert results["registration"]["capability_id"] == "example"

        # Check execution results
        assert len(results["execution"]) > 0
        for exec_result in results["execution"]:
            assert "success" in exec_result

    def test_plugin_validation(self):
        """Test plugin configuration validation."""
        plugin = ExamplePlugin()

        # Test valid config
        valid_result = plugin.validate_config({"greeting": "Hi", "excited": True})
        assert valid_result.valid
        assert len(valid_result.errors) == 0

        # Test invalid config
        invalid_result = plugin.validate_config({"greeting": "A" * 100})  # Too long
        assert not invalid_result.valid
        assert len(invalid_result.errors) > 0

    def test_plugin_middleware_config(self):
        """Test plugin middleware configuration."""
        plugin = ExamplePlugin()
        middleware = plugin.get_middleware_config()

        assert isinstance(middleware, list)
        assert any(m["type"] == "rate_limit" for m in middleware)
        assert any(m["type"] == "logging" for m in middleware)

    def test_plugin_health_status(self):
        """Test plugin health status reporting."""
        plugin = ExamplePlugin()
        health = plugin.get_health_status()

        assert health["status"] == "healthy"
        assert "version" in health
        assert health["has_llm"] is False  # No LLM configured in test
