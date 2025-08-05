"""Tests for version management and consistency."""

import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.utils.config_sync import sync_config_version, validate_config_version
from agent.utils.version import get_version, get_version_info


class TestVersionUtility:
    """Test the version utility functions."""

    def test_get_version_returns_string(self):
        """Test that get_version returns a valid version string."""
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0
        # Should match semantic versioning pattern
        assert re.match(r"^\d+\.\d+\.\d+", version)

    def test_get_version_info(self):
        """Test that get_version_info returns expected structure."""
        info = get_version_info()
        assert isinstance(info, dict)
        assert "version" in info
        assert "package" in info
        assert "source" in info
        assert info["package"] == "agentup"
        assert isinstance(info["version"], str)
        assert info["source"] in ["package", "pyproject.toml", "fallback", "error"]

    @patch("agent.utils.version.importlib.metadata.version")
    def test_version_fallback_to_pyproject(self, mock_version):
        """Test version fallback when package not installed."""
        from importlib.metadata import PackageNotFoundError

        mock_version.side_effect = PackageNotFoundError()

        # Should still return a version (either from pyproject.toml or fallback)
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0


class TestConfigSync:
    """Test configuration file synchronization."""

    def test_sync_yaml_config(self):
        """Test syncing version in a YAML configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml_content = """
name: Test Agent
description: Test agent description
version: 1.0.0
environment: development
"""
            f.write(yaml_content)
            f.flush()

            config_path = Path(f.name)

            try:
                # Test updating version
                result = sync_config_version(config_path, "2.0.0")
                assert result is True

                # Verify the version was updated
                with open(config_path) as f:
                    updated_content = f.read()
                    assert "version: 2.0.0" in updated_content
                    assert "version: 1.0.0" not in updated_content

                # Test that other content is preserved
                assert "name: Test Agent" in updated_content
                assert "description: Test agent description" in updated_content

            finally:
                config_path.unlink()

    def test_sync_yaml_config_with_quotes(self):
        """Test syncing version in YAML with quoted values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml_content = """
name: "Test Agent"
version: "1.0.0"
description: 'Test description'
"""
            f.write(yaml_content)
            f.flush()

            config_path = Path(f.name)

            try:
                # Test updating version
                result = sync_config_version(config_path, "2.0.0")
                assert result is True

                # Verify the version was updated and quotes preserved
                with open(config_path) as f:
                    updated_content = f.read()
                    assert 'version: "2.0.0"' in updated_content

            finally:
                config_path.unlink()

    def test_validate_config_version(self):
        """Test validating configuration file version."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml_content = """
