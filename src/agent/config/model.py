"""
Pydantic models for AgentUp configuration.

This module defines all configuration data structures using Pydantic models
for type safety and validation.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings

from ..types import ConfigDict as ConfigDictType
from ..types import FilePath, LogLevel, ModulePath, ServiceName, ServiceType, Version


class EnvironmentVariable(BaseModel):
    """Model for environment variable references."""

    name: str = Field(..., description="Environment variable name")
    default: str | None = Field(None, description="Default value if not set")
    required: bool = Field(True, description="Whether variable is required")

    @field_validator("name")
    @classmethod
    def validate_env_name(cls, v: str) -> str:
        """Validate environment variable name format."""
        if not v or not v.replace("_", "").isalnum():
            raise ValueError("Environment variable name must be alphanumeric with underscores")
        return v.upper()


class LogFormat(str, Enum):
    """Logging format options."""

    TEXT = "text"
    JSON = "json"


class LoggingConsoleConfig(BaseModel):
    """Console logging configuration."""

    enabled: bool = Field(True, description="Enable console logging")
    colors: bool = Field(True, description="Enable colored output")
    show_time: bool = Field(True, description="Show timestamps")
    show_level: bool = Field(True, description="Show log level")


class LoggingFileConfig(BaseModel):
    """File logging configuration."""

    enabled: bool = Field(False, description="Enable file logging")
    path: FilePath = Field("logs/agentup.log", description="Log file path")
    max_size: int = Field(10 * 1024 * 1024, description="Max file size in bytes")
    backup_count: int = Field(5, description="Number of backup files to keep")
    rotation: Literal["size", "time", "never"] = Field("size", description="Rotation strategy")


class LoggingConfig(BaseModel):
    """Comprehensive logging configuration."""

    enabled: bool = Field(True, description="Enable logging system")
    level: LogLevel = Field("INFO", description="Global log level")
    format: LogFormat = Field(LogFormat.TEXT, description="Log output format")

    # Output destinations
    console: LoggingConsoleConfig = Field(default_factory=LoggingConsoleConfig)
    file: LoggingFileConfig = Field(default_factory=LoggingFileConfig)

    # Advanced configuration
    correlation_id: bool = Field(True, description="Include correlation IDs")
    request_logging: bool = Field(True, description="Log HTTP requests")
    structured_data: bool = Field(False, description="Include structured metadata")

    # Module-specific log levels
    modules: dict[str, LogLevel] = Field(default_factory=dict)

    # Third-party integration
    uvicorn: dict[str, Any] = Field(
        default_factory=lambda: {
            "access_log": True,
            "disable_default_handlers": True,
            "use_colors": True,
        }
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level values."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if isinstance(v, str):
            v = v.upper()
            if v not in valid_levels:
                raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v

    @field_validator("modules")
    @classmethod
    def validate_module_log_levels(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate module log level values."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        for module, level in v.items():
            if isinstance(level, str):
                level = level.upper()
                if level not in valid_levels:
                    raise ValueError(f"Invalid log level for {module}: {level}. Must be one of {valid_levels}")
                v[module] = level
        return v


class ServiceConfig(BaseModel):
    """Base service configuration."""

    type: ServiceType = Field(..., description="Service type identifier")
    enabled: bool = Field(True, description="Whether service is enabled")
    init_path: ModulePath | None = Field(None, description="Custom initialization module path")
    settings: ConfigDictType = Field(default_factory=dict, description="Service-specific settings")
    priority: int = Field(50, description="Service initialization priority (lower = earlier)")

    # Health check configuration
    health_check_enabled: bool = Field(True, description="Enable health checks")
    health_check_interval: int = Field(30, description="Health check interval in seconds")

    # Retry configuration
    max_retries: int = Field(3, description="Max initialization retries")
    retry_delay: float = Field(1.0, description="Delay between retries in seconds")

    @field_validator("type")
    @classmethod
    def validate_service_type(cls, v: str) -> str:
        """Validate service type format."""
        if not v or not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Service type must be alphanumeric with hyphens/underscores")
        return v.lower()

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Validate priority range."""
        if not 0 <= v <= 100:
            raise ValueError("Priority must be between 0 and 100")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_high_priority(self) -> bool:
        """Check if service has high priority (early initialization)."""
        return self.priority <= 20

    @computed_field
    @property
    def is_resilient(self) -> bool:
        """Check if service has resilience features enabled."""
        return self.health_check_enabled and self.max_retries > 1

    @computed_field
    @property
    def initialization_score(self) -> float:
        """Calculate initialization reliability score (0.0 to 1.0)."""
        score = 0.5  # Base score

        # Health check contribution (0.0 to 0.3)
        if self.health_check_enabled:
            score += 0.2
            # Frequent health checks are better
            score += min(0.1, (60 - self.health_check_interval) / 60 * 0.1)

        # Retry configuration contribution (0.0 to 0.2)
        score += min(0.2, self.max_retries / 5 * 0.2)

        return min(1.0, score)


