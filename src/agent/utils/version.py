"""Version management utilities for AgentUp.

This module provides centralized version reading functionality, ensuring
all parts of the application use the same version information.
"""

import importlib.metadata
import re
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def get_version() -> str:
    """Get the current AgentUp version.

    Tries multiple methods to determine the version:
    1. From installed package metadata (production/installed mode)
    2. From pyproject.toml parsing (development mode)
    3. Fallback to a default if all else fails

    Returns:
        The version string (e.g., "0.5.1")
    """
    # Try to get version from installed package metadata first
    try:
        return importlib.metadata.version("agentup")
    except importlib.metadata.PackageNotFoundError:
        logger.debug("Package not installed, trying pyproject.toml")
    except Exception as e:
        logger.debug("Error reading package metadata", error=str(e))

    # Fallback to reading from pyproject.toml (development mode)
    version = _read_version_from_pyproject()
    if version:
        return version

    # Final fallback
    logger.warning("Could not determine version, using fallback")
    return "0.0.0-dev"


def _read_version_from_pyproject() -> str | None:
    """Read version from pyproject.toml file.

    Returns:
        Version string if found, None otherwise
    """
    try:
        # Find pyproject.toml - look up the directory tree from this file
        current_path = Path(__file__).resolve()
        pyproject_path = None

        # Walk up the directory tree looking for pyproject.toml
        for parent in current_path.parents:
            candidate = parent / "pyproject.toml"
            if candidate.exists():
                pyproject_path = candidate
                break

        if not pyproject_path:
            logger.debug("pyproject.toml not found")
            return None

        # Read and parse the version line
        content = pyproject_path.read_text(encoding="utf-8")

        # Look for version = "x.y.z" in the [project] section
        pattern = r'^\s*version\s*=\s*["\']([^"\']+)["\']'
        for line in content.splitlines():
            match = re.match(pattern, line)
            if match:
                version = match.group(1)
                logger.debug("Found version in pyproject.toml", version=version)
                return version

        logger.debug("Version not found in pyproject.toml")
        return None

    except Exception as e:
        logger.debug("Error reading pyproject.toml", error=str(e))
        return None


def get_version_info() -> dict[str, str]:
    """Get detailed version information.

    Returns:
        Dictionary with version details
    """
    version = get_version()

    return {
        "version": version,
        "package": "agentup",
        "source": _get_version_source(),
    }


def _get_version_source() -> str:
    """Determine where the version information came from.

    Returns:
        Source description (e.g., "package", "pyproject.toml", "fallback")
    """
    try:
        importlib.metadata.version("agentup")
        return "package"
    except importlib.metadata.PackageNotFoundError:
        if _read_version_from_pyproject():
            return "pyproject.toml"
        return "fallback"
    except Exception:
        return "error"


def to_version_case(version: str) -> str | None:
    """Normalizes a version string into semantic versioning format (e.g., 1.0.0)."""
    if not version:
        return None

    cleaned_text = re.sub(r"[\s_-]+", ".", version.strip())
    # Remove any existing 'v' prefix for consistency
    cleaned_text = re.sub(r"^v", "", cleaned_text, flags=re.IGNORECASE)

    match = re.match(r"^(\d+(?:\.\d+){0,2})$", cleaned_text)

    if match:
        numbers_part = match.group(1)

        if numbers_part.count(".") == 1:
            numbers_part += ".0"
        elif numbers_part.count(".") == 0:
            numbers_part += ".0.0"

        return numbers_part

    return version
