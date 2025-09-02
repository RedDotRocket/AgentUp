from collections.abc import Callable
from typing import Any

from .base import Service
from .config import ConfigurationManager


class MiddlewareManager(Service):
    """Manages middleware configuration and application.

    This service centralizes middleware management, providing:
    - Global middleware configuration
    - Plugin-specific middleware overrides
    - Middleware factory methods
    """

    def __init__(self, config_manager: ConfigurationManager):
        super().__init__(config_manager)
        self._global_config: list[dict[str, Any]] = []
        self._middleware_factories: dict[str, Callable] = {}

    async def initialize(self) -> None:
        self.logger.info("Initializing middleware manager")

        # Load global middleware configuration
        middleware_config = getattr(self.config, "middleware", None)
        if middleware_config:
            # Convert Pydantic model to list for backwards compatibility
            self._global_config = [middleware_config.model_dump()] if hasattr(middleware_config, "model_dump") else []
        else:
            self._global_config = []

        # Register available middleware factories
        self._register_middleware_factories()

        self._initialized = True
        middleware_count = len(self._global_config) if self._global_config else 0
        self.logger.info(f"Middleware manager initialized with {middleware_count} global middleware")

    def _register_middleware_factories(self) -> None:
        try:
            from agent.middleware import cached, rate_limited, retryable, timed
            from agent.middleware.model import CacheConfig, RateLimitConfig, RetryConfig

            self._middleware_factories = {
                "timed": lambda params: timed(),
                "cached": lambda params: cached(CacheConfig(**params)) if params else cached(),
                "rate_limited": lambda params: rate_limited(RateLimitConfig(**params)) if params else rate_limited(),
                "retryable": lambda params: retryable(RetryConfig(**params)) if params else retryable(),
            }

            self.logger.debug(f"Registered {len(self._middleware_factories)} middleware types")
        except ImportError as e:
            self.logger.warning(f"Some middleware types not available: {e}")

    def get_global_config(self) -> list[dict[str, Any]]:
        return self._global_config.copy()

    def get_middleware_for_plugin(self, plugin_name: str) -> list[dict[str, Any]]:
        """Get middleware configuration for a specific plugin.

        Args:
            plugin_name: Plugin name/package identifier

        Returns:
            List of middleware configurations
        """
        # Check for plugin-specific override
        plugins = getattr(self.config, "plugins", None)
        if not plugins:
            plugins = {}

        plugins_dict = plugins.model_dump() if hasattr(plugins, "model_dump") else plugins

        if isinstance(plugins_dict, dict):
            # New dictionary-based structure
            for package_name, plugin_config in plugins_dict.items():
                plugin_name_attr = (
                    plugin_config.get("name")
                    if isinstance(plugin_config, dict)
                    else getattr(plugin_config, "name", None)
                )
                if package_name == plugin_name or plugin_name_attr == plugin_name:
                    override = (
                        plugin_config.get("plugin_override")
                        if isinstance(plugin_config, dict)
                        else getattr(plugin_config, "plugin_override", None)
                    )
                    if override:
                        self.logger.debug(f"Using plugin override for plugin {plugin_name}")
                        return override.model_dump() if hasattr(override, "model_dump") else override
        else:
            # Legacy list structure
            for plugin in plugins_dict:
                plugin_name_attr = plugin.get("name") if isinstance(plugin, dict) else getattr(plugin, "name", None)
                if plugin_name_attr == plugin_name:
                    override = (
                        plugin.get("plugin_override")
                        if isinstance(plugin, dict)
                        else getattr(plugin, "plugin_override", None)
                    )
                    if override:
                        self.logger.debug(f"Using plugin override for plugin {plugin_name}")
                        return override.model_dump() if hasattr(override, "model_dump") else override

        # Return global config
        return self.get_global_config()

    def create_middleware_stack(self, configs: list[dict[str, Any]]) -> Callable:
        """Create a middleware stack from configuration.

        Args:
            configs: List of middleware configurations

        Returns:
            Composed middleware function
        """
        try:
            from agent.middleware import with_middleware

            return with_middleware(configs)
        except ImportError:
            self.logger.warning("Middleware module not available")
            return lambda f: f  # Identity function as fallback
