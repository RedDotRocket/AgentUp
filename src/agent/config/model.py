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


class BaseAgent(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow",
    }

    agent_name: str = Field(description="The name of the agent.")
    description: str = Field(description="A brief description of the agent's purpose.")
    content_types: list[str] = Field(description="Supported content types.")


class EnvironmentVariable(BaseModel):
    name: str = Field(..., description="Environment variable name")
    default: str | None = Field(None, description="Default value if not set")
    required: bool = Field(True, description="Whether variable is required")

    @field_validator("name")
    @classmethod
    def validate_env_name(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum():
            raise ValueError("Environment variable name must be alphanumeric with underscores")
        return v.upper()


class LogFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


class LoggingConsoleConfig(BaseModel):
    enabled: bool = Field(True, description="Enable console logging")
    colors: bool = Field(True, description="Enable colored output")
    show_time: bool = Field(True, description="Show timestamps")
    show_level: bool = Field(True, description="Show log level")


class LoggingFileConfig(BaseModel):
    enabled: bool = Field(False, description="Enable file logging")
    path: FilePath = Field("logs/agentup.log", description="Log file path")
    max_size: int = Field(10 * 1024 * 1024, description="Max file size in bytes")
    backup_count: int = Field(5, description="Number of backup files to keep")
    rotation: Literal["size", "time", "never"] = Field("size", description="Rotation strategy")


class LoggingConfig(BaseModel):
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
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if isinstance(v, str):
            v = v.upper()
            if v not in valid_levels:
                raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v

    @field_validator("modules")
    @classmethod
    def validate_module_log_levels(cls, v: dict[str, str]) -> dict[str, str]:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        for module, level in v.items():
            if isinstance(level, str):
                level = level.upper()
                if level not in valid_levels:
                    raise ValueError(f"Invalid log level for {module}: {level}. Must be one of {valid_levels}")
                v[module] = level
        return v


class ServiceConfig(BaseModel):
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
        if not v or not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Service type must be alphanumeric with hyphens/underscores")
        return v.lower()

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("Priority must be between 0 and 100")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_high_priority(self) -> bool:
        return self.priority <= 20

    @computed_field
    @property
    def is_resilient(self) -> bool:
        return self.health_check_enabled and self.max_retries > 1

    @computed_field
    @property
    def initialization_score(self) -> float:
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
    name: str = Field(..., description="Server name")
    enabled: bool = Field(True, description="Enable this MCP server")
    transport: Literal["stdio", "sse", "streamable_http"] = Field(..., description="MCP transport protocol")

    # For stdio transport
    command: str | None = Field(None, description="Command to run for stdio server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_dir: FilePath | None = Field(None, description="Working directory")

    # For sse/streamable_http transports
    url: str | None = Field(None, description="Server URL for HTTP-based transports")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    timeout: int = Field(30, description="Request timeout in seconds")

    # Tool permissions (REQUIRED for security)
    tool_scopes: dict[str, list[str]] = Field(..., description="Tool name to required scopes mapping (REQUIRED)")

    # Multi-agent discovery
    expose_as_skills: bool = Field(
        False, description="Expose MCP tools as skills in AgentCard for multi-agent discovery"
    )

    @model_validator(mode="after")
    def validate_server_config(self) -> MCPServerConfig:
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("command is required for stdio transport")
        elif self.transport in ("sse", "streamable_http"):
            if not self.url:
                raise ValueError("url is required for sse and streamable_http transports")
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("Server URL must start with http:// or https://")

        # Validate tool_scopes is not empty (security requirement)
        if not self.tool_scopes:
            raise ValueError(
                "tool_scopes configuration is required for security - all MCP tools must have explicit scope mappings"
            )

        return self


class MCPConfig(BaseModel):
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
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


# Authentication Configuration Models


class ApiKeyEntry(BaseModel):
    key: str = Field(..., description="The API key value")
    scopes: list[str] = Field(default_factory=list, description="Scopes granted to this key")


class ApiKeyConfig(BaseModel):
    header_name: str = Field("X-API-Key", description="HTTP header name for API key")
    location: Literal["header", "query", "cookie"] = Field("header", description="Where to look for the API key")
    keys: list[str | ApiKeyEntry] = Field(..., description="List of valid API keys")


class BearerConfig(BaseModel):
    bearer_token: str | None = Field(None, description="Static bearer token")
    jwt_secret: str | None = Field(None, description="JWT secret for token validation")


class JWTConfig(BaseModel):
    secret_key: str = Field(..., description="Secret key for JWT validation")
    algorithm: str = Field("HS256", description="JWT algorithm")

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        valid_algorithms = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        if v not in valid_algorithms:
            raise ValueError(f"Invalid JWT algorithm. Must be one of: {valid_algorithms}")
        return v


class OAuth2Config(BaseModel):
    validation_strategy: Literal["jwt", "introspection", "both"] = Field("jwt", description="Token validation strategy")
    jwt_secret: str | None = Field(None, description="JWT secret for token validation")
    jwks_url: str | None = Field(None, description="JWKS URL for JWT validation")
    introspection_endpoint: str | None = Field(None, description="Token introspection endpoint")
    client_id: str | None = Field(None, description="OAuth2 client ID")
    client_secret: str | None = Field(None, description="OAuth2 client secret")
    jwt_algorithm: str = Field("RS256", description="JWT algorithm for OAuth2")
    required_scopes: list[str] = Field(default_factory=list, description="Required OAuth2 scopes")


class SecurityConfig(BaseModel):
    enabled: bool = Field(True, description="Enable security features")
    auth: dict[str, ApiKeyConfig | BearerConfig | JWTConfig | OAuth2Config] = Field(
        default_factory=dict, description="Authentication configuration by type"
    )
    scope_hierarchy: dict[str, list[str]] = Field(default_factory=dict, description="Scope hierarchy configuration")

    @field_validator("scope_hierarchy", mode="before")
    @classmethod
    def validate_scope_hierarchy(cls, v):
        """Handle None values for scope_hierarchy."""
        if v is None:
            return {}
        return v

    @field_validator("auth", mode="before")
    @classmethod
    def validate_auth(cls, v):
        """Handle None values for auth."""
        if v is None:
            return {}
        return v


class PluginCapabilityConfig(BaseModel):
    capability_id: str = Field(..., description="Capability identifier")
    name: str | None = Field(None, description="Human-readable name")
    description: str | None = Field(None, description="Capability description")
    required_scopes: list[str] = Field(default_factory=list, description="Required scopes")
    enabled: bool = Field(True, description="Whether capability is enabled")
    config: ConfigDictType = Field(default_factory=dict, description="Capability-specific config")
    capability_override: list[dict[str, Any]] | None = Field(
        None, description="Capability-specific middleware overrides"
    )


class PluginConfig(BaseModel):
    """Legacy plugin configuration model - use IntentConfig for new configurations"""

    name: str = Field(..., description="Plugin name/identifier")
    description: str | None = Field(None, description="Plugin description")
    enabled: bool = Field(True, description="Whether plugin is enabled")
    version: Version | None = Field(None, description="Plugin version constraint")
    package: str | None = Field(None, description="Package name for plugin discovery")
    keywords: list[str] = Field(default_factory=list, description="Keywords for plugin search")
    patterns: list[str] = Field(default_factory=list, description="File patterns to match for plugin files")
    # Capability configuration
    capabilities: list[PluginCapabilityConfig] = Field(default_factory=list, description="Plugin capabilities")
    priority: int = Field(50, description="Plugin initialization priority (lower = earlier)")
    # Default settings applied to all capabilities
    default_scopes: list[str] = Field(default_factory=list, description="Default scopes")
    plugin_override: list[dict[str, Any]] | None = Field(None, description="Plugin-level middleware overrides")
    config: ConfigDictType = Field(default_factory=dict, description="Plugin configuration")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Plugin name must be alphanumeric with hyphens, underscores, and dots")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def has_capabilities(self) -> bool:
        return len(self.capabilities) > 0

    @computed_field
    @property
    def enabled_capabilities_count(self) -> int:
        return sum(1 for cap in self.capabilities if cap.enabled)

    @computed_field
    @property
    def display_name(self) -> str:
        return self.name

    @computed_field
    @property
    def has_middleware(self) -> bool:
        return self.plugin_override is not None and len(self.plugin_override) > 0

    @computed_field
    @property
    def total_required_scopes(self) -> set[str]:
        scopes = set(self.default_scopes)
        for cap in self.capabilities:
            scopes.update(cap.required_scopes)
        return scopes

    @computed_field
    @property
    def complexity_score(self) -> float:
        score = 0.0

        # Capability count contribution (0.0 to 0.4)
        score += min(0.4, len(self.capabilities) / 10 * 0.4)

        # Middleware complexity (0.0 to 0.2)
        if self.has_middleware:
            score += min(0.2, len(self.plugin_override) / 5 * 0.2)

        # Scope count (0.0 to 0.2)
        total_scopes = len(self.total_required_scopes)
        score += min(0.2, total_scopes / 10 * 0.2)

        # Configuration complexity (0.0 to 0.2)
        config_size = len(str(self.config))
        score += min(0.2, config_size / 1000 * 0.2)

        return min(1.0, score)


class PluginsConfig(BaseModel):
    enabled: bool = Field(True, description="Enable plugin system")

    # Plugin configurations
    plugins: list[PluginConfig] = Field(default_factory=list, description="Plugin configurations")


class AIProviderConfig(BaseModel):
    provider: str = Field(..., description="AI provider name (e.g., openai, anthropic)")
    api_key: str | None = Field(None, description="API key for the AI provider")
    model: str = Field(..., description="AI model to use")
    stream: bool = Field(False, description="Enable streaming responses")
    chunk_size: int = Field(50, description="Chunk size for non-streaming fallback")
    stream_timeout: int = Field(30, description="Timeout for streaming responses")
    temperature: float = Field(0.7, description="Sampling temperature")
    max_tokens: int = Field(1000, description="Maximum number of tokens to generate")
    top_p: float = Field(1.0, description="Top-p sampling")


class MiddlewareConfig(BaseModel):
    enabled: bool = Field(True, description="Enable middleware system")

    # Rate limiting
    rate_limiting: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "requests_per_minute": 60, "burst_size": 72}
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
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        if not 1 <= v <= 32:
            raise ValueError("Workers must be between 1 and 32")
        return v


class AgentConfig(BaseModel):
    # Basic agent information
    project_name: str = Field("AgentUp", description="Project name", alias="name")
    description: str = Field("AI agent powered by AgentUp", description="Agent description")
    version: Version = Field("1.0.0", description="Agent version")

    # Add property for backward compatibility
    @property
    def name(self) -> str:
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
    plugins: dict[str, Any] = Field(default_factory=dict, description="Plugin configurations (dictionary format)")
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
        if not v or len(v) > 100:
            raise ValueError("Project name must be 1-100 characters")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        import semver

        try:
            semver.Version.parse(v)
        except ValueError:
            raise ValueError(
                "Version must follow semantic versioning (e.g., 1.0.0, 1.2.3-alpha.1, 1.0.0+build.123)"
            ) from None
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @computed_field
    @property
    def enabled_services(self) -> list[str]:
        return [name for name, config in self.services.items() if config.enabled]

    @computed_field
    @property
    def total_service_count(self) -> int:
        return len(self.services)

    @computed_field
    @property
    def security_enabled(self) -> bool:
        return self.security.enabled

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.project_name} v{self.version}"

    @model_validator(mode="after")
    def validate_mcp_consistency(self) -> AgentConfig:
        if self.mcp_enabled:
            if not self.mcp.enabled:
                self.mcp = MCPConfig(enabled=True)
        return self


class ConfigurationSettings(BaseSettings):
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
        directories = [self.DATA_DIR, self.LOGS_DIR, self.PLUGINS_DIR]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Utility function for environment variable expansion
def expand_env_vars(value: Any) -> Any:
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
    "BaseAgent",
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
