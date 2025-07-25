"""
Pydantic models for AgentUp state management.

This module defines all state-related data structures including conversation state,
variables, and backend configuration.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator

from ..types import TTL, ConfigDict, FilePath, SessionId, Timestamp, UserId

# Generic type for state variables
T = TypeVar("T")


class StateVariableType(str, Enum):
    """Types of state variables."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    JSON = "json"
    BINARY = "binary"


class StateVariable(BaseModel, Generic[T]):
    """Typed state variable with metadata."""

    key: str = Field(..., description="Variable key")
    value: T = Field(..., description="Variable value")
    type_name: StateVariableType = Field(..., description="Variable type")
    created_at: Timestamp = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: Timestamp = Field(default_factory=datetime.utcnow, description="Last update time")
    ttl: TTL | None = Field(None, description="Time-to-live in seconds")
    version: int = Field(1, description="Variable version for optimistic locking")

    # Metadata
    description: str | None = Field(None, description="Variable description")
    tags: list[str] = Field(default_factory=list, description="Variable tags")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validate variable key format."""
        if not v or len(v) > 256:
            raise ValueError("Key must be 1-256 characters")
        # Allow alphanumeric, dots, hyphens, underscores
        import re

        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError("Key can only contain alphanumeric characters, dots, hyphens, and underscores")
        return v

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: TTL | None) -> TTL | None:
        """Validate TTL value."""
        if v is not None and v <= 0:
            raise ValueError("TTL must be positive")
        return v

    @property
    def is_expired(self) -> bool:
        """Check if variable has expired."""
        if not self.ttl:
            return False
        expires_at = self.updated_at + timedelta(seconds=self.ttl)
        return datetime.utcnow() > expires_at

    def touch(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.utcnow()
        self.version += 1

    class Config:
        arbitrary_types_allowed = True


class ConversationRole(str, Enum):
    """Roles in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"
    TOOL = "tool"


class ConversationMessage(BaseModel):
    """Single message in conversation history."""

    id: str = Field(..., description="Message identifier")
    role: ConversationRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: Timestamp = Field(default_factory=datetime.utcnow, description="Message timestamp")

    # Message metadata
    metadata: dict[str, str] = Field(default_factory=dict, description="Message metadata")
    tokens: int | None = Field(None, description="Token count")

    # Function/tool calling
    function_name: str | None = Field(None, description="Function name if role is function")
    function_call: dict[str, Any] | None = Field(None, description="Function call data")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tool calls")

    # Message relationships
    reply_to: str | None = Field(None, description="ID of message this replies to")
    thread_id: str | None = Field(None, description="Thread identifier")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate message content."""
        if len(v) > 1_000_000:  # 1MB limit
            raise ValueError("Message content too large (max 1MB)")
        return v

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate message ID format."""
        if not v or len(v) > 128:
            raise ValueError("Message ID must be 1-128 characters")
        return v


class ConversationSummary(BaseModel):
    """Summary of conversation history."""

    total_messages: int = Field(..., description="Total number of messages")
    user_messages: int = Field(..., description="Number of user messages")
    assistant_messages: int = Field(..., description="Number of assistant messages")
    total_tokens: int | None = Field(None, description="Total token count")
    first_message_at: Timestamp | None = Field(None, description="First message timestamp")
    last_message_at: Timestamp | None = Field(None, description="Last message timestamp")
    topics: list[str] = Field(default_factory=list, description="Conversation topics")
    summary_text: str | None = Field(None, description="Human-readable summary")


