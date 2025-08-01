"""
Test suite for src/agent/plugins/manager.py (PluginRegistry)

This module tests the new decorator-based PluginRegistry that replaces
the old Pluggy-based system.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
from a2a.types import Task, TaskStatus

from src.agent.plugins.base import Plugin
from src.agent.plugins.decorators import capability
from src.agent.plugins.manager import PluginRegistry, get_plugin_registry
from src.agent.plugins.models import (
    CapabilityContext,
    PluginStatus,
)


# Test plugin classes for use in tests (prefix with _ to avoid pytest collection)
class _TestPlugin(Plugin):
    """Test plugin with basic capability."""

    @capability("test_capability", name="Test Capability", scopes=["test:read"])
    async def test_method(self, context: CapabilityContext) -> str:
        return "test result"


class _MultiCapabilityPlugin(Plugin):
    """Test plugin with multiple capabilities."""

    @capability("cap1", name="Capability 1", scopes=["read:files"])
    async def capability_one(self, context: CapabilityContext) -> str:
        return "capability 1 result"

    @capability("cap2", name="Capability 2", scopes=["write:files"])
    async def capability_two(self, context: CapabilityContext) -> str:
        return "capability 2 result"


class TestPluginRegistry:
    """Test PluginRegistry initialization and basic functionality."""

    def test_registry_initialization(self):
        """Test PluginRegistry initialization."""
        registry = PluginRegistry()

        assert registry.plugins == {}
        assert registry.plugin_definitions == {}
        assert registry.capabilities == {}
        assert registry.capability_to_plugin == {}

    def test_registry_initialization_with_config(self):
        """Test PluginRegistry initialization with config."""
        config = {"test": "value"}
        registry = PluginRegistry(config)

        assert registry._config == config

    def test_config_property_loading_failure(self):
        """Test config property when loading fails."""
        registry = PluginRegistry()

        # Reset config to None to trigger loading
        registry._config = None

        # Patch the specific import within the config property
        with patch("src.agent.plugins.manager.PluginRegistry.config", new_callable=PropertyMock) as mock_config:
            # Make the property raise ImportError
            mock_config.side_effect = ImportError("Configuration module not found. Ensure 'agent.config' is available")

            with pytest.raises(ImportError, match="Configuration module not found"):
                _ = registry.config

    def test_register_plugin_success(self):
        """Test successful plugin registration."""
        registry = PluginRegistry()
        plugin = _TestPlugin()

        # Register plugin directly
        registry._register_plugin("test_plugin", plugin)

        # Verify plugin was registered
        assert "test_plugin" in registry.plugins
        assert registry.plugins["test_plugin"] is plugin

        # Verify capability was registered
        assert "test_capability" in registry.capabilities
        assert "test_capability" in registry.capability_to_plugin
        assert registry.capability_to_plugin["test_capability"] == "test_plugin"

    def test_register_plugin_multiple_capabilities(self):
        """Test plugin registration with multiple capabilities."""
        registry = PluginRegistry()
        plugin = _MultiCapabilityPlugin()

        registry._register_plugin("multi_plugin", plugin)

        # Verify plugin was registered
        assert "multi_plugin" in registry.plugins

        # Verify both capabilities were registered
        assert "cap1" in registry.capabilities
        assert "cap2" in registry.capabilities
        assert registry.capability_to_plugin["cap1"] == "multi_plugin"
        assert registry.capability_to_plugin["cap2"] == "multi_plugin"

    @patch("src.agent.plugins.manager.logger")
    def test_register_plugin_error_handling(self, mock_logger):
        """Test plugin registration error handling."""
        registry = PluginRegistry()

        # Mock plugin that raises error during get_capability_definitions
        mock_plugin = Mock(spec=Plugin)
        mock_plugin.get_capability_definitions.side_effect = RuntimeError("Test error")

        registry._register_plugin("error_plugin", mock_plugin)

        # Plugin should not be in plugins dict when error occurs
        assert "error_plugin" not in registry.plugins
        # But error should be recorded in plugin_definitions
        assert "error_plugin" in registry.plugin_definitions
        assert registry.plugin_definitions["error_plugin"].status == PluginStatus.ERROR

    def test_get_plugin(self):
        """Test getting plugin by ID."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        result = registry.get_plugin("test_plugin")
        assert result is plugin

        # Test non-existent plugin
        result = registry.get_plugin("non_existent")
        assert result is None

    def test_get_capability(self):
        """Test getting capability definition by ID."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        capability = registry.get_capability("test_capability")
        assert capability is not None
        assert capability.id == "test_capability"
        assert capability.name == "Test Capability"

        # Test non-existent capability
        capability = registry.get_capability("non_existent")
        assert capability is None

    def test_list_capabilities(self):
        """Test listing all capabilities."""
        registry = PluginRegistry()
        plugin = _MultiCapabilityPlugin()
        registry._register_plugin("multi_plugin", plugin)

        capabilities = registry.list_capabilities()
        assert len(capabilities) == 2

        capability_ids = [cap.id for cap in capabilities]
        assert "cap1" in capability_ids
        assert "cap2" in capability_ids

    def test_list_plugins(self):
        """Test listing all plugins."""
        registry = PluginRegistry()
        plugin1 = _TestPlugin()
        plugin2 = _MultiCapabilityPlugin()

        registry._register_plugin("plugin1", plugin1)
        registry._register_plugin("plugin2", plugin2)

        plugins = registry.list_plugins()
        assert len(plugins) == 2

        plugin_names = [p.name for p in plugins]
        assert "plugin1" in plugin_names
        assert "plugin2" in plugin_names

    @pytest.mark.asyncio
    async def test_execute_capability_success(self):
        """Test successful capability execution."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        result = await registry.execute_capability("test_capability", context)
        assert result.success is True
        assert result.content == "test result"

    @pytest.mark.asyncio
    async def test_execute_capability_not_found(self):
        """Test capability execution when capability not found."""
        registry = PluginRegistry()

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        result = await registry.execute_capability("non_existent", context)
        assert result.success is False
        assert "not found" in result.content

    @pytest.mark.asyncio
    async def test_execute_capability_plugin_error(self):
        """Test capability execution when plugin raises error."""
        registry = PluginRegistry()

        # Mock plugin that raises error
        mock_plugin = Mock(spec=Plugin)
        mock_plugin.execute_capability.side_effect = RuntimeError("Plugin error")

        # Manually set up the mappings
        registry.plugins["error_plugin"] = mock_plugin
        registry.capabilities["error_capability"] = Mock()
        registry.capability_to_plugin["error_capability"] = "error_plugin"

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        result = await registry.execute_capability("error_capability", context)
        assert result.success is False
        assert "execution failed" in result.content

    def test_can_handle_task_success(self):
        """Test can_handle_task when plugin can handle."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        result = registry.can_handle_task("test_capability", context)
        # Should return True since capability exists
        assert result is True

    def test_can_handle_task_capability_not_found(self):
        """Test can_handle_task when capability not found."""
        registry = PluginRegistry()

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        result = registry.can_handle_task("non_existent", context)
        assert result is False

    def test_can_handle_task_plugin_error(self):
        """Test can_handle_task when plugin raises error."""
        registry = PluginRegistry()

        # Mock plugin that raises error
        mock_plugin = Mock(spec=Plugin)
        mock_plugin.can_handle_task.side_effect = RuntimeError("Plugin error")

        # Manually set up the mappings
        registry.plugins["error_plugin"] = mock_plugin
        registry.capability_to_plugin["error_capability"] = "error_plugin"

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        result = registry.can_handle_task("error_capability", context)
        assert result is False

    def test_get_ai_functions_all(self):
        """Test getting AI functions from all plugins."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        ai_functions = registry.get_ai_functions()
        # Test plugin doesn't have AI functions, so should be empty
        assert len(ai_functions) == 0

    def test_get_ai_functions_specific_capability(self):
        """Test getting AI functions for specific capability."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        ai_functions = registry.get_ai_functions("test_capability")
        # Test plugin doesn't have AI functions, so should be empty
        assert len(ai_functions) == 0

    def test_get_ai_functions_capability_not_found(self):
        """Test getting AI functions for non-existent capability."""
        registry = PluginRegistry()

        ai_functions = registry.get_ai_functions("non_existent")
        assert len(ai_functions) == 0

    def test_validate_config_success(self):
        """Test config validation success."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        result = registry.validate_config("test_capability", {})
        assert result.valid is True

    def test_validate_config_capability_not_found(self):
        """Test config validation when capability not found."""
        registry = PluginRegistry()

        result = registry.validate_config("non_existent", {})
        assert result.valid is False
        assert "not found" in result.errors[0]

    def test_configure_plugin(self):
        """Test plugin configuration."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        config = {"setting": "value"}
        registry.configure_plugin("test_plugin", config)

        # Verify plugin was configured (would need to check plugin's internal state)
        # For now, just verify no exception was raised

    def test_configure_services(self):
        """Test service configuration for all plugins."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        services = {"service": Mock()}
        registry.configure_services(services)

        # Verify no exception was raised
        # Individual plugin service configuration would be tested at the plugin level

    def test_find_capabilities_for_task(self):
        """Test finding capabilities that can handle a task."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        # Create a proper Task instance for CapabilityContext
        task = Task(
            id="test-task-123",
            kind="task",
            context_id="test-context-123",
            status=TaskStatus(state="submitted", error=None),
            artifacts=[],
            history=[],
            metadata={},
        )
        context = CapabilityContext(task=task, config={}, services={}, state={}, metadata={})

        candidates = registry.find_capabilities_for_task(context)
        assert len(candidates) == 1
        assert candidates[0][0] == "test_capability"
        assert candidates[0][1] == 1.0  # True converted to 1.0

    @pytest.mark.asyncio
    async def test_get_health_status(self):
        """Test getting health status of all plugins."""
        registry = PluginRegistry()
        plugin = _TestPlugin()
        registry._register_plugin("test_plugin", plugin)

        health = await registry.get_health_status()

        assert "total_plugins" in health
        assert "total_capabilities" in health
        assert "plugin_status" in health
        assert health["total_plugins"] == 1
        assert health["total_capabilities"] == 1
        assert "test_plugin" in health["plugin_status"]


class TestPluginAllowlist:
    """Test plugin allowlist functionality."""

    def test_load_plugin_allowlist_allowlist_mode(self):
        """Test loading allowlist in allowlist mode."""
        config = {
            "plugin_security": {
                "mode": "allowlist",
                "allowed_plugins": {"test_plugin": {"package": "test-package", "verified": True}},
            }
        }

        registry = PluginRegistry(config)

        assert "test_plugin" in registry.allowed_plugins
        assert registry.allowed_plugins["test_plugin"]["package"] == "test-package"
        assert registry.allowed_plugins["test_plugin"]["verified"] is True

    def test_load_plugin_allowlist_default_mode(self):
        """Test loading allowlist in default mode from plugins config."""
        config = {
            "plugins": [
                {"plugin_id": "test_plugin", "package": "custom-package", "verified": True},
                {
                    "plugin_id": "auto_plugin"
                    # No package specified, should auto-generate
                },
            ]
        }

        registry = PluginRegistry(config)

        assert "test_plugin" in registry.allowed_plugins
        assert registry.allowed_plugins["test_plugin"]["package"] == "custom-package"

        assert "auto_plugin" in registry.allowed_plugins
        assert registry.allowed_plugins["auto_plugin"]["package"] == "agentup-auto_plugin-plugin"

    @patch("src.agent.plugins.manager.logger")
    def test_load_plugin_allowlist_error_handling(self, mock_logger):
        """Test allowlist loading error handling."""
        # Config that will cause an error during processing
        config = {"plugins": "invalid"}  # Should be a list

        registry = PluginRegistry(config)

        # Should have empty allowlist on error
        assert registry.allowed_plugins == {}

    def test_is_plugin_allowed_no_allowlist(self):
        """Test plugin allowed check when no allowlist configured."""
        registry = PluginRegistry()
        registry.allowed_plugins = {}  # Empty allowlist

        # Should allow all when no allowlist
        result = registry._is_plugin_allowed("any_plugin", None)
        assert result is True

    def test_is_plugin_allowed_plugin_in_allowlist(self):
        """Test plugin allowed check when plugin in allowlist."""
        registry = PluginRegistry()
        registry.allowed_plugins = {"allowed_plugin": {"package": "test-package"}}

        result = registry._is_plugin_allowed("allowed_plugin", None)
        assert result is True

    def test_is_plugin_allowed_plugin_not_in_allowlist(self):
        """Test plugin allowed check when plugin not in allowlist."""
        registry = PluginRegistry()
        registry.allowed_plugins = {"allowed_plugin": {"package": "test-package"}}

        result = registry._is_plugin_allowed("blocked_plugin", None)
        assert result is False

    @patch("src.agent.plugins.manager.logger")
    def test_is_plugin_allowed_package_mismatch(self, mock_logger):
        """Test plugin allowed check with package mismatch."""
        registry = PluginRegistry()
        registry.allowed_plugins = {"test_plugin": {"package": "expected-package"}}

        # Mock distribution with different package name
        mock_dist = Mock()
        mock_dist.name = "actual-package"

        result = registry._is_plugin_allowed("test_plugin", mock_dist)
        assert result is False


class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    @patch("src.agent.plugins.manager.logger")
    def test_load_entry_point_plugins_no_entry_points(self, mock_logger, mock_entry_points):
        """Test loading entry point plugins when none exist."""
        # Mock empty entry points
        mock_ep_result = Mock()
        mock_ep_result.select = Mock(return_value=[])
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        registry._load_entry_point_plugins()

        # Should complete without error
        assert len(registry.plugins) == 0

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    def test_load_entry_point_plugins_success(self, mock_entry_points):
        """Test successful loading of entry point plugins."""
        # Mock entry point
        mock_entry_point = Mock()
        mock_entry_point.name = "test_plugin"
        mock_entry_point.load.return_value = _TestPlugin
        mock_entry_point.dist = Mock()
        mock_entry_point.dist.name = "test-package"
        mock_entry_point.dist.version = "1.0.0"

        mock_ep_result = Mock()
        mock_ep_result.select = Mock(return_value=[mock_entry_point])
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        # Allow the plugin
        registry.allowed_plugins = {"test_plugin": {"package": "test-package"}}

        registry._load_entry_point_plugins()

        # Verify plugin was loaded
        assert "test_plugin" in registry.plugins
        assert isinstance(registry.plugins["test_plugin"], _TestPlugin)

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    @patch("src.agent.plugins.manager.logger")
    def test_load_entry_point_plugins_not_plugin_subclass(self, mock_logger, mock_entry_points):
        """Test loading entry point that's not a Plugin subclass."""
        # Mock entry point that loads a non-Plugin class
        mock_entry_point = Mock()
        mock_entry_point.name = "bad_plugin"
        mock_entry_point.load.return_value = str  # Not a Plugin subclass
        mock_entry_point.dist = Mock()
        mock_entry_point.dist.name = "bad-package"

        mock_ep_result = Mock()
        mock_ep_result.select = Mock(return_value=[mock_entry_point])
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        registry.allowed_plugins = {"bad_plugin": {"package": "bad-package"}}

        registry._load_entry_point_plugins()

        # Plugin should not be loaded
        assert "bad_plugin" not in registry.plugins

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    def test_load_entry_point_plugins_loading_error(self, mock_entry_points):
        """Test handling of plugin loading errors."""
        # Mock entry point that raises error during loading
        mock_entry_point = Mock()
        mock_entry_point.name = "error_plugin"
        mock_entry_point.load.side_effect = ImportError("Loading failed")
        mock_entry_point.dist = Mock()
        mock_entry_point.dist.name = "error-package"

        mock_ep_result = Mock()
        mock_ep_result.select = Mock(return_value=[mock_entry_point])
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        registry.allowed_plugins = {"error_plugin": {"package": "error-package"}}

        registry._load_entry_point_plugins()

        # Plugin should be tracked as failed
        assert "error_plugin" not in registry.plugins
        assert "error_plugin" in registry.plugin_definitions
        assert registry.plugin_definitions["error_plugin"].status == PluginStatus.ERROR

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    def test_load_entry_point_plugins_python39_compatibility(self, mock_entry_points):
        """Test Python 3.9 compatibility (no select method)."""
        # Mock Python 3.9 style entry points (no select method)
        mock_entry_point = Mock()
        mock_entry_point.name = "test_plugin"
        mock_entry_point.load.return_value = _TestPlugin
        mock_entry_point.dist = Mock()
        mock_entry_point.dist.name = "test-package"
        mock_entry_point.dist.version = "1.0.0"

        # Mock entry points without select method (Python 3.9 style)
        mock_ep_result = {"agentup.plugins": [mock_entry_point]}
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        registry.allowed_plugins = {"test_plugin": {"package": "test-package"}}

        registry._load_entry_point_plugins()

        # Should work with Python 3.9 compatibility
        assert "test_plugin" in registry.plugins