name: Test Agent
version: 1.0.0
"""
            f.write(yaml_content)
            f.flush()

            config_path = Path(f.name)

            try:
                # Test validation with matching version
                assert validate_config_version(config_path, "1.0.0") is True

                # Test validation with non-matching version
                assert validate_config_version(config_path, "2.0.0") is False

            finally:
                config_path.unlink()

    def test_sync_nonexistent_file(self):
        """Test syncing a non-existent file."""
        nonexistent_path = Path("/tmp/nonexistent_config.yml")
        result = sync_config_version(nonexistent_path, "1.0.0")
        assert result is False


class TestVersionConsistency:
    """Test version consistency across the codebase."""

    def test_main_init_uses_version_utility(self):
        """Test that main __init__.py uses the version utility."""
        init_file = Path("src/agent/__init__.py")
        assert init_file.exists()

        content = init_file.read_text()
        assert "from .utils.version import get_version" in content
        assert "__version__ = get_version()" in content
        assert "0.5.1" not in content  # Should not have hardcoded version

    def test_security_init_uses_version_utility(self):
        """Test that security __init__.py uses the version utility."""
        init_file = Path("src/agent/security/__init__.py")
        assert init_file.exists()

        content = init_file.read_text()
        assert "from ..utils.version import get_version" in content
        assert "__version__ = get_version()" in content

    def test_cli_uses_version_utility(self):
        """Test that CLI uses the version utility."""
        cli_file = Path("src/agent/cli/main.py")
        assert cli_file.exists()

        content = cli_file.read_text()
        assert "from ..utils.version import get_version" in content
        assert "version=get_version()" in content
        assert '@click.version_option(version="0.5.1"' not in content

    def test_templates_use_version_variables(self):
        """Test that templates use version variables instead of hardcoded values."""
        template_files = [
            "src/agent/templates/pyproject.toml.j2",
            "src/agent/templates/plugins/pyproject.toml.j2",
            "src/agent/templates/plugins/.cursor/rules/agentup_plugin.mdc.j2",
        ]

        for template_path in template_files:
            template_file = Path(template_path)
            if template_file.exists():
                content = template_file.read_text()
                # Should use template variables, not hardcoded versions
                assert "{{ agentup_version }}" in content or "{{ project_version" in content
                # Should not contain hardcoded 0.5.1
                assert "0.5.1" not in content, f"Found hardcoded version in {template_path}"

    def test_pyproject_toml_version_format(self):
        """Test that pyproject.toml has a valid version format."""
        pyproject_file = Path("pyproject.toml")
        assert pyproject_file.exists()

        content = pyproject_file.read_text()
        # Find version line
        version_match = re.search(r'^version = ["\']([^"\']+)["\']', content, re.MULTILINE)
        assert version_match is not None, "Version not found in pyproject.toml"

        version = version_match.group(1)
        # Should match semantic versioning
        assert re.match(r"^\d+\.\d+\.\d+$", version), f"Invalid version format: {version}"

    def test_version_utilities_accessible(self):
        """Test that version utilities can be imported and used."""
        from agent.utils.config_sync import sync_config_version, validate_config_version
        from agent.utils.version import get_version, get_version_info

        # Test that functions are callable
        version = get_version()
        assert isinstance(version, str)

        info = get_version_info()
        assert isinstance(info, dict)

        # Test that config sync functions exist
        assert callable(sync_config_version)
        assert callable(validate_config_version)


class TestTemplateRendering:
    """Test that template rendering includes version variables."""

    def test_generator_includes_agentup_version(self):
        """Test that the project generator includes agentup_version in context."""
        from agent.generator import ProjectGenerator

        # Create a minimal config
        config = {"name": "test-project", "description": "Test project", "features": []}

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = ProjectGenerator(Path(temp_dir), config)
            context = generator._build_template_context()

            assert "agentup_version" in context
            assert isinstance(context["agentup_version"], str)
            assert len(context["agentup_version"]) > 0

    def test_plugin_command_includes_agentup_version(self):
        """Test that plugin creation includes agentup_version in context."""
        # This test verifies that the plugin.py command includes the version
        # We can't easily test the full command, but we can check imports
        from agent.cli.commands.plugin import get_version

        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0


@pytest.mark.integration
class TestVersionIntegration:
    """Integration tests for version management."""

    def test_version_consistency_across_modules(self):
        """Test that all modules report the same version."""
        from agent import __version__ as main_version
        from agent.security import __version__ as security_version
        from agent.utils.version import get_version

        util_version = get_version()

        # All should report the same version
        assert main_version == util_version
        assert security_version == util_version

    def test_release_script_exists_and_executable(self):
        """Test that the release script exists and is executable."""
        release_script = Path("scripts/release.py")
        assert release_script.exists()
        assert release_script.stat().st_mode & 0o111  # Check if executable

    def test_config_sync_utility_exists(self):
        """Test that config sync utilities exist."""
        from agent.utils.config_sync import (
            find_and_sync_all_configs,
            sync_agentup_yml,
            sync_config_version,
            validate_config_version,
        )

        # Test that all functions are callable
        assert callable(sync_config_version)
        assert callable(sync_agentup_yml)
        assert callable(find_and_sync_all_configs)
        assert callable(validate_config_version)