class ConversationState(BaseModel):
    """Complete conversation state management."""

    context_id: str = Field(..., description="Conversation context identifier")
    user_id: UserId | None = Field(None, description="Associated user")
    session_id: SessionId | None = Field(None, description="Session identifier")

    # Timestamps
    created_at: Timestamp = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: Timestamp = Field(default_factory=datetime.utcnow, description="Last update time")
    last_activity: Timestamp = Field(default_factory=datetime.utcnow, description="Last activity time")

    # State data
    variables: dict[str, StateVariable] = Field(default_factory=dict, description="State variables")
    metadata: dict[str, str] = Field(default_factory=dict, description="Conversation metadata")
    history: list[ConversationMessage] = Field(default_factory=list, description="Message history")

    # Configuration
    max_history_size: int = Field(100, description="Maximum history size")
    max_variable_count: int = Field(1000, description="Maximum variable count")
    auto_summarize: bool = Field(True, description="Auto-summarize old messages")

    # Summary and archival
    summary: ConversationSummary | None = Field(None, description="Conversation summary")
    archived_messages: int = Field(0, description="Number of archived messages")

    # Tags and categorization
    tags: list[str] = Field(default_factory=list, description="Conversation tags")
    category: str | None = Field(None, description="Conversation category")
    priority: int = Field(0, description="Conversation priority")

    @field_validator("context_id")
    @classmethod
    def validate_context_id(cls, v: str) -> str:
        """Validate context ID format."""
        if not v or len(v) > 128:
            raise ValueError("Context ID must be 1-128 characters")
        return v

    @field_validator("max_history_size", "max_variable_count")
    @classmethod
    def validate_limits(cls, v: int) -> int:
        """Validate size limits."""
        if v <= 0:
            raise ValueError("Limits must be positive")
        if v > 10000:
            raise ValueError("Limits too large (max 10000)")
        return v

    def add_message(self, message: ConversationMessage) -> None:
        """Add message with size limit enforcement."""
        self.history.append(message)
        self.last_activity = datetime.utcnow()
        self.updated_at = self.last_activity

        # Enforce history size limit
        if len(self.history) > self.max_history_size:
            if self.auto_summarize:
                self._archive_old_messages()
            else:
                # Remove oldest messages
                removed = self.history[: -self.max_history_size]
                self.history = self.history[-self.max_history_size :]
                self.archived_messages += len(removed)

    def set_variable(self, key: str, value: Any, ttl: TTL | None = None) -> None:
        """Set a state variable."""
        if len(self.variables) >= self.max_variable_count and key not in self.variables:
            raise ValueError(f"Maximum variable count ({self.max_variable_count}) exceeded")

        # Determine type
        var_type = self._determine_type(value)

        if key in self.variables:
            # Update existing variable
            var = self.variables[key]
            var.value = value
            var.touch()
            if ttl is not None:
                var.ttl = ttl
        else:
            # Create new variable
            self.variables[key] = StateVariable(key=key, value=value, type_name=var_type, ttl=ttl)

        self.updated_at = datetime.utcnow()

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a state variable value."""
        if key not in self.variables:
            return default

        var = self.variables[key]
        if var.is_expired:
            del self.variables[key]
            return default

        return var.value

    def delete_variable(self, key: str) -> bool:
        """Delete a state variable."""
        if key in self.variables:
            del self.variables[key]
            self.updated_at = datetime.utcnow()
            return True
        return False

    def cleanup_expired_variables(self) -> int:
        """Remove expired variables and return count removed."""
        expired_keys = [key for key, var in self.variables.items() if var.is_expired]

        for key in expired_keys:
            del self.variables[key]

        if expired_keys:
            self.updated_at = datetime.utcnow()

        return len(expired_keys)

    def get_summary_stats(self) -> ConversationSummary:
        """Generate conversation summary statistics."""
        user_msgs = sum(1 for msg in self.history if msg.role == ConversationRole.USER)
        assistant_msgs = sum(1 for msg in self.history if msg.role == ConversationRole.ASSISTANT)
        total_tokens = sum(msg.tokens or 0 for msg in self.history if msg.tokens)

        first_msg = self.history[0] if self.history else None
        last_msg = self.history[-1] if self.history else None

        return ConversationSummary(
            total_messages=len(self.history) + self.archived_messages,
            user_messages=user_msgs,
            assistant_messages=assistant_msgs,
            total_tokens=total_tokens if total_tokens > 0 else None,
            first_message_at=first_msg.timestamp if first_msg else None,
            last_message_at=last_msg.timestamp if last_msg else None,
            topics=self.tags.copy(),
            summary_text=self.summary.summary_text if self.summary else None,
        )

    def _determine_type(self, value: Any) -> StateVariableType:
        """Determine the type of a value."""
        if isinstance(value, str):
            return StateVariableType.STRING
        elif isinstance(value, bool):
            return StateVariableType.BOOLEAN
        elif isinstance(value, int):
            return StateVariableType.INTEGER
        elif isinstance(value, float):
            return StateVariableType.FLOAT
        elif isinstance(value, list):
            return StateVariableType.LIST
        elif isinstance(value, dict):
            return StateVariableType.DICT
        elif isinstance(value, bytes):
            return StateVariableType.BINARY
        else:
            return StateVariableType.JSON

    def _archive_old_messages(self) -> None:
        """Archive old messages when history is full."""
        # Keep recent messages, archive the rest
        keep_count = self.max_history_size // 2
        to_archive = self.history[:-keep_count]
        self.history = self.history[-keep_count:]
        self.archived_messages += len(to_archive)

        # Update summary
        if not self.summary:
            self.summary = ConversationSummary(total_messages=0, user_messages=0, assistant_messages=0)

        # Update counts
        self.summary.total_messages += len(to_archive)
        self.summary.user_messages += sum(1 for msg in to_archive if msg.role == ConversationRole.USER)
        self.summary.assistant_messages += sum(1 for msg in to_archive if msg.role == ConversationRole.ASSISTANT)


class StateBackendType(str, Enum):
    """State storage backend types."""

    MEMORY = "memory"
    REDIS = "redis"
    FILE = "file"
    DATABASE = "database"


class StateBackendConfig(BaseModel):
    """Configuration for state storage backend."""

    type: StateBackendType = Field(..., description="Backend type")

    # Common settings
    ttl: TTL = Field(3600, description="Default TTL in seconds")
    max_size: int = Field(10000, description="Maximum entries")
    compression: bool = Field(False, description="Enable compression")

    # Connection settings
    connection_string: str | None = Field(None, description="Connection string")
    host: str | None = Field(None, description="Host address")
    port: int | None = Field(None, description="Port number")
    database: str | None = Field(None, description="Database name")

    # Authentication
    username: str | None = Field(None, description="Username")
    password: str | None = Field(None, description="Password")

    # Redis-specific settings
    redis_settings: ConfigDict = Field(default_factory=dict, description="Redis-specific config")

    # File-specific settings
    file_path: FilePath | None = Field(None, description="File storage path")

    # Database-specific settings
    table_name: str = Field("conversation_state", description="Database table name")

    # Performance settings
    connection_pool_size: int = Field(10, description="Connection pool size")
    connection_timeout: int = Field(30, description="Connection timeout in seconds")
    retry_attempts: int = Field(3, description="Retry attempts")

    @field_validator("ttl", "max_size")
    @classmethod
    def validate_positive_values(cls, v: int) -> int:
        """Validate positive values."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int | None) -> int | None:
        """Validate port number."""
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class StateOperationType(str, Enum):
    """Types of state operations."""

    GET = "get"
    SET = "set"
    DELETE = "delete"
    LIST = "list"
    CLEANUP = "cleanup"


