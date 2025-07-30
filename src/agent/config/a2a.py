"""
A2A (Agent-to-Agent) Protocol Integration for AgentUp.

This module provides A2A protocol types, exceptions, and error handling utilities
for JSON-RPC communication between agents.
"""

from __future__ import annotations

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


class JSONRPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class TaskNotFoundError(Exception):
    pass


class TaskNotCancelableError(Exception):
    pass


class PushNotificationNotSupportedError(Exception):
    pass


class UnsupportedOperationError(Exception):
    pass


class ContentTypeNotSupportedError(Exception):
    pass


class InvalidAgentResponseError(Exception):
    pass


# A2A Error Code Mapping
A2A_ERROR_CODE_MAP = {
    TaskNotFoundError: -32001,
    TaskNotCancelableError: -32002,
    PushNotificationNotSupportedError: -32003,
    UnsupportedOperationError: -32004,
    ContentTypeNotSupportedError: -32005,
    InvalidAgentResponseError: -32006,
}


def get_error_code_for_exception(exception_type: type[Exception]) -> int | None:
    """Get the A2A JSON-RPC error code for an exception type.

    Args:
        exception_type: The exception class type

    Returns:
        The corresponding JSON-RPC error code or None if not found
    """
    return A2A_ERROR_CODE_MAP.get(exception_type)


def create_jsonrpc_error_from_exception(exception: Exception, request_id: Any = None) -> dict[str, Any]:
    """Create a JSON-RPC error response from an exception.

    Args:
        exception: The exception instance
        request_id: The JSON-RPC request ID

    Returns:
        A JSON-RPC error response dictionary
    """
    error_code = get_error_code_for_exception(type(exception))

    if error_code is None:
        # Default to internal error for unknown exceptions
        error_code = -32603

    return {
        "jsonrpc": "2.0",
        "error": {"code": error_code, "message": str(exception), "data": {"exception_type": type(exception).__name__}},
        "id": request_id,
    }


# NOTE: Configuration models have been moved to model.py
# This file now focuses solely on A2A protocol integration


class BaseAgent(BaseModel, ABC):
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow",
    }

    agent_name: str = Field(description="The name of the agent.")
    description: str = Field(description="A brief description of the agent's purpose.")
    content_types: list[str] = Field(description="Supported content types.")


# Re-export A2A types and error handling for convenience
__all__ = [
    # A2A protocol types
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
    # A2A JSON-RPC exceptions
    "JSONRPCError",
    "TaskNotFoundError",
    "TaskNotCancelableError",
    "PushNotificationNotSupportedError",
    "UnsupportedOperationError",
    "ContentTypeNotSupportedError",
    "InvalidAgentResponseError",
    # A2A error handling utilities
    "A2A_ERROR_CODE_MAP",
    "get_error_code_for_exception",
    "create_jsonrpc_error_from_exception",
    # A2A base classes
    "BaseAgent",
]
