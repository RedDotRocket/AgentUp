import hashlib
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PluginSecurityManager:
    """
    Manages basic security for the plugin system.

    Provides allowlisting, package verification, and basic integrity checks
    without the complexity of full cryptographic signing.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.security_config = config.get("plugin_security", {})

        # Load security configuration
        self.mode = self.security_config.get("mode", "configured")  # "allowlist", "configured", "permissive"
        self.require_explicit_config = self.security_config.get("require_explicit_configuration", True)

        # Load allowlists
        self.allowed_plugins = self._load_allowed_plugins()
        self.blocked_plugins = self._load_blocked_plugins()

        logger.info(f"Plugin security mode: {self.mode}, allowed plugins: {len(self.allowed_plugins)}")

    def _load_allowed_plugins(self) -> dict[str, dict[str, Any]]:
        """Load allowed plugins from configuration"""
        allowed = {}

        if self.mode == "allowlist":
            # Explicit allowlist mode
            explicit_allowed = self.security_config.get("allowed_plugins", {})
            allowed.update(explicit_allowed)

        elif self.mode == "configured":
            # Allow plugins that are explicitly configured
            configured_plugins = self.config.get("plugins", [])
            for plugin_config in configured_plugins:
                plugin_id = plugin_config.get("plugin_id")
                if plugin_id:
                    allowed[plugin_id] = {
                        "package": plugin_config.get("package"),
                        "verified": plugin_config.get("verified", False),
                        "min_version": plugin_config.get("min_version"),
                        "max_version": plugin_config.get("max_version"),
                    }

        return allowed

    def _load_blocked_plugins(self) -> list[str]:
        """Load blocked plugins from configuration"""
        return self.security_config.get("blocked_plugins", [])

    def is_plugin_allowed(self, plugin_id: str, package_info: Any = None) -> tuple[bool, str]:
        """
        Check if a plugin is allowed to be loaded.

        Args:
            plugin_id: Plugin identifier
            package_info: Package metadata (from entry point dist)

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check blocked list first
        if plugin_id in self.blocked_plugins:
            return False, f"Plugin '{plugin_id}' is explicitly blocked"

        # Permissive mode allows everything except blocked
        if self.mode == "permissive":
            return True, "Permissive mode"

        # Check allowlist
        if plugin_id not in self.allowed_plugins:
            return False, f"Plugin '{plugin_id}' not in allowlist (mode: {self.mode})"

        allowed_config = self.allowed_plugins[plugin_id]

        # Check package name if specified
        expected_package = allowed_config.get("package")
        if expected_package and package_info:
            actual_package = package_info.name
            if actual_package != expected_package:
                return False, f"Package name mismatch: expected '{expected_package}', got '{actual_package}'"

        # Check version constraints
        if package_info:
            version = package_info.version
            min_version = allowed_config.get("min_version")
            max_version = allowed_config.get("max_version")

            if min_version and not self._version_satisfies(version, f">={min_version}"):
                return False, f"Version {version} below minimum {min_version}"

            if max_version and not self._version_satisfies(version, f"<={max_version}"):
                return False, f"Version {version} above maximum {max_version}"

        return True, "Plugin allowed"

    def _version_satisfies(self, version: str, constraint: str) -> bool:
        """Simple version constraint checking"""
        try:
            from packaging import version as pkg_version

            v = pkg_version.parse(version)

            if constraint.startswith(">="):
                min_v = pkg_version.parse(constraint[2:])
                return v >= min_v
            elif constraint.startswith("<="):
                max_v = pkg_version.parse(constraint[2:])
                return v <= max_v
            elif constraint.startswith(">"):
                min_v = pkg_version.parse(constraint[1:])
                return v > min_v
            elif constraint.startswith("<"):
                max_v = pkg_version.parse(constraint[1:])
                return v < max_v
            elif constraint.startswith("=="):
                exact_v = pkg_version.parse(constraint[2:])
                return v == exact_v

            return True

        except ImportError:
            # Fallback to string comparison if packaging not available
            logger.warning("packaging library not available for version checking")
            return True
        except Exception as e:
            logger.warning(f"Version constraint check failed for {version} {constraint}: {e}")
            return True

    def validate_plugin_package(self, plugin_id: str, package_path: Path) -> tuple[bool, list[str]]:
        """
        Perform basic validation of a plugin package.

        Args:
            plugin_id: Plugin identifier
            package_path: Path to plugin package/directory

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        try:
            # Check if path exists
            if not package_path.exists():
                issues.append(f"Plugin path does not exist: {package_path}")
                return False, issues

            # For filesystem plugins, check basic structure
            if package_path.is_dir():
                # Check for plugin entry file
                has_plugin_py = (package_path / "plugin.py").exists()
                has_init_py = (package_path / "__init__.py").exists()

                if not (has_plugin_py or has_init_py):
                    issues.append("No plugin.py or __init__.py found")

                # Check for suspicious files
                suspicious_patterns = ["*.exe", "*.dll", "*.so", "*.dylib"]
                for pattern in suspicious_patterns:
                    suspicious_files = list(package_path.glob(pattern))
                    if suspicious_files:
                        issues.append(f"Suspicious binary files found: {[f.name for f in suspicious_files]}")

                # Check file sizes (prevent large files)
                max_file_size = 10 * 1024 * 1024  # 10MB
                for file_path in package_path.rglob("*"):
                    if file_path.is_file() and file_path.stat().st_size > max_file_size:
                        issues.append(f"Large file detected: {file_path.name} ({file_path.stat().st_size} bytes)")

            # Additional checks can be added here
            # - Code analysis for dangerous patterns
            # - Dependency analysis
            # - Permission checks

        except Exception as e:
            issues.append(f"Validation error: {str(e)}")

        return len(issues) == 0, issues

    def compute_plugin_hash(self, plugin_path: Path) -> str:
        """
        Compute a simple hash of plugin files for basic integrity checking.

        Args:
            plugin_path: Path to plugin directory or file

        Returns:
            SHA256 hash of plugin contents
        """
        hasher = hashlib.sha256()

        try:
            if plugin_path.is_file():
                # Single file
                with open(plugin_path, "rb") as f:
                    hasher.update(f.read())
            else:
                # Directory - hash all Python files
                python_files = sorted(plugin_path.glob("**/*.py"))
                for py_file in python_files:
                    with open(py_file, "rb") as f:
                        hasher.update(py_file.name.encode())  # Include filename
                        hasher.update(f.read())

        except Exception as e:
            logger.warning(f"Could not compute hash for {plugin_path}: {e}")
            return "unknown"

        return hasher.hexdigest()

    def create_security_report(self, plugin_id: str, plugin_info: dict[str, Any]) -> dict[str, Any]:
        """
        Create a security report for a plugin.

        Args:
            plugin_id: Plugin identifier
            plugin_info: Plugin information dictionary

        Returns:
            Security report dictionary
        """
        report = {"plugin_id": plugin_id, "security_level": "unknown", "allowed": False, "reason": "", "checks": {}}

        # Check if plugin is allowed
        allowed, reason = self.is_plugin_allowed(plugin_id, plugin_info.get("package_info"))
        report["allowed"] = allowed
        report["reason"] = reason

        # Determine security level
        if plugin_id in self.allowed_plugins:
            config = self.allowed_plugins[plugin_id]
            if config.get("builtin"):
                report["security_level"] = "builtin"
            elif config.get("verified"):
                report["security_level"] = "verified"
            else:
                report["security_level"] = "configured"
        else:
            report["security_level"] = "unknown"

        # Add validation checks
        plugin_path = plugin_info.get("path")
        if plugin_path:
            path_obj = Path(plugin_path)
            is_valid, issues = self.validate_plugin_package(plugin_id, path_obj)
            report["checks"]["validation"] = {"passed": is_valid, "issues": issues}

            # Add file hash
            report["checks"]["file_hash"] = self.compute_plugin_hash(path_obj)

        return report

    def log_security_event(self, event_type: str, plugin_id: str, details: dict[str, Any]):
        """
        Log security-related events.

        Args:
            event_type: Type of security event
            plugin_id: Plugin identifier
            details: Additional event details
        """
        log_entry = {"event": event_type, "plugin_id": plugin_id, "timestamp": time.time(), **details}

        if event_type in ["plugin_blocked", "validation_failed", "suspicious_activity"]:
            logger.warning(f"Security event: {event_type} for plugin {plugin_id}", extra=log_entry)
        else:
            logger.info(f"Security event: {event_type} for plugin {plugin_id}", extra=log_entry)


def validate_plugin_configuration(plugin_config: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate plugin configuration for security issues.

    Args:
        plugin_config: Plugin configuration dictionary

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check required fields
    if not plugin_config.get("plugin_id"):
        issues.append("Plugin ID is required")

    # Check for dangerous scope combinations
    capabilities = plugin_config.get("capabilities", [])
    dangerous_scopes = {"system:admin", "files:admin", "network:admin"}

    for capability in capabilities:
        scopes = set(capability.get("required_scopes", []))
        if dangerous_scopes.intersection(scopes):
            issues.append(f"Capability '{capability.get('capability_id')}' requires dangerous scopes: {scopes}")

    # Check for suspicious configurations
    suspicious_patterns = ["eval", "exec", "system", "subprocess", "__import__"]
    config_str = str(plugin_config).lower()

    for pattern in suspicious_patterns:
        if pattern in config_str:
            issues.append(f"Configuration contains suspicious pattern: {pattern}")

    return len(issues) == 0, issues