class StateOperation(BaseModel):
    """State operation for logging and debugging."""

    operation_id: str = Field(..., description="Operation identifier")
    operation_type: StateOperationType = Field(..., description="Operation type")
    context_id: str = Field(..., description="Context identifier")
    key: str | None = Field(None, description="Variable key")

    # Timing
    timestamp: Timestamp = Field(default_factory=datetime.utcnow, description="Operation timestamp")
    duration_ms: float | None = Field(None, description="Operation duration")

    # Result
    success: bool = Field(..., description="Operation success")
    error_message: str | None = Field(None, description="Error message if failed")

    # Metadata
    user_id: UserId | None = Field(None, description="User who performed operation")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class StateMetrics(BaseModel):
    """State management metrics."""

    # Counts
    total_contexts: int = Field(0, description="Total conversation contexts")
    total_variables: int = Field(0, description="Total state variables")
    total_messages: int = Field(0, description="Total messages")

    # Size metrics
    avg_variables_per_context: float = Field(0.0, description="Average variables per context")
    avg_messages_per_context: float = Field(0.0, description="Average messages per context")

    # Performance metrics
    avg_get_latency_ms: float = Field(0.0, description="Average get operation latency")
    avg_set_latency_ms: float = Field(0.0, description="Average set operation latency")

    # Backend metrics
    backend_type: StateBackendType = Field(..., description="Backend type")
    backend_health: Literal["healthy", "degraded", "unhealthy"] = Field("healthy", description="Backend health status")

    # Time window
    measurement_window: timedelta = Field(..., description="Measurement time window")
    measured_at: Timestamp = Field(default_factory=datetime.utcnow, description="Measurement time")


class StateConfig(BaseModel):
    """Complete state management configuration."""

    enabled: bool = Field(True, description="Enable state management")

    # Backend configuration
    backend: StateBackendConfig = Field(..., description="Storage backend configuration")

    # Default limits
    default_max_history: int = Field(100, description="Default max history size")
    default_max_variables: int = Field(1000, description="Default max variables")
    default_ttl: TTL = Field(3600, description="Default variable TTL")

    # Cleanup configuration
    cleanup_enabled: bool = Field(True, description="Enable automatic cleanup")
    cleanup_interval: int = Field(300, description="Cleanup interval in seconds")
    expired_cleanup_batch_size: int = Field(100, description="Expired items cleanup batch size")

    # Performance settings
    cache_enabled: bool = Field(True, description="Enable in-memory caching")
    cache_size: int = Field(1000, description="Cache size")
    cache_ttl: TTL = Field(300, description="Cache TTL")

    # Monitoring
    metrics_enabled: bool = Field(True, description="Enable metrics collection")
    operation_logging: bool = Field(False, description="Log all operations")

    @field_validator("default_max_history", "default_max_variables", "cache_size")
    @classmethod
    def validate_positive_limits(cls, v: int) -> int:
        """Validate positive limit values."""
        if v <= 0:
            raise ValueError("Limit must be positive")
        return v


# Re-export key models
__all__ = [
    "StateVariable",
    "StateVariableType",
    "ConversationRole",
    "ConversationMessage",
    "ConversationSummary",
    "ConversationState",
    "StateBackendType",
    "StateBackendConfig",
    "StateOperation",
    "StateOperationType",
    "StateMetrics",
    "StateConfig",
]
