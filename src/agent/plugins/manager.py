"""
New Plugin Manager that replaces Pluggy with direct Python plugin loading.

This manager handles plugin discovery, registration, and execution using
the decorator-based plugin system instead of Pluggy hooks.
"""

import importlib
import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import Any

import structlog

from .base import Plugin
from .decorators import CapabilityMetadata
from .models import (
    AIFunction,
    CapabilityContext,
    CapabilityDefinition,
    CapabilityResult,
    PluginDefinition,
    PluginStatus,
    PluginValidationResult,
)

logger = structlog.get_logger(__name__)


class PluginRegistry:
    """
    Registry for managing decorator-based plugins without Pluggy.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the plugin registry.

        Args:
            config: Optional configuration dictionary. If not provided,
                   will be loaded when needed.
        """
        self.plugins: dict[str, Plugin] = {}
        self.plugin_definitions: dict[str, PluginDefinition] = {}
        self.capabilities: dict[str, CapabilityMetadata] = {}
        self.capability_to_plugin: dict[str, str] = {}

        # Store configuration
        self._config = config

        # Enhanced plugin security system
        self.security_mode = "configured"  # "allowlist", "configured", "permissive"
        self.allowed_plugins: dict[str, dict] | None = None
        self.blocked_plugins: list[str] = []
        self.allowlist_load_failed = False
        self._load_plugin_security_config()

    @property
    def config(self) -> dict[str, Any]:
        """Get configuration, loading it if needed"""
        if self._config is None:
            try:
                from agent.config import Config

                self._config = Config.model_dump()
            except ImportError as e:
                logger.error("Failed to load configuration module")
                raise ImportError("Configuration module not found. Ensure 'agent.config' is available") from e
        return self._config

    def _load_plugin_security_config(self):
        """Load plugin security configuration with enhanced modes and validation"""
        try:
            config = self.config
            logger.debug(f"Loading plugin security config from: {config}")
            security_config = config.get("plugin_security", {})

            # Set security mode
            self.security_mode = security_config.get("mode", "configured")

            # Load blocked plugins
            self.blocked_plugins = security_config.get("blocked_plugins", [])

            if self.security_mode == "allowlist":
                # Explicit allowlist mode - only specified plugins allowed
                self.allowed_plugins = security_config.get("allowed_plugins", {})
                logger.info(f"Security mode: allowlist with {len(self.allowed_plugins)} allowed plugins")
            elif self.security_mode == "permissive":
                # Permissive mode - all plugins allowed except blocked
                self.allowed_plugins = None
                logger.info(f"Security mode: permissive with {len(self.blocked_plugins)} blocked plugins")
            else:
                # Configured mode (default) - allow explicitly configured plugins
                configured_plugins = config.get("plugins", {})
                logger.debug(f"Configured plugins loaded: {configured_plugins}")

                # Initialize empty allowlist - will be set to None if error occurs
                allowed_plugins_temp = {}

                # Validate plugin configuration format
                if not isinstance(configured_plugins, dict | list):
                    raise ValueError(f"Plugin configuration must be a dict or list, got {type(configured_plugins)}")

                # Handle both dictionary and list formats for backward compatibility
                if isinstance(configured_plugins, dict):
                    # New dictionary format: package_name -> plugin_config
                    for package_name, plugin_config in configured_plugins.items():
                        logger.debug(
                            f"Processing plugin entry: package_name='{package_name}', plugin_config={plugin_config}"
                        )
                        if plugin_config and isinstance(plugin_config, dict):
                            plugin_info = {
                                "package": package_name,
                                "plugin_name": plugin_config.get("name", package_name),
                                "verified": plugin_config.get("verified", False),
                                "min_version": plugin_config.get("min_version"),
                                "max_version": plugin_config.get("max_version"),
                            }

                            # Add entry for package name (from config)
                            allowed_plugins_temp[package_name] = plugin_info

                            # Add entry for plugin name if different from package name
                            plugin_name = plugin_config.get("name", package_name)
                            if plugin_name != package_name:
                                allowed_plugins_temp[plugin_name] = plugin_info

                            # Try to discover actual plugin name from entry points
                            discovered_plugin_name = None
                            try:
                                discovered_plugin_name = self._discover_plugin_name_for_package(package_name)
                            except Exception as e:
                                logger.debug(f"Could not discover plugin name for package {package_name}: {e}")

                            # Add discovered name if found
                            if discovered_plugin_name and discovered_plugin_name != package_name:
                                logger.debug(
                                    f"Found entry point name '{discovered_plugin_name}' for package '{package_name}'"
                                )
                                allowed_plugins_temp[discovered_plugin_name] = plugin_info

                            # Try common transformations as fallback if entry point discovery didn't work
                            possible_names = [
                                package_name.replace("-", "_"),  # agentup-systools -> agentup_systools
                                package_name.replace("agentup-", ""),  # agentup-brave -> brave
                                package_name.replace("agentup-", "").replace(
                                    "-", "_"
                                ),  # agentup-some-plugin -> some_plugin
                            ]

                            logger.debug(
                                f"Processing package '{package_name}' with transformed names: {possible_names}"
                            )

                            # Add all possible names to the allowlist
                            for possible_name in possible_names:
                                if possible_name != package_name and possible_name:  # Avoid empty strings
                                    logger.debug(
                                        f"Adding transformed plugin name '{possible_name}' for package '{package_name}'"
                                    )
                                    allowed_plugins_temp[possible_name] = plugin_info
                elif isinstance(configured_plugins, list):
                    # Old list format: list of plugin configs
                    for plugin_config in configured_plugins:
                        package_name = plugin_config.get("package") or plugin_config.get("name")
                        plugin_name = plugin_config.get("name", package_name)
                        logger.debug(
                            f"Processing plugin entry (list format): package_name='{package_name}', plugin_config={plugin_config}"
                        )
                        if package_name:
                            plugin_info = {
                                "package": package_name,
                                "plugin_name": plugin_name,
                                "verified": plugin_config.get("verified", False),
                                "min_version": plugin_config.get("min_version"),
                                "max_version": plugin_config.get("max_version"),
                            }

                            # Add entry for package name (from config)
                            allowed_plugins_temp[package_name] = plugin_info

                            # Try to discover actual plugin name from entry points
                            discovered_plugin_name = None
                            try:
                                discovered_plugin_name = self._discover_plugin_name_for_package(package_name)
                            except Exception as e:
                                logger.debug(f"Could not discover plugin name for package {package_name}: {e}")

                            # Add discovered name if found
                            if discovered_plugin_name and discovered_plugin_name != package_name:
                                logger.debug(
                                    f"Found entry point name '{discovered_plugin_name}' for package '{package_name}'"
                                )
                                allowed_plugins_temp[discovered_plugin_name] = plugin_info

                            # Try common transformations as fallback if entry point discovery didn't work
                            possible_names = [
                                package_name.replace("-", "_"),  # agentup-systools -> agentup_systools
                                package_name.replace("agentup-", ""),  # agentup-brave -> brave
                                package_name.replace("agentup-", "").replace(
                                    "-", "_"
                                ),  # agentup-some-plugin -> some_plugin
                            ]

                            logger.debug(
                                f"Processing package '{package_name}' with transformed names: {possible_names}"
                            )

                            # Add all possible names to the allowlist
                            for possible_name in possible_names:
                                if possible_name != package_name and possible_name:  # Avoid empty strings
                                    logger.debug(
                                        f"Adding transformed plugin name '{possible_name}' for package '{package_name}'"
                                    )
                                    allowed_plugins_temp[possible_name] = plugin_info

                # Successfully processed all plugins, assign to actual field
                self.allowed_plugins = allowed_plugins_temp
                logger.info(f"Security mode: configured with {len(self.allowed_plugins)} allowed plugins")
                logger.debug(f"Allowed plugin keys: {list(self.allowed_plugins.keys())}")
                logger.debug(f"Complete allowlist contents: {self.allowed_plugins}")

        except Exception as e:
            logger.error(f"Failed to load plugin security configuration: {e}")
            self.allowed_plugins = None
            self.allowlist_load_failed = True

    def discover_plugins(self) -> None:
        """Discover and load all allowed plugins"""
        logger.debug("Plugin discovery started")

        # Load from entry points
        self._load_entry_point_plugins()

        # Load from filesystem (if enabled in dev mode)
        self._load_filesystem_plugins()

        if len(self.plugins) == 0:
            logger.info("No plugins discovered at entry points.")
        else:
            # Register capabilities from all loaded plugins
            for plugin_name, plugin in self.plugins.items():
                try:
                    self._register_plugin(plugin_name, plugin)
                except Exception as e:
                    logger.error(f"Failed to register plugin {plugin_name}: {e}", exc_info=True)

    def _load_entry_point_plugins(self) -> None:
        """Load plugins from Python entry points"""
        try:
            # Get all entry points in the agentup.plugins group
            entry_points = importlib.metadata.entry_points()

            # Handle different Python versions
            if hasattr(entry_points, "select"):
                # Python 3.10+
                plugin_entries = entry_points.select(group="agentup.plugins")
            else:
                # Python 3.9
                plugin_entries = entry_points.get("agentup.plugins", [])

            if len(list(plugin_entries)) == 0:
                logger.debug("No plugins found in entry points")
                return

            for entry_point in plugin_entries:
                try:
                    # Check if plugin is allowed
                    if not self._is_plugin_allowed(entry_point.name, entry_point.dist):
                        logger.warning(f"Plugin '{entry_point.name}' not in allowlist, skipping")
                        continue

                    logger.debug(f"Loading plugin: {entry_point.name}")

                    # Load plugin class
                    plugin_class = entry_point.load()

                    # Validate it's a Plugin subclass
                    if not issubclass(plugin_class, Plugin):
                        logger.error(f"Plugin {entry_point.name} does not inherit from Plugin base class")
                        continue

                    # Instantiate plugin
                    plugin_instance = plugin_class()

                    # Register the plugin
                    self._register_plugin(entry_point.name, plugin_instance, entry_point)

                except Exception as e:
                    logger.error(f"Failed to load plugin {entry_point.name}: {e}", exc_info=True)

                    # Track failed plugin
                    self.plugin_definitions[entry_point.name] = PluginDefinition(
                        name=entry_point.name,
                        version="0.0.0",
                        status=PluginStatus.ERROR,
                        error=str(e),
                        entry_point=str(entry_point),
                    )

        except Exception as e:
            logger.error(f"Error loading entry point plugins: {e}")

    def _load_filesystem_plugins(self) -> None:
        """Load plugins from filesystem (development mode only)"""
        try:
            config = self.config
            dev_config = config.get("development", {})

            if not dev_config.get("enabled", False):
                return

            fs_config = dev_config.get("filesystem_plugins", {})
            if not fs_config.get("enabled", False):
                return

            logger.warning("DEVELOPMENT MODE: Loading plugins from filesystem")

            allowed_dirs = fs_config.get("allowed_directories", ["~/.agentup/plugins"])

            for dir_path in allowed_dirs:
                expanded_path = Path(dir_path).expanduser()

                if not expanded_path.exists():
                    logger.debug(f"Plugin directory not found: {expanded_path}")
                    continue

                logger.info(f"Loading filesystem plugins from: {expanded_path}")

                for plugin_dir in expanded_path.iterdir():
                    if plugin_dir.is_dir():
                        try:
                            self._load_filesystem_plugin(plugin_dir)
                        except Exception as e:
                            logger.error(f"Failed to load filesystem plugin from {plugin_dir}: {e}")

        except Exception as e:
            logger.error(f"Error loading filesystem plugins: {e}")

    def _load_filesystem_plugin(self, plugin_dir: Path) -> None:
        """Load a single plugin from filesystem directory"""
        plugin_name = f"fs_{plugin_dir.name}"

        # Look for plugin entry file
        entry_file = None
        if (plugin_dir / "plugin.py").exists():
            entry_file = plugin_dir / "plugin.py"
        elif (plugin_dir / "__init__.py").exists():
            entry_file = plugin_dir / "__init__.py"
        else:
            logger.warning(f"No plugin.py or __init__.py found in {plugin_dir}")
            return

        # Load module
        spec = importlib.util.spec_from_file_location(plugin_name, entry_file)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load plugin from {entry_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_name] = module
        spec.loader.exec_module(module)

        # Find Plugin class
        plugin_class = None
        for _name, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, Plugin) and obj != Plugin:
                plugin_class = obj
                break

        if plugin_class is None:
            logger.warning(f"No Plugin subclass found in {entry_file}")
            return

        # Instantiate and register
        plugin_instance = plugin_class()
        self._register_plugin(plugin_name, plugin_instance, None, source="filesystem", path=str(plugin_dir))

        logger.info(f"Loaded filesystem plugin '{plugin_name}' from {plugin_dir}")

    def _is_plugin_allowed(self, package_name: str, dist) -> bool:
        """Enhanced plugin security check with multiple modes and validation"""
        # Fail-secure: deny if security config failed to load
        if self.allowlist_load_failed:
            logger.warning(f"Plugin security config loading failed, denying plugin '{package_name}'")
            return False

        # Check blocked list first (applies to all modes)
        if package_name in self.blocked_plugins:
            logger.warning(f"Plugin '{package_name}' is explicitly blocked")
            return False

        # Permissive mode: allow everything except blocked
        if self.security_mode == "permissive":
            return True

        # Allowlist/Configured modes: require explicit permission
        if self.allowed_plugins is None:
            logger.warning(f"No plugin allowlist configured, denying plugin '{package_name}'")
            return False

        if not self.allowed_plugins:
            # Explicit empty allowlist means no plugins allowed
            logger.debug(f"Empty plugin allowlist, denying plugin '{package_name}'")
            return False

        # Check if package name is in allowlist (now keyed by package names)
        if package_name not in self.allowed_plugins:
            logger.debug(f"Plugin '{package_name}' not in allowlist (mode: {self.security_mode})")
            return False

        allowed_config = self.allowed_plugins[package_name]

        # Check package name matches (redundant now but kept for safety)
        expected_package = allowed_config.get("package")
        if expected_package and dist:
            actual_package = dist.name
            if actual_package != expected_package:
                logger.warning(
                    f"Plugin {package_name} package mismatch: expected {expected_package}, got {actual_package}"
                )
                return False

        # Check version constraints if specified
        if dist:
            version = dist.version
            min_version = allowed_config.get("min_version")
            max_version = allowed_config.get("max_version")

            if min_version and not self._version_satisfies(version, f">={min_version}"):
                logger.warning(f"Plugin {package_name} version {version} below minimum {min_version}")
                return False

            if max_version and not self._version_satisfies(version, f"<={max_version}"):
                logger.warning(f"Plugin {package_name} version {version} above maximum {max_version}")
                return False

        return True

    def _discover_plugin_name_for_package(self, package_name: str) -> str | None:
        """Discover the actual plugin name (entry point name) for a given package name."""
        try:
            import importlib.metadata as metadata

            # Look for the package in installed distributions
            for dist in metadata.distributions():
                if dist.name == package_name:
                    # Check if this package has agentup plugin entry points
                    entry_points = dist.entry_points
                    if hasattr(entry_points, "select"):
                        plugin_entries = entry_points.select(group="agentup.plugins")
                    else:
                        plugin_entries = entry_points.get("agentup.plugins", [])

                    # Return the first plugin entry point name we find
                    for entry_point in plugin_entries:
                        return entry_point.name

        except Exception as e:
            logger.debug(f"Error discovering plugin name for {package_name}: {e}")

        return None

    def _register_plugin(
        self,
        plugin_name: str,
        plugin_instance: Plugin,
        entry_point=None,
        source: str = "entry_point",
        path: str | None = None,
    ) -> None:
        """Register a plugin instance"""
        try:
            # Store plugin instance
            self.plugins[plugin_name] = plugin_instance

            # Get plugin capabilities
            capability_definitions = plugin_instance.get_capability_definitions()

            # Register each capability
            for cap_def in capability_definitions:
                capability_meta = plugin_instance._capabilities[cap_def.id]
                self.capabilities[cap_def.id] = capability_meta
                self.capability_to_plugin[cap_def.id] = plugin_name

                logger.debug(f"Registered capability '{cap_def.id}' from plugin '{plugin_name}'")

            # Create plugin definition
            version = "1.0.0"  # Default version
            if entry_point and entry_point.dist:
                version = entry_point.dist.version

            plugin_def = PluginDefinition(
                name=plugin_name,
                version=version,
                status=PluginStatus.LOADED,
                entry_point=str(entry_point) if entry_point else None,
                module_name=plugin_instance.__class__.__module__,
                metadata={
                    "source": source,
                    "path": path,
                    "class_name": plugin_instance.__class__.__name__,
                    "capability_count": len(capability_definitions),
                },
            )

            self.plugin_definitions[plugin_name] = plugin_def

            logger.info(f"Registered plugin '{plugin_name}' with {len(capability_definitions)} capabilities")

        except Exception as e:
            logger.error(f"Failed to register plugin {plugin_name}: {e}")

            # Remove plugin from plugins dict since registration failed
            if plugin_name in self.plugins:
                del self.plugins[plugin_name]

            # Track failed registration
            self.plugin_definitions[plugin_name] = PluginDefinition(
                name=plugin_name, version="0.0.0", status=PluginStatus.ERROR, error=str(e)
            )

    # === Plugin Execution Interface ===

    async def execute_capability(self, capability_id: str, context: CapabilityContext) -> CapabilityResult:
        """Execute a capability by ID"""
        if capability_id not in self.capabilities:
            return CapabilityResult(
                content=f"Capability '{capability_id}' not found",
                success=False,
                error="Capability not found",
            )

        plugin_name = self.capability_to_plugin[capability_id]
        plugin = self.plugins[plugin_name]

        try:
            return await plugin.execute_capability(capability_id, context)
        except Exception as e:
            logger.error(f"Failed to execute capability {capability_id}: {e}", exc_info=True)
            return CapabilityResult(content=f"Capability execution failed: {str(e)}", success=False, error=str(e))

    def can_handle_task(self, capability_id: str, context: CapabilityContext) -> bool | float:
        """Check if a capability can handle a task"""
        if capability_id not in self.capability_to_plugin:
            return False

        plugin_name = self.capability_to_plugin[capability_id]
        plugin = self.plugins[plugin_name]

        try:
            return plugin.can_handle_task(capability_id, context)
        except Exception as e:
            logger.error(f"Error checking if capability {capability_id} can handle task: {e}")
            return False

    def get_ai_functions(self, capability_id: str | None = None) -> list[AIFunction]:
        """Get AI functions from all plugins or a specific capability"""
        ai_functions = []

        if capability_id:
            # Get AI functions for specific capability
            if capability_id not in self.capability_to_plugin:
                return []

            plugin_name = self.capability_to_plugin[capability_id]
            plugin = self.plugins[plugin_name]
            ai_functions.extend(plugin.get_ai_functions(capability_id))
        else:
            # Get AI functions from all plugins
            for plugin in self.plugins.values():
                ai_functions.extend(plugin.get_ai_functions())

        return ai_functions

    def validate_config(self, capability_id: str, config: dict) -> PluginValidationResult:
        """Validate configuration for a capability"""
        if capability_id not in self.capabilities:
            return PluginValidationResult(valid=False, errors=[f"Capability '{capability_id}' not found"])

        capability_meta = self.capabilities[capability_id]

        # Use JSON schema validation if config_schema is provided
        if capability_meta.config_schema:
            try:
                import jsonschema

                jsonschema.validate(config, capability_meta.config_schema)
                return PluginValidationResult(valid=True)
            except ImportError:
                logger.warning("jsonschema not available for config validation")
                return PluginValidationResult(valid=True, warnings=["JSON schema validation unavailable"])
            except jsonschema.ValidationError as e:
                return PluginValidationResult(valid=False, errors=[str(e)])

        # No schema provided, assume valid
        return PluginValidationResult(valid=True)

    def configure_services(self, services: dict) -> None:
        """Configure services for all plugins"""
        for plugin_name, plugin in self.plugins.items():
            try:
                plugin.configure_services(services)
            except Exception as e:
                logger.error(f"Failed to configure services for plugin {plugin_name}: {e}")

    def configure_plugin(self, plugin_name: str, config: dict) -> None:
        """Configure a specific plugin"""
        if plugin_name in self.plugins:
            try:
                self.plugins[plugin_name].configure(config)
                logger.debug(f"Configured plugin {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to configure plugin {plugin_name}: {e}")

    # === Discovery and Information ===

    def get_capability(self, capability_id: str) -> CapabilityDefinition | None:
        """Get capability definition by ID"""
        if capability_id not in self.capability_to_plugin:
            return None

        plugin_name = self.capability_to_plugin[capability_id]
        plugin = self.plugins[plugin_name]

        for cap_def in plugin.get_capability_definitions():
            if cap_def.id == capability_id:
                return cap_def

        return None

    def list_capabilities(self) -> list[CapabilityDefinition]:
        """Get all capability definitions"""
        all_capabilities = []
        for plugin in self.plugins.values():
            all_capabilities.extend(plugin.get_capability_definitions())
        return all_capabilities

    def list_plugins(self) -> list[PluginDefinition]:
        """Get all plugin definitions"""
        return list(self.plugin_definitions.values())

    def get_plugin(self, plugin_name: str) -> Plugin | None:
        """Get plugin instance by name"""
        return self.plugins.get(plugin_name)

    def find_capabilities_for_task(self, context: CapabilityContext) -> list[tuple[str, float]]:
        """Find capabilities that can handle a task, sorted by confidence"""
        candidates = []

        for capability_id in self.capabilities.keys():
            confidence = self.can_handle_task(capability_id, context)
            if confidence:
                # Convert boolean True to 1.0
                if confidence is True:
                    confidence = 1.0
                elif confidence is False:
                    continue

                candidates.append((capability_id, float(confidence)))

        # Sort by confidence (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def discover_all_available_plugins(self) -> list[dict]:
        """Discover all available plugins regardless of allowlist for listing purposes"""
        available_plugins = []

        try:
            # Get all entry points in the agentup.plugins group
            entry_points = importlib.metadata.entry_points()

            # Handle different Python versions
            if hasattr(entry_points, "select"):
                # Python 3.10+
                plugin_entries = entry_points.select(group="agentup.plugins")
            else:
                # Python 3.9
                plugin_entries = entry_points.get("agentup.plugins", [])

            for entry_point in plugin_entries:
                try:
                    # Get basic plugin info without loading the plugin
                    plugin_info = {
                        "name": entry_point.name,
                        "version": entry_point.dist.version if entry_point.dist else "unknown",
                        "package": entry_point.dist.name if entry_point.dist else "unknown",
                        "module": entry_point.value.split(":")[0],
                        "class": entry_point.value.split(":")[1] if ":" in entry_point.value else "unknown",
                        "entry_point": str(entry_point),
                        "status": "available",
                        "loaded": entry_point.name in self.plugins,
                        "configured": entry_point.name in self.allowed_plugins,
                    }

                    # If already loaded, get additional info
                    if entry_point.name in self.plugins:
                        plugin_info["status"] = "loaded"
                        plugin_def = self.plugin_definitions.get(entry_point.name)
                        if plugin_def:
                            plugin_info["status"] = plugin_def.status.value
                            plugin_info["error"] = plugin_def.error

                    available_plugins.append(plugin_info)

                except Exception as e:
                    # Still include failed plugins in the list
                    available_plugins.append(
                        {
                            "name": entry_point.name,
                            "version": "unknown",
                            "package": entry_point.dist.name if entry_point.dist else "unknown",
                            "entry_point": str(entry_point),
                            "status": "error",
                            "error": str(e),
                            "loaded": False,
                            "configured": False,
                        }
                    )

        except Exception as e:
            logger.error(f"Error discovering available plugins: {e}")

        return available_plugins

    async def get_health_status(self) -> dict:
        """Get health status of all plugins"""
        health = {
            "total_plugins": len(self.plugins),
            "total_capabilities": len(self.capabilities),
            "plugin_status": {},
        }

        for plugin_name, plugin in self.plugins.items():
            try:
                plugin_health = await plugin.get_health_status()
                health["plugin_status"][plugin_name] = plugin_health
            except Exception as e:
                health["plugin_status"][plugin_name] = {"status": "error", "error": str(e)}

        return health

    def validate_plugin_config(self, plugin_config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate plugin configuration for security issues"""
        issues = []

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

    def _version_satisfies(self, version: str, constraint: str) -> bool:
        """Check if version satisfies constraint using packaging library"""
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

    def get_security_report(self, plugin_name: str) -> dict[str, Any]:
        """Generate security report for a plugin"""
        report = {
            "plugin_name": plugin_name,
            "security_mode": self.security_mode,
            "allowed": False,
            "reason": "",
            "security_level": "unknown",
        }

        # Check if plugin is loaded
        if plugin_name in self.plugins:
            report["loaded"] = True
            plugin_def = self.plugin_definitions.get(plugin_name)
            if plugin_def:
                report["status"] = plugin_def.status.value
        else:
            report["loaded"] = False

        # Check allowlist status
        if plugin_name in self.blocked_plugins:
            report["allowed"] = False
            report["reason"] = "Plugin is explicitly blocked"
        elif self.security_mode == "permissive":
            report["allowed"] = True
            report["reason"] = "Permissive mode allows all non-blocked plugins"
            report["security_level"] = "permissive"
        elif self.allowed_plugins and plugin_name in self.allowed_plugins:
            report["allowed"] = True
            report["reason"] = f"Plugin allowed in {self.security_mode} mode"
            config = self.allowed_plugins[plugin_name]
            if config.get("verified"):
                report["security_level"] = "verified"
            else:
                report["security_level"] = "configured"
        else:
            report["allowed"] = False
            report["reason"] = f"Plugin not allowed in {self.security_mode} mode"

        return report


# Global plugin registry instance
_plugin_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry instance"""
    global _plugin_registry
    if _plugin_registry is None:
        # Try to load configuration for the plugin registry
        config = None
        try:
            from agent.config import Config

            config = Config.model_dump()
        except ImportError:
            logger.debug("Could not load configuration for plugin registry")

        _plugin_registry = PluginRegistry(config)
        _plugin_registry.discover_plugins()

    return _plugin_registry