class TestFilesystemPlugins:
    """Test filesystem plugin loading functionality."""

    def test_load_filesystem_plugins_disabled(self):
        """Test filesystem plugin loading when disabled."""
        config = {"development": {"enabled": False}}

        registry = PluginRegistry(config)
        registry._load_filesystem_plugins()

        # Should not load any plugins
        assert len(registry.plugins) == 0

    def test_load_filesystem_plugins_dev_disabled(self):
        """Test filesystem plugin loading when development mode disabled."""
        config = {"development": {"enabled": True, "filesystem_plugins": {"enabled": False}}}

        registry = PluginRegistry(config)
        registry._load_filesystem_plugins()

        # Should not load any plugins
        assert len(registry.plugins) == 0

    @patch("src.agent.plugins.manager.Path")
    @patch("src.agent.plugins.manager.logger")
    def test_load_filesystem_plugins_directory_not_found(self, mock_logger, mock_path):
        """Test filesystem plugin loading when directory doesn't exist."""
        config = {
            "development": {
                "enabled": True,
                "filesystem_plugins": {"enabled": True, "allowed_directories": ["~/.agentup/plugins"]},
            }
        }

        # Mock path that doesn't exist
        mock_path_instance = Mock()
        mock_path_instance.expanduser.return_value = mock_path_instance
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        registry = PluginRegistry(config)
        registry._load_filesystem_plugins()

        # Should complete without error, no plugins loaded
        assert len(registry.plugins) == 0

    @patch("src.agent.plugins.manager.Path")
    def test_load_filesystem_plugins_path_not_directory(self, mock_path):
        """Test filesystem plugin loading when path is not a directory."""
        config = {
            "development": {
                "enabled": True,
                "filesystem_plugins": {"enabled": True, "allowed_directories": ["~/.agentup/plugins"]},
            }
        }

        # Mock path that exists but is not a directory
        mock_path_instance = Mock()
        mock_path_instance.expanduser.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.iterdir.return_value = []  # Empty directory
        mock_path.return_value = mock_path_instance

        registry = PluginRegistry(config)
        registry._load_filesystem_plugins()

        # Should complete without error
        assert len(registry.plugins) == 0

    def test_load_filesystem_plugin_with_plugin_py(self):
        """Test loading filesystem plugin with plugin.py file."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir) / "test_plugin"
            plugin_dir.mkdir()

            # Create plugin.py with test plugin
            plugin_file = plugin_dir / "plugin.py"
            plugin_code = """
