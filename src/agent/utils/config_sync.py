"""Configuration file synchronization utilities.

This module provides utilities to keep configuration files in sync with
the current AgentUp version, particularly for YAML config files.
"""

import re
from pathlib import Path

import structlog
import yaml

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