class MCPServerConfig(BaseModel):
    """MCP server configuration."""

    name: str = Field(..., description="Server name")
    type: Literal["stdio", "http"] = Field(..., description="Connection type")

    # For stdio type
    command: str | None = Field(None, description="Command to run for stdio server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_dir: FilePath | None = Field(None, description="Working directory")

    # For http type
    url: str | None = Field(None, description="HTTP server URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    timeout: int = Field(30, description="Request timeout in seconds")

    # Tool permissions
    tool_scopes: dict[str, list[str]] = Field(default_factory=dict, description="Tool name to required scopes mapping")
    allowed_tools: list[str] | None = Field(None, description="Allowed tools (None = all)")
    blocked_tools: list[str] = Field(default_factory=list, description="Blocked tools")

    @model_validator(mode="after")
    def validate_server_config(self) -> MCPServerConfig:
        """Validate server configuration based on type."""
        if self.type == "stdio":
            if not self.command:
                raise ValueError("command is required for stdio server")
        elif self.type == "http":
            if not self.url:
                raise ValueError("url is required for http server")
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("HTTP server URL must start with http:// or https://")
        return self


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""

    enabled: bool = Field(False, description="Enable MCP support")

    # Client configuration
    client_enabled: bool = Field(True, description="Enable MCP client")
    client_timeout: int = Field(30, description="Client timeout in seconds")
    client_retry_attempts: int = Field(3, description="Client retry attempts")

    # Server configuration
    server_enabled: bool = Field(False, description="Enable MCP server")
    server_host: str = Field("localhost", description="Server host")
    server_port: int = Field(8080, description="Server port")

    # Server configurations
    servers: list[MCPServerConfig] = Field(default_factory=list, description="MCP servers")

    @field_validator("server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class SecurityConfig(BaseModel):
    """Security configuration reference."""

    enabled: bool = Field(True, description="Enable security features")
    # Note: Detailed security config is in security/model.py to avoid circular imports


class PluginCapabilityConfig(BaseModel):
    """Plugin capability configuration."""

    capability_id: str = Field(..., description="Capability identifier")
    name: str | None = Field(None, description="Human-readable name")
    description: str | None = Field(None, description="Capability description")
    required_scopes: list[str] = Field(default_factory=list, description="Required scopes")
    enabled: bool = Field(True, description="Whether capability is enabled")
    config: ConfigDictType = Field(default_factory=dict, description="Capability-specific config")
    middleware_override: list[dict[str, Any]] | None = Field(None, description="Override middleware configuration")


class PluginConfig(BaseModel):
    """Individual plugin configuration."""

    plugin_id: str = Field(..., description="Plugin identifier")
    name: str | None = Field(None, description="Plugin name")
    description: str | None = Field(None, description="Plugin description")
    enabled: bool = Field(True, description="Whether plugin is enabled")
    version: Version | None = Field(None, description="Plugin version constraint")

    # Capability configuration
    capabilities: list[PluginCapabilityConfig] = Field(default_factory=list, description="Plugin capabilities")

    # Default settings applied to all capabilities
    default_scopes: list[str] = Field(default_factory=list, description="Default scopes")
    middleware: list[dict[str, Any]] | None = Field(None, description="Middleware configuration")
    config: ConfigDictType = Field(default_factory=dict, description="Plugin configuration")

    @field_validator("plugin_id")
    @classmethod
    def validate_plugin_id(cls, v: str) -> str:
        """Validate plugin ID format."""
        if not v or not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Plugin ID must be alphanumeric with hyphens, underscores, and dots")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def has_capabilities(self) -> bool:
        """Check if plugin has any capabilities defined."""
        return len(self.capabilities) > 0

    @computed_field
    @property
    def enabled_capabilities_count(self) -> int:
        """Count of enabled capabilities."""
        return sum(1 for cap in self.capabilities if cap.enabled)

    @computed_field
    @property
    def display_name(self) -> str:
        """Get display name (name or plugin_id as fallback)."""
        return self.name or self.plugin_id

    @computed_field
    @property
    def has_middleware(self) -> bool:
        """Check if plugin has middleware configuration."""
        return self.middleware is not None and len(self.middleware) > 0

    @computed_field
    @property
    def total_required_scopes(self) -> set[str]:
        """Get all required scopes (default + capability-specific)."""
        scopes = set(self.default_scopes)
        for cap in self.capabilities:
            scopes.update(cap.required_scopes)
        return scopes

    @computed_field
    @property
    def complexity_score(self) -> float:
        """Calculate plugin complexity score (0.0 to 1.0)."""
        score = 0.0

        # Capability count contribution (0.0 to 0.4)
        score += min(0.4, len(self.capabilities) / 10 * 0.4)

        # Middleware complexity (0.0 to 0.2)
        if self.has_middleware:
            score += min(0.2, len(self.middleware) / 5 * 0.2)

        # Scope count (0.0 to 0.2)
        total_scopes = len(self.total_required_scopes)
        score += min(0.2, total_scopes / 10 * 0.2)

        # Configuration complexity (0.0 to 0.2)
        config_size = len(str(self.config))
        score += min(0.2, config_size / 1000 * 0.2)

        return min(1.0, score)


class PluginsConfig(BaseModel):
    """Plugins system configuration."""

    enabled: bool = Field(True, description="Enable plugin system")

    # Plugin configurations
    plugins: list[PluginConfig] = Field(default_factory=list, description="Plugin configurations")


class MiddlewareConfig(BaseModel):
    """Middleware configuration."""

    enabled: bool = Field(True, description="Enable middleware system")

    # Rate limiting
    rate_limiting: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "requests_per_minute": 60, "burst_size": 10}
    )

    # Caching
    caching: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "backend": "memory", "default_ttl": 300, "max_size": 1000}
    )

    # Retry logic
    retry: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "max_attempts": 3, "initial_delay": 1.0, "max_delay": 60.0}
    )