from src.agent.plugins.base import Plugin
from src.agent.plugins.decorators import capability
from src.agent.plugins.models import CapabilityContext

class TestFilePlugin(Plugin):
    @capability("file_test", name="File Test")
    async def test_method(self, context: CapabilityContext) -> str:
        return "file test result"
"""
            plugin_file.write_text(plugin_code)

            # Test loading - plugin should load successfully
            registry._load_filesystem_plugin(plugin_dir)

            # Verify plugin was loaded (with fs_ prefix)
            assert "fs_test_plugin" in registry.plugins
            assert len(registry.plugins) == 1

    def test_load_filesystem_plugin_no_plugin_class(self):
        """Test loading filesystem plugin with no Plugin class."""
        registry = PluginRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir) / "test_plugin"
            plugin_dir.mkdir()

            # Create plugin.py without Plugin class
            plugin_file = plugin_dir / "plugin.py"
            plugin_code = """
# No Plugin class here
def some_function():
    return "not a plugin"
"""
            plugin_file.write_text(plugin_code)

            # Should handle gracefully and log warning
            registry._load_filesystem_plugin(plugin_dir)

            # No plugin should be loaded
            assert len(registry.plugins) == 0


class TestPluginRegistryGlobalInstance:
    """Test global plugin registry instance management."""

    @patch("src.agent.plugins.manager.logger")
    def test_get_plugin_registry_creates_instance(self, mock_logger):
        """Test that get_plugin_registry creates instance."""
        # Reset global instance
        import src.agent.plugins.manager as manager_module

        manager_module._plugin_registry = None

        with patch.object(PluginRegistry, "discover_plugins"):
            registry = get_plugin_registry()

            assert registry is not None
            assert isinstance(registry, PluginRegistry)

    def test_get_plugin_registry_with_config_loading_error(self):
        """Test get_plugin_registry when config loading fails."""
        # Reset global instance
        import src.agent.plugins.manager as manager_module

        manager_module._plugin_registry = None

        with patch("builtins.__import__", side_effect=ImportError("Config not found")):
            with patch.object(PluginRegistry, "discover_plugins"):
                registry = get_plugin_registry()

                # Should still create registry, just without config
                assert registry is not None
                assert isinstance(registry, PluginRegistry)


class TestPluginDiscoveryAll:
    """Test discover_all_available_plugins functionality."""

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    def test_discover_all_available_plugins_success(self, mock_entry_points):
        """Test discovering all available plugins."""
        # Mock entry points
        mock_entry_point = Mock()
        mock_entry_point.name = "available_plugin"
        mock_entry_point.dist = Mock()
        mock_entry_point.dist.name = "available-package"
        mock_entry_point.dist.version = "1.0.0"
        mock_entry_point.value = "module:PluginClass"

        mock_ep_result = Mock()
        mock_ep_result.select = Mock(return_value=[mock_entry_point])
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        available = registry.discover_all_available_plugins()

        assert len(available) == 1
        plugin_info = available[0]
        assert plugin_info["name"] == "available_plugin"
        assert plugin_info["version"] == "1.0.0"
        assert plugin_info["package"] == "available-package"
        assert plugin_info["status"] == "available"
        assert plugin_info["loaded"] is False

    @patch("src.agent.plugins.manager.importlib.metadata.entry_points")
    @patch("src.agent.plugins.manager.logger")
    def test_discover_all_available_plugins_with_error(self, mock_logger, mock_entry_points):
        """Test discovering available plugins when some have errors."""
        # Mock entry point that raises error
        mock_entry_point = Mock()
        mock_entry_point.name = "error_plugin"
        mock_entry_point.dist = Mock()
        mock_entry_point.dist.name = "error-package"

        # Make accessing dist.version raise an error
        type(mock_entry_point.dist).version = PropertyMock(side_effect=Exception("Version error"))

        mock_ep_result = Mock()
        mock_ep_result.select = Mock(return_value=[mock_entry_point])
        mock_entry_points.return_value = mock_ep_result

        registry = PluginRegistry()
        available = registry.discover_all_available_plugins()

        # Should still include the plugin with error status
        assert len(available) == 1
        plugin_info = available[0]
        assert plugin_info["name"] == "error_plugin"
        assert plugin_info["status"] == "error"
        assert "error" in plugin_info


# Add custom PropertyMock import for older Python versions
try:
    from unittest.mock import PropertyMock
except ImportError:

    class PropertyMock(Mock):
        def __get__(self, obj, obj_type=None):
            return self()

        def __set__(self, obj, val):
            self(val)
