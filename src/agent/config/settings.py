import os
from functools import cache, lru_cache
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..types import ConfigDict as ConfigDictType
from ..types import ModulePath, ServiceName, Version
from .logging import configure_logging_from_config
from .model import (
    APIConfig,
    LoggingConfig,
    MCPConfig,
    MiddlewareConfig,
    PluginConfig,
    SecurityConfig,
    ServiceConfig,
)
from .yaml_source import YamlConfigSettingsSource


class Settings(BaseSettings):
    """
    Global application settings with support for YAML files and environment variables.

    Configuration is loaded in the following order (later sources override earlier ones):
    1. Default values defined in this class
    2. Values from agentup.yml (or file specified by AGENT_CONFIG_PATH)
    3. Environment variables with AGENTUP_ prefix

    Environment variables use double underscore for nested values:
    - AGENTUP_API__HOST sets api.host
    - AGENTUP_LOGGING__LEVEL sets logging.level
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENTUP_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown fields
        validate_assignment=True,
        populate_by_name=True,  # Allow using field name or alias
    )

    # Basic agent information
    project_name: Annotated[str, Field(alias="name")] = "AgentUp"
    description: str = "AI agent powered by AgentUp"
    version: Version = "1.0.0"

    # Environment
    environment: str = Field("development", pattern="^(development|staging|production)$")

    # Module paths for dynamic loading
    dispatcher_path: ModulePath | None = None
    services_enabled: bool = True
    services_init_path: ModulePath | None = None

    # MCP integration
    mcp_enabled: bool = False
    mcp_init_path: ModulePath | None = None
    mcp_shutdown_path: ModulePath | None = None

    # Configuration sections
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    plugins: list[PluginConfig] = Field(default_factory=list)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    # AI configuration
    ai: dict[str, Any] = Field(default_factory=dict)
    ai_provider: dict[str, Any] = Field(default_factory=dict)

    # Services configuration
    services: dict[ServiceName, ServiceConfig] = Field(default_factory=dict)

    # Custom configuration sections
    custom: ConfigDictType = Field(default_factory=dict)

    # Push notifications
    push_notifications: dict[str, Any] = Field(default_factory=dict)

    # State management
    state_management: dict[str, Any] = Field(default_factory=dict)

    # Development settings
    development: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        # Load .env file if it exists
        env_file = Path.cwd() / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        else:
            # Check parent directory (for development)
            parent_env = Path.cwd().parent / ".env"
            if parent_env.exists():
                load_dotenv(parent_env)

        # Initialize settings
        super().__init__(**kwargs)

        # Configure logging immediately after settings are loaded
        self._configure_logging()

    def _configure_logging(self) -> None:
        try:
            # Use the logging configuration
            logging_config = self.logging.model_dump() if hasattr(self.logging, "model_dump") else dict(self.logging)
            configure_logging_from_config({"logging": logging_config})
        except Exception:
            # Fallback to basic logging if configuration fails
            import logging

            logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Customize settings sources to add YAML support.

        The order here determines priority (later sources override earlier ones):
        1. init_settings (constructor arguments)
        2. yaml_settings (from agentup.yml)
        3. env_settings (environment variables) - HIGHEST PRIORITY
        """
        yaml_file = os.getenv("AGENT_CONFIG_PATH", "agentup.yml")
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file),
            file_secret_settings,
        )

    @property
    def name(self) -> str:
        return self.project_name

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def enabled_services(self) -> list[str]:
        return [name for name, config in self.services.items() if config.enabled]

    @property
    def security_enabled(self) -> bool:
        return self.security.enabled

    @property
    def full_name(self) -> str:
        return f"{self.project_name} v{self.version}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key with dot notation support.

        Args:
            key: Configuration key (supports dot notation like "api.host")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Support nested key access with dot notation
        if "." in key:
            keys = key.split(".")
            value = self
            for k in keys:
                if hasattr(value, k):
                    value = getattr(value, k)
                else:
                    return default
            return value

        # Simple attribute access
        return getattr(self, key, default)

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """
        Export configuration as dictionary.
        """
        return super().model_dump(**kwargs)


@lru_cache
def get_settings() -> Settings:
    """
    Get the cached global settings instance.

    This function ensures settings are loaded only once and cached
    for the lifetime of the application.
    """
    return Settings()


# Create global Config instance only when accessed
# This avoids loading configuration when importing the module


@cache
def get_config() -> Settings:
    """Get the global configuration instance, loading it if necessary."""
    return get_settings()


# For backward compatibility, provide Config as a property-like access
class ConfigProxy:
    def __getattr__(self, name):
        return getattr(get_config(), name)

    def __getitem__(self, key):
        return get_config()[key]

    def get(self, key, default=None):
        return get_config().get(key, default)


Config = ConfigProxy()
