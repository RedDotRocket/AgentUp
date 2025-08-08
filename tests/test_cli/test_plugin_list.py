"""Tests for the plugin list command."""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from agent.cli.commands.plugin import list_plugins
from agent.plugins.models import CapabilityDefinition, CapabilityType


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_plugin_registry():
    """Create a mock plugin registry with test data."""
    with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
        mock_registry = MagicMock()

        # Mock plugin data
        mock_registry.discover_all_available_plugins.return_value = [
            {
                "name": "test_plugin",
                "package": "test-plugin-package",
                "version": "1.0.0",
                "status": "available",
                "loaded": False,
                "configured": False,
            },
            {
                "name": "ai_plugin",
                "package": "ai-plugin-package",
                "version": "2.0.0",
                "status": "loaded",
                "loaded": True,
                "configured": True,
            },
        ]

        mock_registry_class.return_value = mock_registry
        yield mock_registry


@pytest.fixture
def mock_plugin_with_capabilities():
    """Create mock plugins with capabilities."""
    with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
        mock_registry = MagicMock()

        # Mock plugin data
        mock_registry.discover_all_available_plugins.return_value = [
            {
                "name": "test_plugin",
                "package": "test-plugin-package",
                "version": "1.0.0",
                "status": "available",
                "loaded": False,
                "configured": False,
            },
        ]

        mock_registry_class.return_value = mock_registry

        # Mock entry points and plugin loading
        with patch("importlib.metadata.entry_points") as mock_entry_points:
            mock_eps = MagicMock()

            # Create mock entry point
            mock_entry_point = MagicMock()
            mock_plugin_class = MagicMock()
            mock_plugin_instance = MagicMock()

            # Create capability definitions
            cap1 = CapabilityDefinition(
                id="test_capability",
                name="Test Capability",
                version="1.0.0",
                description="A test capability",
                capabilities=[CapabilityType.TEXT],
                required_scopes=["test:read"],
            )

            cap2 = CapabilityDefinition(
                id="ai_capability",
                name="AI Capability",
                version="1.0.0",
                description="An AI capability",
                capabilities=[CapabilityType.AI_FUNCTION],
                required_scopes=["ai:function", "test:write"],
            )

            mock_plugin_instance.get_capability_definitions.return_value = [cap1, cap2]
            mock_plugin_class.return_value = mock_plugin_instance
            mock_entry_point.load.return_value = mock_plugin_class

            # Configure entry points mock
            if hasattr(mock_eps, "select"):
                mock_eps.select.return_value = [mock_entry_point]
            else:
                mock_entry_points.return_value = {"agentup.plugins": [mock_entry_point]}
                mock_entry_point.name = "test_plugin"

            mock_entry_points.return_value = mock_eps

            yield mock_registry


