from typing import Any

from .base import Service
from .capabilities import CapabilityRegistry
from .config import ConfigurationManager


class PluginService(Service):
    """
    Plugin management service.

    This service handles:
    - Plugin discovery and loading
    - Capability registration from plugins
    - Plugin lifecycle management
    """

    def __init__(self, config_manager: ConfigurationManager, capability_registry: CapabilityRegistry):
        """Initialize the plugin service.

        Args:
            config_manager: Configuration manager instance
            capability_registry: Registry for plugin capabilities
        """
        super().__init__(config_manager)
        self.capabilities = capability_registry
        self._loaded_plugins: dict[str, Any] = {}
        self._plugin_adapter = None

    async def initialize(self) -> None:
        self.logger.info("Initializing plugin service")

        plugin_config = self.config.get("plugins", {})

        # Check if plugins are enabled
        if not self._is_enabled(plugin_config):
            self.logger.info("Plugin system disabled")
            self._initialized = True
            return

        try:
            # Enable the plugin system
            from agent.plugins.integration import enable_plugin_system, get_plugin_adapter

            enable_plugin_system()
            self._plugin_adapter = get_plugin_adapter()

            if not self._plugin_adapter:
                self.logger.warning("Plugin adapter not available")
                self._initialized = True
                return

            # Load and register plugins
            await self._load_plugins(plugin_config)

            self._initialized = True
            self.logger.info(f"Plugin service initialized with {len(self._loaded_plugins)} plugins")

        except ImportError:
            self.logger.warning("Plugin system not available")
            self._initialized = True
        except Exception as e:
            self.logger.error(f"Failed to initialize plugin service: {e}")
            raise

    async def shutdown(self) -> None:
        self.logger.debug("Shutting down plugin service")

        # Unregister all plugin capabilities
        for plugin_id in self._loaded_plugins:
            self._unregister_plugin_capabilities(plugin_id)

        self._loaded_plugins.clear()
        self._plugin_adapter = None

    def _is_enabled(self, plugin_config: Any) -> bool:
        """
        Check if plugin system is enabled based on configuration.
        e.g.
        plugins:
          - plugin_id: my_plugin
            enabled: true
          - plugin_id: another_plugin
            enabled: false
        """
        if isinstance(plugin_config, dict):
            return plugin_config.get("enabled", True)
        elif isinstance(plugin_config, list):
            return bool(plugin_config)  # Enabled if not empty
        return True  # Default enabled

    async def _load_plugins(self, plugin_config: Any) -> None:
        plugins_to_load = []

        if isinstance(plugin_config, dict):
            plugins_to_load = plugin_config.get("plugins", [])
        elif isinstance(plugin_config, list):
            plugins_to_load = plugin_config

        for plugin_def in plugins_to_load:
            if isinstance(plugin_def, dict):
                await self._load_plugin(plugin_def)

    async def _load_plugin(self, plugin_def: dict[str, Any]) -> None:
        """Load a single plugin and register its capabilities.

        Args:
            plugin_def: Plugin definition from configuration
        """
        plugin_id = plugin_def.get("plugin_id")
        if not plugin_id:
            self.logger.warning("Plugin definition missing plugin_id, skipping")
            return

        self.logger.debug(f"Loading plugin: {plugin_id}")

        try:
            # Register plugin capabilities
            capabilities = plugin_def.get("capabilities", [])
            for cap_def in capabilities:
                if isinstance(cap_def, dict):
                    await self._register_capability(plugin_id, cap_def)

            self._loaded_plugins[plugin_id] = plugin_def
            self.logger.info(f"Loaded plugin: {plugin_id} with {len(capabilities)} capabilities")

        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_id}: {e}")

    async def _register_capability(self, plugin_id: str, cap_def: dict[str, Any]) -> None:
        """Register a plugin capability.

        Args:
            plugin_id: Plugin identifier
            cap_def: Capability definition
        """
        capability_id = cap_def.get("capability_id")
        if not capability_id:
            self.logger.warning(f"Capability definition for plugin {plugin_id} missing capability_id")
            return

        # Use the existing registration method from capabilities/executors.py
        try:
            from agent.capabilities.executors import register_plugin_capability

            # Prepare capability config
            capability_config = {
                "plugin_id": plugin_id,
                "capability_id": capability_id,
                "required_scopes": cap_def.get("required_scopes", []),
                "enabled": cap_def.get("enabled", True),
            }

            if capability_config["enabled"]:
                register_plugin_capability(capability_config)
                self.logger.debug(f"Registered capability {capability_id} from plugin {plugin_id}")
            else:
                self.logger.debug(f"Capability {capability_id} is disabled, skipping registration")

        except Exception as e:
            self.logger.error(f"Failed to register capability {capability_id}: {e}")

    def _unregister_plugin_capabilities(self, plugin_id: str) -> None:
        """Unregister all capabilities from a plugin.

        Args:
            plugin_id: Plugin to unregister
        """
        plugin_def = self._loaded_plugins.get(plugin_id, {})
        capabilities = plugin_def.get("capabilities", [])

        for cap_def in capabilities:
            if isinstance(cap_def, dict):
                capability_id = cap_def.get("capability_id")
                if capability_id:
                    self.capabilities.unregister(capability_id)
                    self.logger.debug(f"Unregistered capability {capability_id}")

    def get_loaded_plugins(self) -> dict[str, dict[str, Any]]:
        """Get information about all loaded plugins.

        Returns:
            Dictionary mapping plugin IDs to their definitions
        """
        return self._loaded_plugins.copy()

    def is_plugin_loaded(self, plugin_id: str) -> bool:
        """Check if a specific plugin is loaded.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if plugin is loaded, False otherwise
        """
        return plugin_id in self._loaded_plugins
