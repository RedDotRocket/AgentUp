"""Configuration file synchronization utilities.

This module provides utilities to keep configuration files in sync with
the current AgentUp version, particularly for YAML config files.
"""

import re
import shutil
from pathlib import Path

import structlog
import yaml

from ..config.model import PluginConfig
from .version import get_version

logger = structlog.get_logger(__name__)


def sync_config_version(config_path: Path, version: str = None) -> bool:
    """Sync version in a YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file
        version: Version to set (defaults to current AgentUp version)

    Returns:
        True if file was updated, False if no changes needed
    """
    if version is None:
        version = get_version()

    if not config_path.exists():
        logger.warning("Configuration file not found", path=str(config_path))
        return False

    try:
        # Read the current config
        with open(config_path, encoding="utf-8") as f:
            content = f.read()

        # Parse YAML to check current version
        config_data = yaml.safe_load(content)
        current_version = config_data.get("version")

        if current_version == version:
            logger.debug("Configuration already up to date", path=str(config_path), version=version)
            return False

        # Update version using regex to preserve formatting/comments
        version_pattern = r'^(\s*version\s*:\s*)(["\']?)([^"\'\n]+)(["\']?)(\s*)$'

        lines = content.splitlines()
        updated = False

        for i, line in enumerate(lines):
            match = re.match(version_pattern, line)
            if match:
                prefix, quote1, old_version, quote2, suffix = match.groups()
                # Use same quoting style as original
                new_line = f"{prefix}{quote1}{version}{quote2}{suffix}"
                lines[i] = new_line
                updated = True
                logger.info(
                    "Updated version in config", path=str(config_path), old_version=old_version, new_version=version
                )
                break

        if not updated:
            logger.warning("Version field not found in config", path=str(config_path))
            return False

        # Write back the updated content
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return True

    except Exception as e:
        logger.error("Failed to sync config version", path=str(config_path), error=str(e))
        return False


def sync_agentup_yml(project_root: Path = None, version: str = None) -> bool:
    """Sync version in the main agentup.yml file.

    Args:
        project_root: Root directory of the project (defaults to current dir)
        version: Version to set (defaults to current AgentUp version)

    Returns:
        True if file was updated, False if no changes needed
    """
    if project_root is None:
        project_root = Path.cwd()

    config_path = project_root / "agentup.yml"
    return sync_config_version(config_path, version)


def find_and_sync_all_configs(root_dir: Path = None, version: str = None) -> dict[str, bool]:
    """Find all AgentUp configuration files and sync their versions.

    Args:
        root_dir: Root directory to search (defaults to current dir)
        version: Version to set (defaults to current AgentUp version)

    Returns:
        Dictionary mapping file paths to update status (True if updated)
    """
    if root_dir is None:
        root_dir = Path.cwd()

    if version is None:
        version = get_version()

    results = {}

    # Common AgentUp config file patterns
    config_patterns = ["agentup.yml", "agentup.yaml", "*/agentup.yml", "*/agentup.yaml"]

    for pattern in config_patterns:
        for config_path in root_dir.glob(pattern):
            if config_path.is_file():
                try:
                    updated = sync_config_version(config_path, version)
                    results[str(config_path)] = updated
                except Exception as e:
                    logger.error("Failed to process config file", path=str(config_path), error=str(e))
                    results[str(config_path)] = False

    return results


def validate_config_version(config_path: Path, expected_version: str = None) -> bool:
    """Validate that a config file has the expected version.

    Args:
        config_path: Path to the configuration file
        expected_version: Expected version (defaults to current AgentUp version)

    Returns:
        True if version matches, False otherwise
    """
    if expected_version is None:
        expected_version = get_version()

    if not config_path.exists():
        return False

    try:
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        current_version = config_data.get("version")
        return current_version == expected_version

    except Exception as e:
        logger.error("Failed to validate config version", path=str(config_path), error=str(e))
        return False


