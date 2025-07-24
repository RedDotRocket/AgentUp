# Import typing for exception classes
from abc import ABC
from typing import Any

# Import official A2A types
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentSkill,
    APIKeySecurityScheme,
    Artifact,
    DataPart,
    HTTPAuthSecurityScheme,
    In,
    JSONRPCMessage,
    Message,
    Part,
    Role,
    SecurityScheme,
    SendMessageRequest,
    Task,
    TaskState,
    TaskStatus,
    TextPart,
)
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False
    LOG_NAME: str = "your_app.app_logs"
    LOG_ACCESS_NAME: str = "your_app.access_logs"


class JSONRPCError(Exception):
    """JSON-RPC error with code."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class TaskNotFoundError(Exception):
    """Task not found error."""

    pass


class ContentTypeNotSupportedError(Exception):
    """Content type not supported error."""

    pass


class InvalidAgentResponseError(Exception):
    """Invalid agent response error."""

    pass


class PluginCapability(BaseModel):
    """Model for plugin capability configuration."""

    capability_id: str
    # name: str
    # description: str
    required_scopes: list[str] = []
    enabled: bool = True


class PluginConfig(BaseModel):
    """Model for individual plugin configuration."""

    plugin_id: str
    name: str
    description: str
    capabilities: list[PluginCapability] = []


class PluginsConfig(BaseModel):
    """Model for plugins configuration - can be a list of plugins or dict with enabled flag."""

    enabled: bool = True
    plugins: list[PluginConfig] = []

    @classmethod
    def from_config_value(cls, config_value) -> "PluginsConfig":
        """Create PluginsConfig from various config formats."""
        if isinstance(config_value, dict):
            if "enabled" in config_value or "plugins" in config_value:
                # New format: {"enabled": True, "plugins": [...]}
                return cls(**config_value)
            else:
                # Legacy dict format - treat as enabled with empty plugins
                return cls(enabled=config_value.get("enabled", True), plugins=[])
        elif isinstance(config_value, list):
            # List format: [{"plugin_id": "...", ...}, ...]
            plugins = [PluginConfig(**plugin) for plugin in config_value]
            return cls(enabled=bool(plugins), plugins=plugins)
        else:
            # Other types - default behavior
            return cls(enabled=bool(config_value), plugins=[])


class AgentConfig(BaseModel):
    """Configuration for the agent."""

    project_name: str = "MyAgent"
    description: str = "AI agent description"
    version: str = "1.0.0"
    dispatcher_path: str | None = None  # e.g. "src.agent.function_dispatcher:get_function_dispatcher"
    # Services
    services_enabled: bool = True
    services_init_path: str | None = None  # e.g. "src.agent.services:initialize_services_from_config"

    # MCP integration
    mcp_enabled: bool = False
    mcp_init_path: str | None = None  # e.g. "src.agent.mcp.mcp_integration:initialize_mcp_integration"
    mcp_shutdown_path: str | None = None

    plugins: list[PluginConfig] = []
    security: dict[str, Any] | None = None
    services: dict[str, Any] | None = None


class ServiceConfig(BaseModel):
    type: str  # e.g. "llm", "database", "mcp_client", etc.
    init_path: str | None = None  # for custom loader overrides
    settings: dict[str, Any] | None = {}


class LoggingConfig(BaseModel):
    """Configuration model for logging settings."""

    enabled: bool = True
    level: str = "INFO"
    format: str = "text"  # "text" or "json"

    # Output destinations
    console: dict[str, Any] = {
        "enabled": True,
        "colors": True,
    }

    # Advanced configuration
    correlation_id: bool = True
    request_logging: bool = True

    # Module-specific log levels
    modules: dict[str, str] = {}

    # Uvicorn integration
    uvicorn: dict[str, Any] = {
        "access_log": True,
        "disable_default_handlers": True,
        "use_colors": True,
    }


class PluginResponse(BaseModel):
    """Response from a plugin handler."""

    success: bool
    result: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class BaseAgent(BaseModel, ABC):
    """Base class for agents."""

    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow",
    }

    agent_name: str = Field(
        description="The name of the agent.",
    )

    description: str = Field(
        description="A brief description of the agent's purpose.",
    )

    content_types: list[str] = Field(description="Supported content types.")


class CapabilityConfig(BaseModel):
    """Configuration for a single capability within a plugin."""

    capability_id: str
    name: str | None = None
    description: str | None = None
    required_scopes: list[str] = Field(default_factory=list)
    enabled: bool = True
    config: dict[str, Any] | None = None
    middleware_override: list[dict[str, Any]] | None = None


class ModernPluginConfig(BaseModel):
    """New capability-based plugin configuration."""

    plugin_id: str
    name: str | None = None
    description: str | None = None
    enabled: bool = True

    # Capability-based structure
    capabilities: list[CapabilityConfig] = Field(default_factory=list)

    # Plugin-level defaults (applied to all capabilities if not overridden)
    default_scopes: list[str] = Field(default_factory=list)
    middleware: list[dict[str, Any]] | None = None
    config: dict[str, Any] | None = None


class MCPToolScopeConfig(BaseModel):
    """Configuration for MCP tool scopes."""

    tool_name: str
    required_scopes: list[str] = Field(default_factory=list)


class MCPServerConfig(BaseModel):
    """Configuration for MCP servers with scope definitions."""

    name: str
    type: str  # "stdio" or "http"
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    tool_scopes: dict[str, list[str]] = Field(default_factory=dict)  # tool_name -> required_scopes


class MCPConfig(BaseModel):
    """MCP configuration with scope support."""

    client: dict[str, Any] | None = None
    server: dict[str, Any] | None = None
    servers: list[MCPServerConfig] = Field(default_factory=list)


# Re-export A2A types for convenience
__all__ = [
    # A2A types
    "AgentCard",
    "Artifact",
    "DataPart",
    "JSONRPCMessage",
    "AgentSkill",
    "AgentCapabilities",
    "AgentExtension",
    "APIKeySecurityScheme",
    "In",
    "SecurityScheme",
    "HTTPAuthSecurityScheme",
    "Message",
    "Role",
    "SendMessageRequest",
    "Task",
    "TextPart",
    "Part",
    "TaskState",
    "TaskStatus",
    # Custom exceptions
    "JSONRPCError",
    "TaskNotFoundError",
    "ContentTypeNotSupportedError",
    "InvalidAgentResponseError",
    # Custom models
    "PluginConfig",
    "AgentConfig",
    "LoggingConfig",
    "PluginResponse",
    "BaseAgent",
    # New capability-based models
    "CapabilityConfig",
    "ModernPluginConfig",
    "MCPToolScopeConfig",
    "MCPServerConfig",
    "MCPConfig",
    # Plugins configuration models
    "PluginCapability",
    "PluginsConfig",
]
