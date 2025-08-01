import pytest

from agent.plugins import CapabilityContext, CapabilityDefinition, CapabilityResult, PluginRegistry
from agent.plugins.example_plugin import ExamplePlugin
from tests.utils.plugin_testing import MockTask, create_test_plugin


class TestPluginSystem:
    def test_plugin_manager_creation(self):
        manager = PluginRegistry()
        assert manager is not None
        assert hasattr(manager, "plugins")
        assert hasattr(manager, "capabilities")
        assert hasattr(manager, "plugin_definitions")
        assert hasattr(manager, "capability_to_plugin")

    def test_example_plugin_registration(self):
        plugin = ExamplePlugin()
        capability_info = plugin.register_capability()

        assert isinstance(capability_info, CapabilityDefinition)
        assert capability_info.id == "example"
        assert capability_info.name == "Example Capability"
        # Check that the capability has ai_function support
        assert capability_info.capabilities is not None

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
        confidence1 = plugin.can_handle_task("example", context1)
        assert confidence1 > 0

        # Test without matching keywords
        mock_task2 = MockTask("Unrelated content")
        context2 = CapabilityContext(task=mock_task2._task)
        confidence2 = plugin.can_handle_task("example", context2)
        assert confidence2 == 0

    def test_example_plugin_ai_functions(self):
        plugin = ExamplePlugin()
        ai_functions = plugin.get_ai_functions()

        assert len(ai_functions) == 2
        assert any(f.name == "greet_user" for f in ai_functions)
        assert any(f.name == "echo_message" for f in ai_functions)

    def test_plugin_manager_capability_registration(self):
        manager = PluginRegistry()

        # Create and register a test plugin
        TestPlugin = create_test_plugin("test_capability", "Test Skill")
        plugin = TestPlugin()

        # Register the plugin using the new system
        manager._register_plugin("test_plugin", plugin)

        # Check capability was registered
        capability = manager.get_capability("test_capability")
        assert capability is not None
        assert capability.name == "Test Skill"
        assert "test_capability" in manager.capabilities

    def test_plugin_manager_execution(self):
        manager = PluginRegistry()

        # Register example plugin
        plugin = ExamplePlugin()
        manager._register_plugin("example_plugin", plugin)

        # Execute capability
        mock_task = MockTask("Test input")
        context = CapabilityContext(task=mock_task._task)

        # The execute_capability is async in PluginRegistry
        import asyncio

        result = asyncio.run(manager.execute_capability("example", context))

        assert result.success
        assert result.content

    def test_plugin_adapter_integration(self):
        from agent.plugins.adapter import PluginAdapter

        # Create adapter with a manager
        manager = PluginRegistry()

        # Register example plugin
        plugin = ExamplePlugin()
        manager._register_plugin("example_plugin", plugin)

        from agent.config.settings import Settings

        config = Settings()
        adapter = PluginAdapter(config, plugin_registry=manager)

        # Test listing capabilities
        capabilities = adapter.list_available_capabilities()
        assert "example" in capabilities

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

        # get_health_status is async
        import asyncio

        health = asyncio.run(plugin.get_health_status())

        assert health["status"] == "healthy"
        assert "version" in health
        assert health["has_llm"] is False  # No LLM configured in test
