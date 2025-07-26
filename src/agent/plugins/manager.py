import importlib
import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pluggy
import structlog

from .hookspecs import CapabilitySpec
from .models import (
    AIFunction,
    CapabilityContext,
    CapabilityInfo,
    CapabilityResult,
    PluginInfo,
    PluginStatus,
    PluginValidationResult,
)

logger = structlog.get_logger(__name__)


class PluginManager:
    """Manages capability plugins for AgentUp."""

    # Hook implementation marker - shared across all plugin instances
    hookimpl = pluggy.HookimplMarker("agentup")

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the plugin manager.

        Args:
            config: Optional configuration dictionary. If not provided,
                   will be loaded when needed.
        """
        self.pm = pluggy.PluginManager("agentup")
        self.pm.add_hookspecs(CapabilitySpec)

        self.plugins: dict[str, PluginInfo] = {}
        self.capabilities: dict[str, CapabilityInfo] = {}
        self.capability_to_plugin: dict[str, str] = {}

        # Track plugin hooks for each capability
        self.capability_hooks: dict[str, Any] = {}

        # Store configuration
        self._config = config

    @property
    def config(self) -> dict[str, Any]:
        """Get configuration, loading if necessary."""
        if self._config is None:
            try:
                from agent.config import load_config

                self._config = load_config(configure_logging=False)
            except ImportError:
                logger.warning("Could not load configuration, using empty config")
                self._config = {}
        return self._config

    def discover_plugins(self) -> None:
        """Discover and load all available plugins."""
        logger.debug("Plugin discovery started")

        # Load from entry points
        self._load_entry_point_plugins()

        # Load from installed plugins directory
        self._load_installed_plugins()

        # Individual plugin discovery logs already show capability counts

    def _load_entry_point_plugins(self) -> None:
        """Load plugins from Python entry points."""
        try:
            # Get all entry points in the agentup.capabilities group
            entry_points = importlib.metadata.entry_points()

            # Handle different Python versions
            if hasattr(entry_points, "select"):
                # Python 3.10+
                capability_entries = entry_points.select(group="agentup.capabilities")
            else:
                # Python 3.9
                capability_entries = entry_points.get("agentup.capabilities", [])

            logger.debug(f"Discovered {len(capability_entries)} Plugins")

            for entry_point in capability_entries:
                try:
                    logger.debug(f"Querying: {entry_point.name}")
                    plugin_class = entry_point.load()
                    plugin_instance = plugin_class()

                    # Register the plugin
                    self.pm.register(plugin_instance, name=entry_point.name)

                    # Track plugin info
                    plugin_info = PluginInfo(
                        name=entry_point.name,
                        version=entry_point.dist.version
                        if entry_point.dist
                        else self._get_package_version(entry_point.name),
                        status=PluginStatus.LOADED,
                        entry_point=str(entry_point),
                        module_name=entry_point.module,
                    )
                    self.plugins[entry_point.name] = plugin_info

                    # Register the capability
                    capabilities_before = len(self.capabilities)
                    self._register_plugin_capability(entry_point.name, plugin_instance)
                    capabilities_after = len(self.capabilities)
                    capability_count = capabilities_after - capabilities_before

                    logger.info(f"Discovered plugin '{entry_point.name}' with {capability_count} capabilities")

                except Exception as e:
                    logger.error(f"Failed to load entry point {entry_point.name}: {e}")
                    self.plugins[entry_point.name] = PluginInfo(
                        name=entry_point.name, version="0.0.0", status=PluginStatus.ERROR, error=str(e)
                    )
        except Exception as e:
            logger.error(f"Error loading entry point plugins: {e}")

    def _should_load_filesystem_plugins(self) -> bool:
        """Check if filesystem plugin loading is enabled in development configuration.

        Returns:
            True if filesystem plugins should be loaded, False otherwise (default).
        """
        # Check if development mode is enabled
        dev_config = self.config.get("development", {})
        if not dev_config.get("enabled", False):
            return False

        # Check if filesystem plugins specifically enabled
        fs_plugins = dev_config.get("filesystem_plugins", {})
        if not fs_plugins.get("enabled", False):
            return False

        # Log security warning
        logger.warning(
            "SECURITY WARNING: Filesystem plugin loading is enabled. "
            "This allows execution of arbitrary code from the filesystem. "
            "Only use in trusted development environments!"
        )

        return True

    def _load_installed_plugins(self) -> None:
        """Load plugins from installed plugins directory only if explicitly enabled in config."""
        # Check if filesystem plugin loading is enabled
        if not self._should_load_filesystem_plugins():
            logger.debug("Filesystem based plugin loading disabled (secure default)")
            return

        # Get allowed directories from config
        dev_config = self.config.get("development", {})
        fs_config = dev_config.get("filesystem_plugins", {})
        allowed_dirs = fs_config.get("allowed_directories", ["~/.agentup/plugins"])

        for dir_path in allowed_dirs:
            # Expand user home directory
            expanded_path = Path(dir_path).expanduser()

            if not expanded_path.exists():
                logger.debug(f"Filesystem plugin directory not found: {expanded_path}")
                continue

            if not expanded_path.is_dir():
                logger.warning(f"Filesystem plugin path is not a directory: {expanded_path}")
                continue

            logger.info(f"Loading filesystem plugins from: {expanded_path}")

            for plugin_dir in expanded_path.iterdir():
                if plugin_dir.is_dir():
                    try:
                        # Check for plugin.py or __init__.py
                        if (plugin_dir / "plugin.py").exists():
                            self._load_installed_plugin(plugin_dir, "plugin.py")
                        elif (plugin_dir / "__init__.py").exists():
                            self._load_installed_plugin(plugin_dir, "__init__.py")
                    except Exception as e:
                        logger.error(f"Failed to load installed plugin from {plugin_dir}: {e}")

    def _load_installed_plugin(self, plugin_dir: Path, entry_file: str) -> None:
        """Load a single installed plugin."""
        plugin_name = f"installed_{plugin_dir.name}"
        plugin_file = plugin_dir / entry_file

        # Similar to local plugin loading
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load plugin from {plugin_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_name] = module
        spec.loader.exec_module(module)

        # Find plugin class
        plugin_class = getattr(module, "Plugin", None)
        if plugin_class is None:
            # Search for a class with our hooks
            for _, obj in vars(module).items():
                if isinstance(obj, type) and hasattr(obj, "register_capability"):
                    plugin_class = obj
                    break
            # Fallback to old interface
            if plugin_class is None:
                for _, obj in vars(module).items():
                    if isinstance(obj, type) and hasattr(obj, "register_skill"):
                        plugin_class = obj
                        break

        if plugin_class is None:
            raise ValueError(f"No plugin class found in {plugin_file}")

        # Instantiate and register
        plugin_instance = plugin_class()
        self.pm.register(plugin_instance, name=plugin_name)

        # Load metadata if available
        metadata = {}
        metadata_file = plugin_dir / "plugin.yaml"
        if metadata_file.exists():
            import yaml

            with open(metadata_file) as f:
                metadata = yaml.safe_load(f) or {}

        # Track plugin info
        plugin_info = PluginInfo(
            name=plugin_name,
            version=metadata.get("version", "1.0.0"),
            author=metadata.get("author"),
            description=metadata.get("description"),
            status=PluginStatus.LOADED,
            module_name=plugin_name,
            metadata={"source": "installed", "path": str(plugin_dir)},
        )
        self.plugins[plugin_name] = plugin_info

        # Register the capability
        capabilities_before = len(self.capabilities)
        self._register_plugin_capability(plugin_name, plugin_instance)
        capabilities_after = len(self.capabilities)
        capability_count = capabilities_after - capabilities_before

        logger.info(f"Discovered plugin '{plugin_name}' with {capability_count} capabilities")

    def _register_plugin_capability(self, plugin_name: str, plugin_instance: Any) -> None:
        """Register capability or capabilities from a plugin."""
        try:
            # Get capability info from entry points care of pluggy hooks
            results = self.pm.hook.register_capability()
            if not results:
                logger.warning(f"Plugin {plugin_name} did not return capability info")
                return

            # Find the result from this specific plugin
            plugin_result = None
            for result in results:
                # Check if this result came from our plugin
                if hasattr(plugin_instance, "register_capability"):
                    test_result = plugin_instance.register_capability()
                    if test_result == result:
                        plugin_result = result
                        break

            if plugin_result is None:
                plugin_result = results[-1]  # Fallback to last result

            # Handle both single capability and list of capabilities
            capabilities_to_register = []
            if isinstance(plugin_result, list):
                capabilities_to_register = plugin_result
            else:
                capabilities_to_register = [plugin_result]

            # Register each capability
            for capability_info in capabilities_to_register:
                # Check if this is a CapabilityInfo object (handle different import paths)
                if not (
                    hasattr(capability_info, "id")
                    and hasattr(capability_info, "name")
                    and hasattr(capability_info, "capabilities")
                    and type(capability_info).__name__ == "CapabilityInfo"
                ):
                    logger.error(f"Plugin {plugin_name} returned invalid capability info: {type(capability_info)}")
                    continue

                # Register the capability
                self.capabilities[capability_info.id] = capability_info
                self.capability_to_plugin[capability_info.id] = plugin_name
                self.capability_hooks[capability_info.id] = plugin_instance

                logger.debug(f"Discovered capability '{capability_info.id}' from plugin '{plugin_name}'")

        except Exception as e:
            logger.error(f"Failed to register capabilities from plugin {plugin_name}: {e}")

    def _get_package_version(self, package_name: str) -> str:
        """Get version of an installed package."""
        try:
            return importlib.metadata.version(package_name)
        except Exception:
            return "unknown"

    def get_capability(self, capability_id: str) -> CapabilityInfo | None:
        """Get capability information by ID."""
        return self.capabilities.get(capability_id)

    def list_capabilities(self) -> list[CapabilityInfo]:
        """List all available capabilities."""
        return list(self.capabilities.values())

    def list_plugins(self) -> list[PluginInfo]:
        """List all loaded plugins."""
        return list(self.plugins.values())

    def can_handle_task(self, capability_id: str, context: CapabilityContext) -> bool | float:
        """Check if a capability can handle a task."""
        if capability_id not in self.capability_hooks:
            return False

        plugin = self.capability_hooks[capability_id]
        if hasattr(plugin, "can_handle_task"):
            try:
                return plugin.can_handle_task(context)
            except Exception as e:
                logger.error(f"Error checking if capability {capability_id} can handle task: {e}")
                return False
        return True  # Default to true if no handler

    def execute_capability(self, capability_id: str, context: CapabilityContext) -> CapabilityResult:
        """Execute a capability."""
        if capability_id not in self.capability_hooks:
            return CapabilityResult(
                content=f"Capability '{capability_id}' not found", success=False, error="Capability not found"
            )

        plugin = self.capability_hooks[capability_id]
        try:
            # Add capability_id to context metadata so plugin knows which capability is being invoked
            context.metadata["capability_id"] = capability_id

            # Try new interface first
            if hasattr(plugin, "execute_capability"):
                return plugin.execute_capability(context)
            else:
                raise AttributeError("Plugin has no execute method")
        except Exception as e:
            logger.error(f"Error executing capability {capability_id}: {e}", exc_info=True)
            return CapabilityResult(content=f"Error executing capability: {str(e)}", success=False, error=str(e))

    def get_ai_functions(self, capability_id: str) -> list[AIFunction]:
        """Get AI functions from a capability."""
        if capability_id not in self.capability_hooks:
            return []

        plugin = self.capability_hooks[capability_id]
        if hasattr(plugin, "get_ai_functions"):
            try:
                # Pass capability_id to get capability-specific functions
                return plugin.get_ai_functions(capability_id=capability_id)
            except Exception as e:
                logger.error(f"Error getting AI functions from capability {capability_id}: {e}")
        return []

    def validate_config(self, capability_id: str, config: dict) -> PluginValidationResult:
        """Validate capability configuration."""
        if capability_id not in self.capability_hooks:
            return PluginValidationResult(valid=False, errors=[f"Capability '{capability_id}' not found"])

        plugin = self.capability_hooks[capability_id]
        if hasattr(plugin, "validate_config"):
            try:
                return plugin.validate_config(config)
            except Exception as e:
                logger.error(f"Error validating config for capability {capability_id}: {e}")
                return PluginValidationResult(valid=False, errors=[f"Validation error: {str(e)}"])
        return PluginValidationResult(valid=True)  # Default to valid if no validator

    def configure_services(self, capability_id: str, services: dict) -> None:
        """Configure services for a capability."""
        if capability_id not in self.capability_hooks:
            return

        plugin = self.capability_hooks[capability_id]
        if hasattr(plugin, "configure_services"):
            try:
                plugin.configure_services(services)
            except Exception as e:
                logger.error(f"Error configuring services for capability {capability_id}: {e}")

    def find_capabilities_for_task(self, context: CapabilityContext) -> list[tuple[str, float]]:
        """Find capabilities that can handle a task, sorted by confidence."""
        candidates = []

        for capability_id, _ in self.capabilities.items():
            confidence = self.can_handle_task(capability_id, context)
            if confidence:
                # Convert boolean True to 1.0
                if confidence is True:
                    confidence = 1.0
                elif confidence is False:
                    continue

                candidates.append((capability_id, float(confidence)))

        # Sort by confidence (highest first) and priority
        candidates.sort(key=lambda x: (x[1], self.capabilities[x[0]].priority), reverse=True)
        return candidates

    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (useful for development)."""
        try:
            # Unregister the old plugin
            if plugin_name in self.plugins:
                self.pm.unregister(name=plugin_name)

                # Remove associated capabilities
                capabilities_to_remove = [
                    capability_id for capability_id, pname in self.capability_to_plugin.items() if pname == plugin_name
                ]
                for capability_id in capabilities_to_remove:
                    del self.capabilities[capability_id]
                    del self.capability_to_plugin[capability_id]
                    del self.capability_hooks[capability_id]

            # Reload based on source
            plugin_info = self.plugins.get(plugin_name)
            if plugin_info and plugin_info.metadata.get("source") == "local":
                path = Path(plugin_info.metadata["path"])
                self._load_local_plugin(path)
                return True
            elif plugin_info and plugin_info.metadata.get("source") == "installed":
                path = Path(plugin_info.metadata["path"])
                entry_file = "plugin.py" if (path / "plugin.py").exists() else "__init__.py"
                self._load_installed_plugin(path, entry_file)
                return True
            else:
                # Entry point plugins can't be reloaded easily
                logger.warning(f"Cannot reload entry point plugin {plugin_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            return False


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        # Try to load configuration for the plugin manager
        config = None
        try:
            from agent.config import load_config

            config = load_config(configure_logging=False)
        except ImportError:
            logger.debug("Could not load configuration for plugin manager")

        _plugin_manager = PluginManager(config)
        _plugin_manager.discover_plugins()
    return _plugin_manager


# Export the hookimpl for use by plugins
def get_hookimpl():
    """Get the hook implementation marker for AgentUp plugins."""
    return PluginManager.hookimpl


# Backward compatibility
hookimpl = PluginManager.hookimpl
