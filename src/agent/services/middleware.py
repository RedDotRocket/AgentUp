"""Middleware management service for AgentUp framework."""

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
        """Initialize the middleware manager."""
        super().__init__(config_manager)
        self._global_config: list[dict[str, Any]] = []
        self._middleware_factories: dict[str, Callable] = {}

    async def initialize(self) -> None:
        """Initialize the middleware manager."""
        self.logger.info("Initializing middleware manager")

        # Load global middleware configuration
        self._global_config = self.config.get("middleware", [])

        # Register available middleware factories
        self._register_middleware_factories()

        self._initialized = True
        self.logger.info(f"Middleware manager initialized with {len(self._global_config)} global middleware")

    def _register_middleware_factories(self) -> None:
        """Register all available middleware factories."""
        try:
            from agent.middleware import cached, rate_limited, retryable, timed

            self._middleware_factories = {
                "timed": lambda params: timed(),
                "cached": lambda params: cached(**params) if params else cached(),
                "rate_limited": lambda params: rate_limited(**params) if params else rate_limited(),
                "retryable": lambda params: retryable(**params) if params else retryable(),
            }

            self.logger.debug(f"Registered {len(self._middleware_factories)} middleware types")
        except ImportError as e:
            self.logger.warning(f"Some middleware types not available: {e}")

    def get_global_config(self) -> list[dict[str, Any]]:
        """Get global middleware configuration."""
        return self._global_config.copy()

    def get_middleware_for_plugin(self, plugin_id: str) -> list[dict[str, Any]]:
        """Get middleware configuration for a specific plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            List of middleware configurations
        """
        # Check for plugin-specific override
        plugins = self.config.get("plugins", [])
        for plugin in plugins:
            if plugin.get("plugin_id") == plugin_id:
                if "middleware_override" in plugin:
                    self.logger.debug(f"Using middleware override for plugin {plugin_id}")
                    return plugin["middleware_override"]

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