class APIConfig(BaseModel):
    """API server configuration."""

    enabled: bool = Field(True, description="Enable API server")
    host: str = Field("127.0.0.1", description="Server host")
    port: int = Field(8000, description="Server port")

    # Server settings
    workers: int = Field(1, description="Number of workers")
    reload: bool = Field(False, description="Enable auto-reload")
    debug: bool = Field(False, description="Enable debug mode")

    # Request handling
    max_request_size: int = Field(16 * 1024 * 1024, description="Max request size in bytes")
    request_timeout: int = Field(30, description="Request timeout in seconds")
    keepalive_timeout: int = Field(5, description="Keep-alive timeout in seconds")

    # CORS settings
    cors_enabled: bool = Field(True, description="Enable CORS")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], description="Allowed origins")
    cors_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"], description="Allowed methods"
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """Validate worker count."""
        if not 1 <= v <= 32:
            raise ValueError("Workers must be between 1 and 32")
        return v


class AgentConfig(BaseModel):
    """Main agent configuration."""

    # agent: dict[str, Any] = Field(default_factory=dict, description="Agent metadata")
    # Basic agent information
    project_name: str = Field("AgentUp", description="Project name", alias="name")
    description: str = Field("AI agent powered by AgentUp", description="Agent description")
    version: Version = Field("1.0.0", description="Agent version")

    # Add property for backward compatibility
    @property
    def name(self) -> str:
        """Get project name (backward compatibility)."""
        return self.project_name

    # Module paths for dynamic loading
    dispatcher_path: ModulePath | None = Field(None, description="Function dispatcher module path")
    services_enabled: bool = Field(True, description="Enable services system")
    services_init_path: ModulePath | None = Field(None, description="Services initialization module path")

    # MCP integration
    mcp_enabled: bool = Field(False, description="Enable MCP integration")
    mcp_init_path: ModulePath | None = Field(None, description="MCP initialization module path")
    mcp_shutdown_path: ModulePath | None = Field(None, description="MCP shutdown module path")

    # Configuration sections
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    plugins: list[PluginConfig] = Field(default_factory=list, description="Plugin configurations")
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    # AI configuration
    ai: dict[str, Any] = Field(default_factory=dict, description="AI settings")
    ai_provider: dict[str, Any] = Field(default_factory=dict, description="AI provider configuration")
    # Services configuration
    services: dict[ServiceName, ServiceConfig] = Field(default_factory=dict, description="Service configurations")

    # Custom configuration sections
    custom: ConfigDictType = Field(default_factory=dict, description="Custom configuration")

    # Push Notification settings
    push_notifications: dict[str, Any] = Field(default_factory=dict, description="Push notifications config")
    # Environment-specific settings
    state_management: dict[str, Any] = Field(default_factory=dict, description="State management config")
    development: dict[str, Any] = Field(default_factory=dict, description="Development settings")

    environment: Literal["development", "staging", "production"] = Field(
        "development", description="Deployment environment"
    )

    model_config = ConfigDict(
        extra="forbid",  # Prevent unknown configuration fields
        validate_assignment=True,
        populate_by_name=True,  # Allow using both field name and alias
    )

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """Validate project name format."""
        if not v or len(v) > 100:
            raise ValueError("Project name must be 1-100 characters")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        import re

        if not re.match(r"^\d+\.\d+\.\d+(?:-[\w.-]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @computed_field
    @property
    def enabled_services(self) -> list[str]:
        """Get list of enabled service names."""
        return [name for name, config in self.services.items() if config.enabled]

    @computed_field
    @property
    def total_service_count(self) -> int:
        """Total number of configured services."""
        return len(self.services)

    @computed_field
    @property
    def security_enabled(self) -> bool:
        """Check if any security features are enabled."""
        return self.security.enabled

    @computed_field
    @property
    def full_name(self) -> str:
        """Get full agent name with version."""
        return f"{self.project_name} v{self.version}"

    @model_validator(mode="after")
    def validate_mcp_consistency(self) -> AgentConfig:
        """Ensure MCP configuration consistency."""
        if self.mcp_enabled:
            if not self.mcp.enabled:
                self.mcp = MCPConfig(enabled=True)
        return self


class ConfigurationSettings(BaseSettings):
    """Environment-based configuration settings."""

    # File paths
    CONFIG_FILE: FilePath = Field("agentup.yml", description="Main configuration file")
    CONFIG_DIR: FilePath = Field(".", description="Configuration directory")
    DATA_DIR: FilePath = Field("data/", description="Data directory")
    LOGS_DIR: FilePath = Field("logs/", description="Logs directory")
    PLUGINS_DIR: FilePath = Field("plugins/", description="Plugins directory")

    # Environment overrides
    ENVIRONMENT: str = Field("development", description="Deployment environment")
    DEBUG: bool = Field(False, description="Debug mode")
    LOG_LEVEL: LogLevel = Field("INFO", description="Global log level")

    # API settings
    API_HOST: str = Field("127.0.0.1", description="API server host")
    API_PORT: int = Field(8000, description="API server port")

    # Security settings
    SECRET_KEY: str | None = Field(None, description="Application secret key")

    model_config = ConfigDict(env_prefix="AGENTUP_", case_sensitive=True)

    def create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [self.DATA_DIR, self.LOGS_DIR, self.PLUGINS_DIR]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Utility function for environment variable expansion
def expand_env_vars(value: Any) -> Any:
    """Expand environment variables in configuration values."""
    if isinstance(value, str):
        # Handle ${VAR} and ${VAR:default} patterns
        import re

        def replace_env_var(match):
            var_spec = match.group(1)
            if ":" in var_spec:
                var_name, default = var_spec.split(":", 1)
            else:
                var_name, default = var_spec, None

            return os.getenv(var_name, default or match.group(0))

        return re.sub(r"\$\{([^}]+)\}", replace_env_var, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]

    return value


# Re-export key models
__all__ = [
    "AgentConfig",
    "ServiceConfig",
    "LoggingConfig",
    "APIConfig",
    "SecurityConfig",
    "PluginsConfig",
    "PluginConfig",
    "MiddlewareConfig",
    "MCPConfig",
    "ConfigurationSettings",
    "EnvironmentVariable",
    "expand_env_vars",
]
