"""
Plugin Configuration Resolver Service

This service resolves effective plugin configuration by merging:
1. Global defaults
2. Plugin-level overrides
3. Capability-level overrides

It provides a unified interface for security, middleware, and other systems
to get the effective configuration for any plugin or capability.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from .intent import CapabilityOverride, IntentConfig, PluginOverride

logger = structlog.get_logger(__name__)


class PluginConfigurationResolver:
    """
    Resolves effective plugin configuration from the unified configuration system.

    This service handles the merging of global defaults, plugin overrides, and
    capability overrides to provide the effective configuration for security,
    middleware, and other systems.
    """

    def __init__(self, intent_config: IntentConfig):
        """Initialize the resolver with the intent configuration."""
        self.intent_config = intent_config
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_clear = time.time()

    def _clear_expired_cache(self) -> None:
        """Clear expired cache entries."""
        current_time = time.time()
        if current_time - self._last_cache_clear > self._cache_ttl:
            self._cache.clear()
            self._last_cache_clear = current_time

    def get_plugin_override(self, package_name: str) -> PluginOverride:
        """Get the plugin override configuration for a package."""
        self._clear_expired_cache()

        cache_key = f"plugin_override:{package_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        plugin_config = self.intent_config.get_plugin_config(package_name)
        self._cache[cache_key] = plugin_config
        return plugin_config

    def get_capability_override(self, package_name: str, capability_id: str) -> CapabilityOverride:
        """Get the capability override configuration."""
        self._clear_expired_cache()

        cache_key = f"capability_override:{package_name}:{capability_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        plugin_override = self.get_plugin_override(package_name)
        capability_override = plugin_override.capabilities.get(capability_id)

        if capability_override is None:
            # Import here to avoid circular imports
            from .intent import CapabilityOverride

            capability_override = CapabilityOverride()

        self._cache[cache_key] = capability_override
        return capability_override

    def get_effective_scopes(
        self, package_name: str, capability_id: str, default_scopes: list[str] | None = None
    ) -> list[str]:
        """
        Get the effective required scopes for a capability.

        Precedence order:
        1. Capability-level scope override
        2. Plugin decorator scopes (default_scopes parameter)
        3. Empty list
        """
        self._clear_expired_cache()

        cache_key = f"effective_scopes:{package_name}:{capability_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        capability_override = self.get_capability_override(package_name, capability_id)

        # Use capability override if specified
        if capability_override.required_scopes:
            effective_scopes = capability_override.required_scopes
            logger.debug(
                f"Using capability scope override for {package_name}:{capability_id}",
                scopes=effective_scopes,
                source="capability_override",
            )
        # Otherwise use decorator defaults
        elif default_scopes:
            effective_scopes = default_scopes
            logger.debug(
                f"Using decorator default scopes for {package_name}:{capability_id}",
                scopes=effective_scopes,
                source="decorator_default",
            )
        else:
            effective_scopes = []
            logger.debug(f"No scopes configured for {package_name}:{capability_id}", source="empty_default")

        self._cache[cache_key] = effective_scopes
        return effective_scopes

    def get_effective_middleware(self, package_name: str, capability_id: str | None = None) -> list[dict[str, Any]]:
        """
        Get the effective middleware configuration.

        Precedence order:
        1. Capability-level middleware override (if capability_id provided)
        2. Plugin-level middleware override
        3. Global middleware defaults
        """
        self._clear_expired_cache()

        cache_key = f"effective_middleware:{package_name}:{capability_id or 'plugin'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        middleware_config = []

        plugin_override = self.get_plugin_override(package_name)

        # Start with plugin defaults
        plugin_middleware_defaults = self.intent_config.plugin_defaults.middleware
        for name, params in plugin_middleware_defaults.items():
            middleware_config.append({"name": name, "config": params.copy(), "source": "plugin_default"})

        # Apply plugin-level overrides
        for mw_override in plugin_override.plugin_override:
            # Check if this middleware already exists from plugin defaults
            existing_idx = None
            for i, existing_mw in enumerate(middleware_config):
                if existing_mw["name"] == mw_override.name:
                    existing_idx = i
                    break

            mw_config = {"name": mw_override.name, "config": mw_override.config.copy(), "source": "plugin_override"}

            if existing_idx is not None:
                # Replace existing middleware config
                middleware_config[existing_idx] = mw_config
            else:
                # Add new middleware
                middleware_config.append(mw_config)

        # Apply capability-level overrides if specified
        if capability_id:
            capability_override = self.get_capability_override(package_name, capability_id)

            for mw_override in capability_override.capability_override:
                # Check if this middleware already exists
                existing_idx = None
                for i, existing_mw in enumerate(middleware_config):
                    if existing_mw["name"] == mw_override.name:
                        existing_idx = i
                        break

                mw_config = {
                    "name": mw_override.name,
                    "config": mw_override.config.copy(),
                    "source": "capability_override",
                }

                if existing_idx is not None:
                    # Replace existing middleware config
                    middleware_config[existing_idx] = mw_config
                else:
                    # Add new middleware
                    middleware_config.append(mw_config)

        # Remove source information for compatibility with existing middleware system
        final_config = [{"name": mw["name"], "config": mw["config"]} for mw in middleware_config]

        logger.debug(
            f"Resolved effective middleware for {package_name}:{capability_id or 'plugin'}",
            middleware=final_config,
            sources=[mw["source"] for mw in middleware_config],
        )

        self._cache[cache_key] = final_config
        return final_config

    def is_capability_enabled(self, package_name: str, capability_id: str) -> bool:
        """Check if a capability is enabled based on configuration."""
        self._clear_expired_cache()

        cache_key = f"capability_enabled:{package_name}:{capability_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        plugin_override = self.get_plugin_override(package_name)

        # First check if the entire plugin is disabled
        if not plugin_override.enabled:
            self._cache[cache_key] = False
            return False

        # Then check capability-specific configuration
        capability_override = self.get_capability_override(package_name, capability_id)
        enabled = capability_override.enabled

        self._cache[cache_key] = enabled
        return enabled

    def get_plugin_config(self, package_name: str) -> dict[str, Any]:
        """Get plugin-specific configuration parameters."""
        self._clear_expired_cache()

        cache_key = f"plugin_config:{package_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        plugin_override = self.get_plugin_override(package_name)
        config = plugin_override.config.copy()

        self._cache[cache_key] = config
        return config

    def get_capability_config(self, package_name: str, capability_id: str) -> dict[str, Any]:
        """Get capability-specific configuration parameters."""
        self._clear_expired_cache()

        cache_key = f"capability_config:{package_name}:{capability_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        capability_override = self.get_capability_override(package_name, capability_id)
        config = capability_override.config.copy()

        self._cache[cache_key] = config
        return config

    def clear_cache(self) -> None:
        """Clear all cached configuration data."""
        self._cache.clear()
        self._last_cache_clear = time.time()
        logger.debug("Cleared plugin configuration resolver cache")


# Global resolver instance
_resolver: PluginConfigurationResolver | None = None


def get_plugin_resolver() -> PluginConfigurationResolver | None:
    """Get the global plugin configuration resolver."""
    return _resolver


def initialize_plugin_resolver(intent_config: IntentConfig) -> None:
    """Initialize the global plugin configuration resolver."""
    global _resolver
    _resolver = PluginConfigurationResolver(intent_config)
    logger.debug("Initialized plugin configuration resolver")


def clear_plugin_resolver() -> None:
    """Clear the global plugin configuration resolver."""
    global _resolver
    if _resolver:
        _resolver.clear_cache()
    _resolver = None
    logger.debug("Cleared global plugin configuration resolver")
