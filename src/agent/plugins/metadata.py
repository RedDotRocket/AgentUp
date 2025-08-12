from importlib.metadata import distributions

import structlog

# Lock file functionality removed - using UV-based package management
# This module now contains only essential utility functions for plugin metadata

logger = structlog.get_logger(__name__)


def get_plugin_id_from_package(package_name: str) -> str | None:
    """
    Determine plugin_id from package name by checking entry points.

    Args:
        package_name: Package name to check

    Returns:
        Plugin ID if found, None otherwise
    """
    try:
        # Check all agentup plugin entry points
        for dist in distributions():
            if dist.entry_points:
                for entry_point in dist.entry_points:
                    if entry_point.group == "agentup.plugins":
                        try:
                            # Check if this distribution matches the package name
                            normalized_name = dist.metadata["Name"].lower().replace("_", "-")
                            if normalized_name == package_name.lower():
                                return entry_point.name
                        except Exception as e:
                            logger.warning(f"Failed to get plugin_id for package {package_name}: {e}")
    except Exception as e:
        logger.debug(f"Failed to find plugin_id for package {package_name}: {e}")

    # Fallback: convert package name to plugin_id format
    return package_name.replace("-", "_").replace(".", "_")
