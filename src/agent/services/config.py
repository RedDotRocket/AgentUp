import warnings
from typing import Any, Optional

import structlog


class ConfigurationManager:
    """Singleton configuration manager with caching.

    .. deprecated:: 1.0
        ConfigurationManager is deprecated. Use `agent.config.get_settings()` or
        FastAPI dependency injection with `agent.dependencies.ConfigDep` instead.

        Migration Guide:
        - Replace `ConfigurationManager().config` with `get_settings().model_dump()`
        - Replace `ConfigurationManager().get("key")` with `get_settings().get("key")`
        - Replace `ConfigurationManager().is_feature_enabled("feature")` with direct Settings properties
        - Use FastAPI dependency injection: `async def endpoint(config: ConfigDep)`

    This class provides a centralized, cached access to application configuration,
    eliminating the need for repeated Config access throughout the codebase.
    """

    _instance: Optional["ConfigurationManager"] = None
    _config: dict[str, Any] | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logger = structlog.get_logger(__name__)
            # Issue deprecation warning
            warnings.warn(
                "ConfigurationManager is deprecated. Use agent.config.get_settings() or "
                "FastAPI dependency injection with agent.dependencies.ConfigDep instead. "
                "See class docstring for migration guide.",
                DeprecationWarning,
                stacklevel=2,
            )
        return cls._instance

    @property
    def config(self) -> dict[str, Any]:
        """Get the application configuration with caching.

        Returns:
            Dictionary containing the full application configuration
        """
        if self._config is None:
            self.logger.debug("Loading configuration for the first time")
            from agent.config import get_settings

            self._config = get_settings().model_dump()
            self.logger.info("Configuration loaded successfully")
        return self._config

    @property
    def pydantic_config(self):
        """Get the underlying Pydantic Settings model.

        Returns:
            Settings instance with full Pydantic validation and typed access
        """
        from agent.config import get_settings

        return get_settings()

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
            "version": agent_config.get("version", "0.5.1"),
            "description": agent_config.get("description", "AgentUp Agent"),
        }

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled in configuration.

        Args:
            feature: Feature name to check

        Returns:
            True if feature is enabled, False otherwise
        """
        # Use Pydantic models for proper validation
        from agent.config import get_settings

        settings = get_settings()

        # Check common feature patterns
        if feature == "security":
            return settings.security.enabled
        elif feature == "mcp":
            return settings.mcp.enabled
        elif feature == "state_management":
            return settings.state_management.get("enabled", False)
        elif feature == "plugins":
            # Plugins are enabled if any are configured
            return bool(settings.plugins)

        # Generic feature check - fallback to dict access
        return self.get(f"{feature}.enabled", False)
