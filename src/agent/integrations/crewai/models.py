"""Pydantic models for CrewAI integration."""

from typing import Any

from pydantic import BaseModel, Field


class A2ARequest(BaseModel):
    """A2A JSON-RPC request model."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    method: str = Field(..., description="RPC method name")
    params: dict[str, Any] = Field(..., description="Method parameters")
    id: str = Field(..., description="Request ID")


class A2AResponse(BaseModel):
    """A2A JSON-RPC response model."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    result: dict[str, Any] | None = Field(None, description="Successful result")
    error: dict[str, Any] | None = Field(None, description="Error details")
    id: str = Field(..., description="Request ID matching the request")


class MessagePart(BaseModel):
    """Part of a message in A2A protocol."""

    kind: str = Field(..., description="Type of message part (text, data, etc.)")
    text: str | None = Field(None, description="Text content")
    data: dict[str, Any] | None = Field(None, description="Data content")


class Message(BaseModel):
    """A2A message model."""

    role: str = Field(..., description="Role of the message sender")
    parts: list[MessagePart] = Field(..., description="Message parts")
    message_id: str = Field(..., description="Unique message ID")
    kind: str = Field(default="message", description="Message kind")


class AgentUpConfig(BaseModel):
    """Configuration for AgentUp integration."""

    base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the AgentUp agent",
    )
    api_key: str | None = Field(None, description="API key for authentication")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    enable_streaming: bool = Field(default=False, description="Enable SSE streaming")


class SkillInfo(BaseModel):
    """Information about an AgentUp skill from AgentCard."""

    id: str = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="Skill description")
    input_modes: list[str] = Field(default=["text"], description="Supported input modes")
    output_modes: list[str] = Field(default=["text"], description="Supported output modes")
    tags: list[str] = Field(default=[], description="Skill tags")