class TestPluginListCommand:
    """Test the plugin list command."""

    def test_list_plugins_no_plugins(self, runner):
        """Test listing plugins when none are available."""
        with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.discover_all_available_plugins.return_value = []
            mock_registry_class.return_value = mock_registry

            result = runner.invoke(list_plugins, [])
            assert result.exit_code == 0
            assert "No plugins found" in result.output
            assert "agentup plugin create" in result.output

    def test_list_plugins_table_format(self, runner, mock_plugin_registry):
        """Test listing plugins in table format (default)."""
        result = runner.invoke(list_plugins, [])
        assert result.exit_code == 0
        assert "Available Plugins" in result.output
        assert "test_plugin" in result.output
        assert "test-plugin-package" in result.output
        assert "1.0.0" in result.output

    def test_list_plugins_json_format(self, runner, mock_plugin_registry):
        """Test listing plugins in JSON format."""
        result = runner.invoke(list_plugins, ["--format", "json"])
        assert result.exit_code == 0

        output = json.loads(result.output)
        assert "plugins" in output
        assert len(output["plugins"]) == 2
        assert output["plugins"][0]["name"] == "test_plugin"
        assert output["plugins"][0]["package"] == "test-plugin-package"
        assert output["plugins"][0]["version"] == "1.0.0"

    def test_list_plugins_yaml_format(self, runner, mock_plugin_registry):
        """Test listing plugins in YAML format."""
        result = runner.invoke(list_plugins, ["--format", "yaml"])
        assert result.exit_code == 0

        output = yaml.safe_load(result.output)
        assert "plugins" in output
        assert len(output["plugins"]) == 2
        assert output["plugins"][0]["plugin_id"] == "test_plugin"
        assert output["plugins"][0]["package"] == "test-plugin-package"

    def test_list_plugins_with_capabilities_flag(self, runner, mock_plugin_with_capabilities):
        """Test listing plugins with capabilities flag."""
        result = runner.invoke(list_plugins, ["-c"])
        assert result.exit_code == 0
        assert "Available Plugins" in result.output
        assert "Available Capabilities" in result.output
        assert "test_capability" in result.output
        assert "ai_capability" in result.output

    def test_list_plugins_agentup_cfg_format(self, runner, mock_plugin_with_capabilities):
        """Test listing plugins in agentup-cfg format."""
        result = runner.invoke(list_plugins, ["--format", "agentup-cfg"])
        assert result.exit_code == 0

        output = yaml.safe_load(result.output)
        assert "plugins" in output
        assert len(output["plugins"]) == 1

        plugin = output["plugins"][0]
        assert plugin["plugin_id"] == "test_plugin"
        assert plugin["package"] == "test-plugin-package"
        assert plugin["name"] == "Test Plugin"
        assert "capabilities" in plugin
        assert len(plugin["capabilities"]) == 2

        # Check capability structure
        cap1 = plugin["capabilities"][0]
        assert cap1["capability_id"] == "test_capability"
        assert cap1["required_scopes"] == ["test:read"]
        assert cap1["enabled"] is True

    def test_list_plugins_agentup_cfg_flag(self, runner, mock_plugin_with_capabilities):
        """Test listing plugins using --agentup-cfg flag."""
        result = runner.invoke(list_plugins, ["--agentup-cfg"])
        assert result.exit_code == 0

        output = yaml.safe_load(result.output)
        assert "plugins" in output

        # Should automatically include capabilities without -c flag
        plugin = output["plugins"][0]
        assert "capabilities" in plugin
        assert len(plugin["capabilities"]) == 2

    def test_list_plugins_verbose_mode(self, runner, mock_plugin_registry):
        """Test listing plugins with verbose flag."""
        result = runner.invoke(list_plugins, ["-v"])
        assert result.exit_code == 0
        assert "Available Plugins" in result.output
        # Verbose mode should show additional columns
        assert "Configured" in result.output
        assert "Module" in result.output

    def test_list_plugins_debug_mode(self, runner):
        """Test listing plugins with debug flag."""
        with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.discover_all_available_plugins.return_value = []
            mock_registry_class.return_value = mock_registry

            with patch.dict("os.environ", {}, clear=False) as mock_environ:
                result = runner.invoke(list_plugins, ["--debug"])
                assert result.exit_code == 0
                assert mock_environ.get("AGENTUP_LOG_LEVEL") == "DEBUG"

    def test_ai_function_detection(self, runner, mock_plugin_with_capabilities):
        """Test that AI functions are properly detected."""
        result = runner.invoke(list_plugins, ["-c"])
        assert result.exit_code == 0
        assert "AI Function" in result.output
        # Should show checkmark for AI capability

    def test_empty_capabilities_not_included(self, runner):
        """Test that plugins without capabilities are not included in agentup-cfg format."""
        with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.discover_all_available_plugins.return_value = [
                {
                    "name": "empty_plugin",
                    "package": "empty-plugin",
                    "version": "1.0.0",
                    "status": "available",
                    "loaded": False,
                    "configured": False,
                }
            ]
            mock_registry_class.return_value = mock_registry

            with patch("importlib.metadata.entry_points") as mock_entry_points:
                mock_eps = MagicMock()
                mock_entry_point = MagicMock()
                mock_plugin_class = MagicMock()
                mock_plugin_instance = MagicMock()

                # Return empty capabilities list
                mock_plugin_instance.get_capability_definitions.return_value = []
                mock_plugin_class.return_value = mock_plugin_instance
                mock_entry_point.load.return_value = mock_plugin_class

                if hasattr(mock_eps, "select"):
                    mock_eps.select.return_value = [mock_entry_point]
                else:
                    mock_entry_points.return_value = {"agentup.plugins": [mock_entry_point]}
                    mock_entry_point.name = "empty_plugin"

                mock_entry_points.return_value = mock_eps

                result = runner.invoke(list_plugins, ["--agentup-cfg"])
                assert result.exit_code == 0
                assert "plugins: []" in result.output

    def test_plugin_load_error_handling(self, runner):
        """Test handling of plugin load errors."""
        with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.discover_all_available_plugins.return_value = [
                {
                    "name": "broken_plugin",
                    "package": "broken-plugin",
                    "version": "1.0.0",
                    "status": "error",
                    "loaded": False,
                    "configured": False,
                }
            ]
            mock_registry_class.return_value = mock_registry

            with patch("importlib.metadata.entry_points") as mock_entry_points:
                mock_eps = MagicMock()
                mock_entry_point = MagicMock()
                mock_entry_point.load.side_effect = Exception("Plugin load failed")

                if hasattr(mock_eps, "select"):
                    mock_eps.select.return_value = [mock_entry_point]
                else:
                    mock_entry_points.return_value = {"agentup.plugins": [mock_entry_point]}
                    mock_entry_point.name = "broken_plugin"

                mock_entry_points.return_value = mock_eps

                # Should handle error gracefully
                result = runner.invoke(list_plugins, ["--agentup-cfg", "--verbose"])
                assert result.exit_code == 0

    def test_config_import_error_handling(self, runner):
        """Test handling when Config import fails."""
        with patch("agent.config.Config", side_effect=ImportError):
            with patch("agent.plugins.manager.PluginRegistry") as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry.discover_all_available_plugins.return_value = []
                mock_registry_class.return_value = mock_registry

                result = runner.invoke(list_plugins, [])
                assert result.exit_code == 0
