"""
Pydantic models for AgentUp MCP (Model Context Protocol) support system.

This module defines all MCP-related data structures using Pydantic models
for type safety and validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ..types import JsonValue
from ..utils.validation import BaseValidator, CompositeValidator, ValidationResult


class MCPResourceType(str, Enum):
    TEXT = "text"
    JSON = "json"
    BINARY = "binary"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class MCPToolType(str, Enum):
    FUNCTION = "function"
    RESOURCE = "resource"
    PROMPT = "prompt"


class MCPMessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


class MCPSessionState(str, Enum):
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    READY = "ready"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class MCPResource(BaseModel):
    name: str = Field(..., description="Resource name", min_length=1, max_length=128)
    uri: str = Field(..., description="Resource URI")
    description: str | None = Field(None, description="Resource description")
    mime_type: str = Field("text/plain", description="MIME type of resource")
    resource_type: MCPResourceType = Field(MCPResourceType.TEXT, description="Resource type")
    annotations: dict[str, JsonValue] = Field(default_factory=dict, description="Resource annotations")
    blob: bytes | None = Field(None, description="Binary resource data")
    text: str | None = Field(None, description="Text resource content")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Resource metadata")
    last_modified: datetime | None = Field(None, description="Last modification time")
    size_bytes: int | None = Field(None, description="Resource size in bytes", ge=0)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v.startswith(("file://", "http://", "https://", "agent://", "mcp://")):
            raise ValueError("URI must use supported scheme (file, http, https, agent, mcp)")
        return v

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError("MIME type must be in format 'type/subtype'")
        return v

    @model_validator(mode="after")
    def validate_resource_content(self) -> MCPResource:
        if self.resource_type == MCPResourceType.TEXT and not self.text:
            raise ValueError("Text resources must have text content")

        if self.resource_type == MCPResourceType.BINARY and not self.blob:
            raise ValueError("Binary resources must have blob data")

        # Update size if not provided
        if self.size_bytes is None:
            if self.text:
                self.size_bytes = len(self.text.encode("utf-8"))
            elif self.blob:
                self.size_bytes = len(self.blob)

        return self

    @property
    def is_binary(self) -> bool:
        return self.resource_type in (
            MCPResourceType.BINARY,
            MCPResourceType.IMAGE,
            MCPResourceType.AUDIO,
            MCPResourceType.VIDEO,
        )

    @property
    def human_readable_size(self) -> str:
        if not self.size_bytes:
            return "0 bytes"

        for unit in ["bytes", "KB", "MB", "GB"]:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024

        return f"{self.size_bytes:.1f} TB"


class MCPTool(BaseModel):
    name: str = Field(..., description="Tool name", min_length=1, max_length=64)
    description: str = Field(..., description="Tool description", min_length=1, max_length=1024)
    tool_type: MCPToolType = Field(MCPToolType.FUNCTION, description="Tool type")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for input")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for output")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    required_scopes: list[str] = Field(default_factory=list, description="Required permission scopes")
    annotations: dict[str, JsonValue] = Field(default_factory=dict, description="Tool annotations")
    examples: list[dict[str, Any]] = Field(default_factory=list, description="Usage examples")
    deprecated: bool = Field(False, description="Whether tool is deprecated")
    version: str = Field("1.0.0", description="Tool version")

    @field_validator("name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", v):
            raise ValueError("Tool name must be valid identifier with hyphens allowed")
        return v

    @field_validator("input_schema", "output_schema")
    @classmethod
    def validate_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v and "type" not in v:
            raise ValueError("Schema must have 'type' property if provided")
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

    @property
    def has_required_scopes(self) -> bool:
        return len(self.required_scopes) > 0

    @property
    def security_level(self) -> str:
        if not self.required_scopes:
            return "public"
        elif len(self.required_scopes) <= 2:
            return "low"
        elif len(self.required_scopes) <= 5:
            return "medium"
        else:
            return "high"


class MCPMessage(BaseModel):
    id: str | int = Field(..., description="Message ID")
    message_type: MCPMessageType = Field(..., description="Message type")
    method: str | None = Field(None, description="Method name for requests")
    params: dict[str, JsonValue] | None = Field(None, description="Message parameters")
    result: JsonValue | None = Field(None, description="Response result")
    error: dict[str, JsonValue] | None = Field(None, description="Error information")
    jsonrpc: str = Field("2.0", description="JSON-RPC version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")

    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc(cls, v: str) -> str:
        if v != "2.0":
            raise ValueError("Only JSON-RPC 2.0 is supported")
        return v

    @model_validator(mode="after")
    def validate_message_consistency(self) -> MCPMessage:
        if self.message_type == MCPMessageType.REQUEST:
            if not self.method:
                raise ValueError("Request messages must have method")
            if self.result is not None or self.error is not None:
                raise ValueError("Request messages cannot have result or error")

        elif self.message_type == MCPMessageType.RESPONSE:
            if self.method is not None:
                raise ValueError("Response messages cannot have method")
            if self.result is None and self.error is None:
                raise ValueError("Response messages must have result or error")
            if self.result is not None and self.error is not None:
                raise ValueError("Response messages cannot have both result and error")

        elif self.message_type == MCPMessageType.ERROR:
            if not self.error:
                raise ValueError("Error messages must have error information")

        return self

    @property
    def is_request(self) -> bool:
        return self.message_type == MCPMessageType.REQUEST

    @property
    def is_response(self) -> bool:
        return self.message_type == MCPMessageType.RESPONSE

    @property
    def is_error(self) -> bool:
        return self.message_type == MCPMessageType.ERROR or self.error is not None


class MCPSession(BaseModel):
    session_id: str = Field(..., description="Session identifier", min_length=1, max_length=128)
    server_name: str = Field(..., description="MCP server name")
    state: MCPSessionState = Field(MCPSessionState.INITIALIZING, description="Session state")
    capabilities: dict[str, JsonValue] = Field(default_factory=dict, description="Server capabilities")
    available_tools: list[MCPTool] = Field(default_factory=list, description="Available tools")
    available_resources: list[MCPResource] = Field(default_factory=list, description="Available resources")
    connection_info: dict[str, JsonValue] = Field(default_factory=dict, description="Connection details")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    error_message: str | None = Field(None, description="Error message if session failed")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Session metadata")
    timeout_seconds: int = Field(300, description="Session timeout", gt=0, le=3600)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Session ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

    @model_validator(mode="after")
    def validate_session_consistency(self) -> MCPSession:
        if self.state == MCPSessionState.ERROR and not self.error_message:
            raise ValueError("Error state requires error message")

        if self.state != MCPSessionState.ERROR and self.error_message:
            self.error_message = None  # Clear error for non-error states

        return self

    @property
    def is_active(self) -> bool:
        return self.state in (MCPSessionState.CONNECTED, MCPSessionState.READY)

    @property
    def is_healthy(self) -> bool:
        if self.state == MCPSessionState.ERROR:
            return False

        # Check for timeout
        elapsed = (datetime.utcnow() - self.last_activity).total_seconds()
        return elapsed < self.timeout_seconds

    @property
    def tool_count(self) -> int:
        return len(self.available_tools)

    @property
    def resource_count(self) -> int:
        return len(self.available_resources)

    def update_activity(self) -> None:
        self.last_activity = datetime.utcnow()


class MCPCapability(BaseModel):
    name: str = Field(..., description="Capability name", min_length=1, max_length=64)
    version: str = Field("1.0.0", description="Capability version")
    description: str | None = Field(None, description="Capability description")
    supported_methods: list[str] = Field(default_factory=list, description="Supported MCP methods")
    supported_notifications: list[str] = Field(default_factory=list, description="Supported notifications")
    experimental: bool = Field(False, description="Whether capability is experimental")
    deprecated: bool = Field(False, description="Whether capability is deprecated")
    required_client_version: str | None = Field(None, description="Minimum required client version")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Capability metadata")

    @field_validator("name")
    @classmethod
    def validate_capability_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", v):
            raise ValueError("Capability name must start with letter, contain only alphanumeric, hyphens, underscores")
        return v

    @field_validator("version", "required_client_version")
    @classmethod
    def validate_version(cls, v: str | None) -> str | None:
        if v is None:
            return v

        import semver

        try:
            semver.Version.parse(v)
        except ValueError:
            raise ValueError(
                "Version must follow semantic versioning (e.g., 1.0.0, 1.2.3-alpha.1, 1.0.0+build.123)"
            ) from None
        return v

    @property
    def is_stable(self) -> bool:
        return not self.experimental and not self.deprecated

    @property
    def method_count(self) -> int:
        return len(self.supported_methods)

    @property
    def notification_count(self) -> int:
        return len(self.supported_notifications)


class MCPCapabilityInfo(BaseModel):
    """Metadata about an MCP tool registered as an agent capability.

    This tracks MCP tools that have been converted to agent capabilities
    for exposure in AgentCards and multi-agent systems.
    """

    name: str = Field(..., description="MCP tool name (sanitized for capability use)")
    original_name: str = Field(..., description="Original MCP tool name")
    description: str = Field(default="", description="Tool description from MCP server")
    server_name: str = Field(..., description="Name of MCP server providing this tool")
    scopes: list[str] = Field(default_factory=list, description="Required scopes for this tool")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameter schema")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for input")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for output")

    @field_validator("name")
    @classmethod
    def validate_capability_name(cls, v: str) -> str:
        """Ensure capability name is valid (alphanumeric + underscores)."""
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Capability name must be valid identifier (underscores allowed)")
        return v


# MCP Validators using validation framework
class MCPResourceValidator(BaseValidator[MCPResource]):
    def validate(self, model: MCPResource) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for very large resources
        if model.size_bytes and model.size_bytes > 10 * 1024 * 1024:  # 10MB
            result.add_warning("Large resource may impact performance")

        # Validate URI schemes for security
        if model.uri.startswith("file://"):
            result.add_suggestion("File URIs may have security implications - ensure proper access controls")

        # Check for missing descriptions on public resources
        if not model.description and not model.uri.startswith("agent://"):
            result.add_suggestion("Public resources should have descriptions")

        return result


class MCPToolValidator(BaseValidator[MCPTool]):
    def validate(self, model: MCPTool) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for dangerous tool names
        dangerous_patterns = ["delete", "remove", "destroy", "kill", "terminate", "exec", "eval"]
        name_lower = model.name.lower()
        for pattern in dangerous_patterns:
            if pattern in name_lower:
                result.add_warning(f"Tool name contains potentially dangerous pattern: '{pattern}'")

        # Validate tools with no security requirements
        if not model.required_scopes and model.tool_type == MCPToolType.FUNCTION:
            result.add_suggestion("Function tools should typically require some permission scopes")

        # Check for missing examples on complex tools
        if len(str(model.input_schema)) > 1000 and not model.examples:
            result.add_suggestion("Complex tools should include usage examples")

        # Validate deprecated tools
        if model.deprecated and not model.description:
            result.add_warning("Deprecated tools should explain deprecation reason in description")

        return result


class MCPSessionValidator(BaseValidator[MCPSession]):
    def validate(self, model: MCPSession) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for stale sessions
        elapsed = (datetime.utcnow() - model.last_activity).total_seconds()
        if elapsed > model.timeout_seconds / 2:
            result.add_warning("Session may be stale - consider refreshing")

        # Validate session without capabilities
        if model.state == MCPSessionState.READY and not model.capabilities:
            result.add_warning("Ready session should have discovered capabilities")

        # Check timeout settings
        if model.timeout_seconds < 30:
            result.add_warning("Very short timeout may cause premature session termination")
        elif model.timeout_seconds > 1800:  # 30 minutes
            result.add_suggestion("Long timeout may keep resources tied up")

        return result


class MCPCapabilityValidator(BaseValidator[MCPCapability]):
    def validate(self, model: MCPCapability) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check experimental capabilities in production
        if model.experimental and not model.description:
            result.add_suggestion("Experimental capabilities should have clear descriptions")

        # Validate capabilities with no methods or notifications
        if not model.supported_methods and not model.supported_notifications:
            result.add_warning("Capability should support at least some methods or notifications")

        # Check for both experimental and deprecated
        if model.experimental and model.deprecated:
            result.add_warning("Capability cannot be both experimental and deprecated")

        return result


# Composite validator for MCP models
def create_mcp_validator() -> CompositeValidator[MCPResource]:
    validators = [
        MCPResourceValidator(MCPResource),
    ]
    return CompositeValidator(MCPResource, validators)


# Re-export key models
__all__ = [
    "MCPResourceType",
    "MCPToolType",
    "MCPMessageType",
    "MCPSessionState",
    "MCPResource",
    "MCPTool",
    "MCPMessage",
    "MCPSession",
    "MCPCapability",
    "MCPCapabilityInfo",
    "MCPResourceValidator",
    "MCPToolValidator",
    "MCPSessionValidator",
    "MCPCapabilityValidator",
    "create_mcp_validator",
]