def add_plugin_to_config(config_path: Path, plugin_config: PluginConfig, backup: bool = True) -> bool:
    """Add a plugin configuration to agentup.yml.

    Args:
        config_path: Path to the agentup.yml file
        plugin_config: Plugin configuration to add
        backup: Whether to create backup of existing config

    Returns:
        True if plugin was added successfully
    """
    if not config_path.exists():
        logger.debug("Configuration file not found", path=str(config_path))
        return False

    # Create backup if requested
    if backup:
        backup_path = config_path.with_suffix(".yml.backup")
        shutil.copy2(config_path, backup_path)
        logger.debug("Created config backup", backup_path=str(backup_path))

    try:
        # Read current content to preserve formatting
        with open(config_path, encoding="utf-8") as f:
            content = f.read()

        # Parse YAML to check for existing plugin
        config_data = yaml.safe_load(content)
        existing_plugins = config_data.get("plugins", [])

        # Check if plugin already exists
        if any(p.get("plugin_id") == plugin_config.plugin_id for p in existing_plugins):
            return False

        # Convert plugin config to dict for YAML serialization
        plugin_dict = plugin_config.model_dump(exclude_unset=True)

        # Add plugin to the list
        existing_plugins.append(plugin_dict)
        config_data["plugins"] = existing_plugins

        # Write updated config preserving structure
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config_data, f, default_flow_style=False, sort_keys=False, indent=2, width=120, allow_unicode=True
            )

        logger.info("Added plugin to configuration", plugin_id=plugin_config.plugin_id, path=str(config_path))
        return True

    except Exception as e:
        logger.error("Failed to add plugin to config", path=str(config_path), error=str(e))
        # Restore backup on failure
        if backup:
            backup_path = config_path.with_suffix(".yml.backup")
            if backup_path.exists():
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup due to error")
        return False


def remove_plugin_from_config(config_path: Path, plugin_id: str, backup: bool = True) -> bool:
    """Remove a plugin configuration from agentup.yml.

    Args:
        config_path: Path to the agentup.yml file
        plugin_id: ID of plugin to remove
        backup: Whether to create backup of existing config

    Returns:
        True if plugin was removed successfully
    """
    if not config_path.exists():
        logger.debug("Configuration file not found", path=str(config_path))
        return False

    # Create backup if requested
    if backup:
        backup_path = config_path.with_suffix(".yml.backup")
        shutil.copy2(config_path, backup_path)
        logger.debug("Created config backup", backup_path=str(backup_path))

    try:
        # Read and parse config
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        plugins = config_data.get("plugins", [])

        # Find and remove plugin
        original_count = len(plugins)
        plugins = [p for p in plugins if p.get("plugin_id") != plugin_id]

        if len(plugins) == original_count:
            logger.debug("Plugin not found in config", plugin_id=plugin_id)
            return False

        config_data["plugins"] = plugins

        # Write updated config
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config_data, f, default_flow_style=False, sort_keys=False, indent=2, width=120, allow_unicode=True
            )

        logger.info("Removed plugin from configuration", plugin_id=plugin_id, path=str(config_path))
        return True

    except Exception as e:
        logger.error("Failed to remove plugin from config", path=str(config_path), error=str(e))
        # Restore backup on failure
        if backup:
            backup_path = config_path.with_suffix(".yml.backup")
            if backup_path.exists():
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup due to error")
        return False


def update_plugin_in_config(config_path: Path, plugin_config: PluginConfig, backup: bool = True) -> bool:
    """Update an existing plugin configuration in agentup.yml.

    Args:
        config_path: Path to the agentup.yml file
        plugin_config: Updated plugin configuration
        backup: Whether to create backup of existing config

    Returns:
        True if plugin was updated successfully
    """
    if not config_path.exists():
        logger.debug("Configuration file not found", path=str(config_path))
        return False

    # Create backup if requested
    if backup:
        backup_path = config_path.with_suffix(".yml.backup")
        shutil.copy2(config_path, backup_path)
        logger.debug("Created config backup", backup_path=str(backup_path))

    try:
        # Read and parse config
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        plugins = config_data.get("plugins", [])

        # Find and update plugin
        plugin_updated = False
        for i, plugin in enumerate(plugins):
            if plugin.get("plugin_id") == plugin_config.plugin_id:
                # Convert new plugin config to dict
                plugin_dict = plugin_config.model_dump(exclude_unset=True)
                plugins[i] = plugin_dict
                plugin_updated = True
                break

        if not plugin_updated:
            logger.debug("Plugin not found in config for update", plugin_id=plugin_config.plugin_id)
            return False

        config_data["plugins"] = plugins

        # Write updated config
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config_data, f, default_flow_style=False, sort_keys=False, indent=2, width=120, allow_unicode=True
            )

        logger.info("Updated plugin in configuration", plugin_id=plugin_config.plugin_id, path=str(config_path))
        return True

    except Exception as e:
        logger.error("Failed to update plugin in config", path=str(config_path), error=str(e))
        # Restore backup on failure
        if backup:
            backup_path = config_path.with_suffix(".yml.backup")
            if backup_path.exists():
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup due to error")
        return False


def get_plugins_from_config(config_path: Path) -> list[dict]:
    """Get all plugin configurations from agentup.yml.

    Args:
        config_path: Path to the agentup.yml file

    Returns:
        List of plugin configuration dictionaries
    """
    if not config_path.exists():
        logger.debug("Configuration file not found", path=str(config_path))
        return []

    try:
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return config_data.get("plugins", [])

    except Exception as e:
        logger.error("Failed to read plugins from config", path=str(config_path), error=str(e))
        return []
