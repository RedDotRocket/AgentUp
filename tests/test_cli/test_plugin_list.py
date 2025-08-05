import sys
from pathlib import Path
from unittest.mock import Mock, patch
import yaml

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.cli.commands.plugin import list_plugins


class TestPluginListCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_plugin_registry(self):
        """Mock the plugin registry to return predictable test data."""
        with patch("agent.cli.commands.plugin.PluginRegistry") as mock_registry:
            # Create mock plugin data
            mock_plugins = [
                {
                    "name": "test_plugin",
                    "version": "1.0.0",
                    "package": "test-plugin",
                    "status": "available",
                    "loaded": False,
                    "configured": False,
                    "display_name": "Test Plugin",
                }
            ]
            
            mock_instance = Mock()
            mock_instance.discover_all_available_plugins.return_value = mock_plugins
            mock_registry.return_value = mock_instance
            
            yield mock_instance

    @pytest.fixture
    def mock_entry_points(self):
        """Mock importlib.metadata.entry_points to return test plugin entry points."""
        with patch("agent.cli.commands.plugin.importlib.metadata.entry_points") as mock_ep:
            # Create a mock entry point
            mock_entry_point = Mock()
            mock_entry_point.name = "test_plugin"
            
            # Create a mock plugin class
            mock_plugin_class = Mock()
            mock_plugin_instance = Mock()
            
            # Create mock capability definitions
            mock_capability = Mock()
            mock_capability.id = "test_capability"
            mock_capability.name = "Test Capability"
            mock_capability.description = "A test capability"
            mock_capability.required_scopes = ["test:read"]
            mock_capability.ai_function = False
            
            mock_plugin_instance.get_capability_definitions.return_value = [mock_capability]
            mock_plugin_class.return_value = mock_plugin_instance
            mock_entry_point.load.return_value = mock_plugin_class
            
            # Mock the entry_points() function
            mock_ep_result = Mock()
            mock_ep_result.select.return_value = [mock_entry_point]
            mock_ep.return_value = mock_ep_result
            
            yield mock_ep

    def test_list_plugins_table_format(self, runner, mock_plugin_registry):
        """Test the default table format output."""
        result = runner.invoke(list_plugins)
        
        assert result.exit_code == 0
        assert "Available Plugins" in result.output
        assert "test_plugin" in result.output

    def test_list_plugins_json_format(self, runner, mock_plugin_registry):
        """Test the JSON format output."""
        result = runner.invoke(list_plugins, ["--format", "json"])
        
        assert result.exit_code == 0
        assert '"plugins"' in result.output
        assert '"test_plugin"' in result.output

    def test_list_plugins_yaml_format(self, runner, mock_plugin_registry):
        """Test the YAML format output."""
        result = runner.invoke(list_plugins, ["--format", "yaml"])
        
        assert result.exit_code == 0
        assert "plugins:" in result.output
        assert "test_plugin" in result.output

    def test_list_plugins_agentup_config_format(self, runner, mock_plugin_registry, mock_entry_points):
        """Test the new agentup-config format output."""
        result = runner.invoke(list_plugins, ["--format", "agentup-config"])
        
        assert result.exit_code == 0
        
        # Parse the YAML output to verify structure
        try:
            output_data = yaml.safe_load(result.output)
            
            # Verify the structure matches agentup.yml format
            assert "plugins" in output_data
            assert isinstance(output_data["plugins"], list)
            
            if output_data["plugins"]:  # Only check if there are plugins
                plugin = output_data["plugins"][0]
                
                # Check required fields
                assert "plugin_id" in plugin
                assert "name" in plugin
                assert "description" in plugin
                assert "priority" in plugin
                assert "tags" in plugin
                assert "input_mode" in plugin
                assert "output_mode" in plugin
                assert "capabilities" in plugin
                
                # Check capabilities structure
                if plugin["capabilities"]:
                    capability = plugin["capabilities"][0]
                    assert "capability_id" in capability
                    assert "required_scopes" in capability
                    assert "enabled" in capability
                    
        except yaml.YAMLError as e:
            pytest.fail(f"Output is not valid YAML: {e}")

    def test_list_plugins_agentup_config_includes_capabilities_by_default(self, runner, mock_plugin_registry, mock_entry_points):
        """Test that agentup-config format includes capabilities by default (no -c flag needed)."""
        result = runner.invoke(list_plugins, ["--format", "agentup-config"])
        
        assert result.exit_code == 0
        
        # Parse the YAML output
        output_data = yaml.safe_load(result.output)
        
        # Verify capabilities are included even without -c flag
        if output_data.get("plugins"):
            plugin = output_data["plugins"][0]
            assert "capabilities" in plugin
            # Should have capabilities populated, not just an empty list
            if plugin["capabilities"]:
                assert plugin["capabilities"][0]["capability_id"] == "test_capability"

    def test_list_plugins_with_capabilities_flag(self, runner, mock_plugin_registry, mock_entry_points):
        """Test that the -c flag works with other formats."""
        result = runner.invoke(list_plugins, ["--format", "yaml", "-c"])
        
        assert result.exit_code == 0
        assert "capabilities:" in result.output

    def test_agentup_config_format_choice_exists(self, runner):
        """Test that agentup-config is a valid format choice."""
        result = runner.invoke(list_plugins, ["--format", "invalid"])
        
        assert result.exit_code != 0
        assert "agentup-config" in result.output  # Should be in the error message showing valid choices