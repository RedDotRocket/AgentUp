import pytest

from src.agent.plugins import PluginManager, SkillContext, SkillInfo, SkillResult
from src.agent.plugins.example_plugin import ExamplePlugin
from tests.utils.plugin_testing import MockTask, create_test_plugin


class TestPluginSystem:
    """Test the plugin system functionality."""

    def test_plugin_manager_creation(self):
        """Test that plugin manager can be created."""
        manager = PluginManager()
        assert manager is not None
        assert hasattr(manager, "pm")
        assert hasattr(manager, "plugins")
        assert hasattr(manager, "skills")

    def test_example_plugin_registration(self):
        """Test that the example plugin registers correctly."""
        plugin = ExamplePlugin()
        skill_info = plugin.register_skill()

        assert isinstance(skill_info, SkillInfo)
        assert skill_info.id == "example"
        assert skill_info.name == "Example Skill"
        assert "text" in [cap.value for cap in skill_info.capabilities]
        assert "ai_function" in [cap.value for cap in skill_info.capabilities]

    def test_example_plugin_execution(self):
        """Test that the example plugin can execute."""
        plugin = ExamplePlugin()

        # Create test context
        task = MockTask("Hello, world!")
        context = SkillContext(task=task)

        # Execute skill
        result = plugin.execute_skill(context)

        assert isinstance(result, SkillResult)
        assert result.success
        assert "Hello, you said: Hello, world!" in result.content

    def test_example_plugin_routing(self):
        """Test that the example plugin routing works."""
        plugin = ExamplePlugin()

        # Test with matching keywords
        task1 = MockTask("This is an example test")
        context1 = SkillContext(task=task1)
        confidence1 = plugin.can_handle_task(context1)
        assert confidence1 > 0

        # Test without matching keywords
        task2 = MockTask("Unrelated content")
        context2 = SkillContext(task=task2)
        confidence2 = plugin.can_handle_task(context2)
        assert confidence2 == 0

    def test_example_plugin_ai_functions(self):
        """Test that the example plugin provides AI functions."""
        plugin = ExamplePlugin()
        ai_functions = plugin.get_ai_functions()

        assert len(ai_functions) == 2
        assert any(f.name == "greet_user" for f in ai_functions)
        assert any(f.name == "echo_message" for f in ai_functions)

    def test_plugin_manager_skill_registration(self):
        """Test registering a skill with the plugin manager."""
        manager = PluginManager()

        # Create and register a test plugin
        TestPlugin = create_test_plugin("test_skill", "Test Skill")
        plugin = TestPlugin()

        # Manually register the plugin properly
        manager.pm.register(plugin, name="test_plugin")

        # Get skill info directly and store it
        skill_info = plugin.register_skill()
        manager.skills[skill_info.id] = skill_info
        manager.skill_to_plugin[skill_info.id] = "test_plugin"
        manager.skill_hooks[skill_info.id] = plugin

        # Check skill was registered
        assert "test_skill" in manager.skills
        skill = manager.get_skill("test_skill")
        assert skill is not None
        assert skill.name == "Test Skill"

    def test_plugin_manager_execution(self):
        """Test executing a skill through the plugin manager."""
        manager = PluginManager()

        # Register example plugin
        plugin = ExamplePlugin()
        manager.pm.register(plugin, name="example_plugin")
        manager._register_plugin_skill("example_plugin", plugin)

        # Execute skill
        task = MockTask("Test input")
        context = SkillContext(task=task)
        result = manager.execute_skill("example", context)

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
        manager._register_plugin_skill("example_plugin", plugin)

        adapter = PluginAdapter(manager)

        # Test listing skills
        skills = adapter.list_available_skills()
        assert "example" in skills

        # Test getting skill info
        info = adapter.get_skill_info("example")
        assert info["skill_id"] == "example"
        assert info["name"] == "Example Skill"

    @pytest.mark.asyncio
    async def test_plugin_async_execution(self):
        """Test async plugin execution."""
        from tests.utils.plugin_testing import test_plugin_async

        plugin = ExamplePlugin()
        results = await test_plugin_async(plugin)

        assert results["registration"]["success"]
        assert results["registration"]["skill_id"] == "example"

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
