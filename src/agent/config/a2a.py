"""
A2A (Agent-to-Agent) Protocol Integration for AgentUp.

This module provides A2A protocol types, exceptions, and error handling utilities
for JSON-RPC communication between agents.
"""

from __future__ import annotations

# Import official A2A types
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentCardSignature,
    AgentExtension,
    AgentProvider,
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
    "AgentProvider",
    "AgentCardSignature",
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
    "TaskNotFoundError",
    "TaskNotCancelableError",
    "PushNotificationNotSupportedError",
    "UnsupportedOperationError",
    "ContentTypeNotSupportedError",
    "InvalidAgentResponseError",
    # A2A error handling utilities
    "A2A_ERROR_CODE_MAP",
    "get_error_code_for_exception",
]
