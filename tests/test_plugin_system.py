import pytest

from agent.plugins import CapabilityContext, CapabilityResult, PluginDefinition, PluginManager
from agent.plugins.example_plugin import ExamplePlugin
from tests.utils.plugin_testing import MockTask, create_test_plugin


class TestPluginSystem:
    def test_plugin_manager_creation(self):
        manager = PluginManager()
        assert manager is not None
        assert hasattr(manager, "pm")
        assert hasattr(manager, "plugins")
        assert hasattr(manager, "capabilities")

    def test_example_plugin_registration(self):
        plugin = ExamplePlugin()
        capability_info = plugin.register_capability()

        assert isinstance(capability_info, PluginDefinition)
        assert capability_info.id == "example"
        assert capability_info.name == "Example Capability"
        assert "text" in [cap.value for cap in capability_info.capabilities]
        assert "ai_function" in [cap.value for cap in capability_info.capabilities]

    def test_example_plugin_execution(self):
        plugin = ExamplePlugin()

        # Create test context
        mock_task = MockTask("Hello, world!")
        context = CapabilityContext(task=mock_task._task)

        # Execute capability
        result = plugin.execute_capability(context)

        assert isinstance(result, CapabilityResult)
        assert result.success
        assert "Hello, you said: Hello, world!" in result.content

    def test_example_plugin_routing(self):
        plugin = ExamplePlugin()

        # Test with matching keywords
        mock_task1 = MockTask("This is an example test")
        context1 = CapabilityContext(task=mock_task1._task)
        confidence1 = plugin.can_handle_task(context1)
        assert confidence1 > 0

        # Test without matching keywords
        mock_task2 = MockTask("Unrelated content")
        context2 = CapabilityContext(task=mock_task2._task)
        confidence2 = plugin.can_handle_task(context2)
        assert confidence2 == 0

    def test_example_plugin_ai_functions(self):
        plugin = ExamplePlugin()
        ai_functions = plugin.get_ai_functions()

        assert len(ai_functions) == 2
        assert any(f.name == "greet_user" for f in ai_functions)
        assert any(f.name == "echo_message" for f in ai_functions)

    def test_plugin_manager_capability_registration(self):
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
        manager = PluginManager()

        # Register example plugin
        plugin = ExamplePlugin()
        manager.pm.register(plugin, name="example_plugin")
        manager._register_plugin_capability("example_plugin", plugin)

        # Execute capability
        mock_task = MockTask("Test input")
        context = CapabilityContext(task=mock_task._task)
        result = manager.execute_capability("example", context)

        assert result.success
        assert result.content

    def test_plugin_adapter_integration(self):
        from src.agent.plugins.adapter import PluginAdapter

        # Create adapter with a manager
        manager = PluginManager()

        # Register example plugin
        plugin = ExamplePlugin()
        manager.pm.register(plugin, name="example_plugin")
        manager._register_plugin_capability("example_plugin", plugin)

        from src.agent.config.settings import Settings

        config = Settings()
        adapter = PluginAdapter(config, plugin_manager=manager)

        # Test listing capabilitys
        capabilitys = adapter.list_available_capabilities()
        assert "example" in capabilitys

        # Test getting capability info
        info = adapter.get_capability_info("example")
        assert info["capability_id"] == "example"
        assert info["name"] == "Example Capability"

    @pytest.mark.asyncio
    async def test_plugin_async_execution(self):
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
        plugin = ExamplePlugin()
        middleware = plugin.get_middleware_config()

        assert isinstance(middleware, list)
        assert any(m["type"] == "rate_limit" for m in middleware)
        assert any(m["type"] == "logging" for m in middleware)

    def test_plugin_health_status(self):
        plugin = ExamplePlugin()
        health = plugin.get_health_status()

        assert health["status"] == "healthy"
        assert "version" in health
        assert health["has_llm"] is False  # No LLM configured in test
