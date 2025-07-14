"""Configuration management service with singleton pattern and caching."""

from typing import Any, Optional

import structlog


class ConfigurationManager:
    """Singleton configuration manager with caching.

    This class provides a centralized, cached access to application configuration,
    eliminating the need for repeated load_config() calls throughout the codebase.
    """

    _instance: Optional["ConfigurationManager"] = None
    _config: dict[str, Any] | None = None

    def __new__(cls):
        """Ensure only one instance of ConfigurationManager exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logger = structlog.get_logger(__name__)
        return cls._instance

    @property
    def config(self) -> dict[str, Any]:
        """Get the application configuration with caching.

        Returns:
            Dictionary containing the full application configuration
        """
        if self._config is None:
            self.logger.debug("Loading configuration for the first time")
            from agent.config import load_config

            self._config = load_config(configure_logging=False)
            self.logger.info("Configuration loaded successfully")
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key (supports nested keys with dot notation)
            default: Default value if key not found

        Returns:
            Configuration value or default

        Examples:
            >>> config.get("agent.name", "DefaultAgent")
            >>> config.get("plugins", [])
        """
        # Support nested key access with dot notation
        if "." in key:
            keys = key.split(".")
            value = self.config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                    if value is None:
                        return default
                else:
                    return default
            return value

        return self.config.get(key, default)

    def reload(self) -> None:
        """Force reload configuration.

        This clears the cache and forces a fresh load on next access.
        Useful for testing or when configuration changes at runtime.
        """
        self.logger.info("Reloading configuration")
        self._config = None

    def update(self, updates: dict[str, Any]) -> None:
        """Update configuration values.

        Args:
            updates: Dictionary of configuration updates

        Note:
            This only updates the in-memory configuration and
            does not persist changes to disk.
        """
        if self._config is None:
            _ = self.config  # Force load

        self._config.update(updates)
        self.logger.debug(f"Configuration updated with keys: {list(updates.keys())}")

    def get_agent_info(self) -> dict[str, str]:
        """Get agent information from configuration.

        Returns:
            Dictionary with agent name, version, and description
        """
        agent_config = self.get("agent", {})
        return {
            "name": agent_config.get("name", "Agent"),
            "version": agent_config.get("version", "0.1.0"),
            "description": agent_config.get("description", "AgentUp Agent"),
        }

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled in configuration.

        Args:
            feature: Feature name to check

        Returns:
            True if feature is enabled, False otherwise
        """
        # Check common feature patterns
        if feature == "security":
            return self.get("security.enabled", False)
        elif feature == "mcp":
            return self.get("mcp.enabled", False)
        elif feature == "state_management":
            return self.get("state_management.enabled", False)
        elif feature == "plugins":
            plugins_config = self.get("plugins", {})
            if isinstance(plugins_config, dict):
                return plugins_config.get("enabled", True)
            elif isinstance(plugins_config, list):
                return bool(plugins_config)
            return False

        # Generic feature check
        return self.get(f"{feature}.enabled", False)
