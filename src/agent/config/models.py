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


class RoutingConfig(BaseModel):
    """Global routing configuration."""

    default_mode: str = "ai"  # "ai" or "direct"
    fallback_plugin: str | None = None  # Fallback plugin when no match
    fallback_enabled: bool = True  # Allow AI→Direct fallback


class PluginConfig(BaseModel):
    """Configuration for a plugin - extends A2A with routing config."""

    plugin_id: str
    name: str
    description: str
    input_mode: str = "text"
    output_mode: str = "text"
    routing_mode: str | None = None  # "ai", "direct", or None (use default)
    keywords: list[str] | None = None  # For direct routing
    patterns: list[str] | None = None  # For direct routing
    config: dict[str, Any] | None = None
    middleware: list[dict[str, Any]] | None = None
    enabled: bool = True  # Allow disabling plugins


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

    file: dict[str, Any] = {
        "enabled": False,
        "path": "logs/agent.log",
        "rotation": "100 MB",
        "retention": "1 week",
        "compression": True,
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
    "RoutingConfig",
    "PluginConfig",
    "AgentConfig",
    "LoggingConfig",
    "PluginResponse",
    "BaseAgent",
]
