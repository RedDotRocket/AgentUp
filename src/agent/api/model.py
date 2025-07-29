"""
Pydantic models for AgentUp API system.

This module defines all API-related data structures using Pydantic models
for type safety and validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

# Import A2A protocol types
from a2a.types import TaskState as A2ATaskState
from pydantic import BaseModel, Field, field_validator, model_validator

from agent.types import JsonValue
from agent.utils.validation import BaseValidator, CompositeValidator, ValidationResult


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ErrorType(str, Enum):
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    INTERNAL_ERROR = "internal_error"
    NOT_FOUND_ERROR = "not_found_error"
    TIMEOUT_ERROR = "timeout_error"


class TaskRequest(BaseModel):
    task_id: str = Field(..., description="Task identifier", min_length=1, max_length=128)
    function_name: str = Field(..., description="Function to execute", min_length=1, max_length=64)
    parameters: dict[str, JsonValue] = Field(default_factory=dict, description="Function parameters")
    timeout: int = Field(300, description="Task timeout in seconds", gt=0, le=3600)
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority")
    callback_url: str | None = Field(None, description="Callback URL for task completion")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Task metadata")
    user_id: str | None = Field(None, description="User identifier")
    session_id: str | None = Field(None, description="Session identifier")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Task ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

    @field_validator("function_name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Function name must be valid Python identifier")
        return v

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Callback URL must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def validate_task_request(self) -> TaskRequest:
        # Check parameter size
        params_str = str(self.parameters)
        if len(params_str) > 100000:  # 100KB limit
            raise ValueError("Parameters too large (max 100KB)")

        return self


class TaskResponse(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    status: A2ATaskState = Field(..., description="Task status")
    result: JsonValue | None = Field(None, description="Task result")
    error: str | None = Field(None, description="Error message if failed")
    error_details: dict[str, JsonValue] = Field(default_factory=dict, description="Detailed error information")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Task start time")
    completed_at: datetime | None = Field(None, description="Task completion time")
    progress: float = Field(0.0, description="Task progress (0.0-1.0)", ge=0.0, le=1.0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Response metadata")

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        return self.status in (A2ATaskState.completed, A2ATaskState.failed, A2ATaskState.canceled)

    @model_validator(mode="after")
    def validate_task_response(self) -> TaskResponse:
        # Completed/failed tasks should have completion time
        if self.is_complete and self.completed_at is None:
            self.completed_at = datetime.utcnow()

        # Failed tasks should have error message
        if self.status == A2ATaskState.failed and not self.error:
            raise ValueError("Failed tasks must have error message")

        # Successful tasks should not have error
        if self.status == A2ATaskState.completed and self.error:
            self.error = None

        # Running tasks should have progress > 0
        if self.status == A2ATaskState.working and self.progress == 0.0:
            self.progress = 0.1  # Default to small progress for running tasks

        return self


class APIError(BaseModel):
    error_type: ErrorType = Field(..., description="Error type")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, JsonValue] = Field(default_factory=dict, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: str | None = Field(None, description="Request identifier for tracking")
    suggestion: str | None = Field(None, description="Suggested fix or action")

    @field_validator("error_code")
    @classmethod
    def validate_error_code(cls, v: str) -> str:
        import re

        if not re.match(r"^[A-Z][A-Z0-9_]*$", v):
            raise ValueError("Error code must be uppercase with underscores")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if len(v) < 5:
            raise ValueError("Error message must be at least 5 characters")
        if len(v) > 500:
            raise ValueError("Error message must be at most 500 characters")
        return v


class PaginationParams(BaseModel):
    page: int = Field(1, description="Page number", ge=1)
    per_page: int = Field(50, description="Items per page", ge=1, le=1000)
    sort_by: str | None = Field(None, description="Sort field")
    sort_order: Literal["asc", "desc"] = Field("asc", description="Sort order")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class PaginatedResponse(BaseModel):
    items: list[JsonValue] = Field(..., description="Response items")
    total: int = Field(..., description="Total item count", ge=0)
    page: int = Field(..., description="Current page", ge=1)
    per_page: int = Field(..., description="Items per page", ge=1)
    pages: int = Field(..., description="Total pages", ge=1)
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")

    @classmethod
    def create(cls, items: list[JsonValue], total: int, pagination: PaginationParams) -> PaginatedResponse:
        pages = max(1, (total + pagination.per_page - 1) // pagination.per_page)

        return cls(
            items=items,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
            pages=pages,
            has_next=pagination.page < pages,
            has_prev=pagination.page > 1,
        )


class HealthCheckResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(..., description="Application uptime", ge=0)
    services: dict[str, dict[str, JsonValue]] = Field(default_factory=dict, description="Service health details")

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"


class MetricsResponse(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metrics timestamp")
    request_count: int = Field(0, description="Total request count", ge=0)
    error_count: int = Field(0, description="Total error count", ge=0)
    average_response_time_ms: float = Field(0.0, description="Average response time", ge=0)
    active_tasks: int = Field(0, description="Currently active tasks", ge=0)
    completed_tasks: int = Field(0, description="Completed tasks", ge=0)
    failed_tasks: int = Field(0, description="Failed tasks", ge=0)

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100

    @property
    def success_rate(self) -> float:
        return 100.0 - self.error_rate


# API Validators using validation framework
class TaskRequestValidator(BaseValidator[TaskRequest]):
    def validate(self, model: TaskRequest) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for potentially dangerous function names
        dangerous_patterns = ["eval", "exec", "delete", "remove", "destroy"]
        function_lower = model.function_name.lower()
        for pattern in dangerous_patterns:
            if pattern in function_lower:
                result.add_warning(f"Function name contains potentially dangerous pattern: '{pattern}'")

        # Validate timeout ranges
        if model.timeout < 5:
            result.add_warning("Very short timeout may cause premature failures")
        elif model.timeout > 1800:  # 30 minutes
            result.add_warning("Very long timeout may block resources")

        # Check parameter complexity
        if len(model.parameters) > 20:
            result.add_warning("Large number of parameters may indicate overly complex request")

        # Validate urgent priority usage
        if model.priority == TaskPriority.URGENT and not model.user_id:
            result.add_suggestion("Urgent tasks should typically have associated user")

        return result


class APIErrorValidator(BaseValidator[APIError]):
    def validate(self, model: APIError) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for vague error messages
        vague_terms = ["error", "failed", "problem", "issue"]
        message_lower = model.message.lower()
        if any(term in message_lower for term in vague_terms) and len(model.message) < 20:
            result.add_suggestion("Error message could be more specific")

        # Validate error type consistency
        if model.error_type == ErrorType.VALIDATION_ERROR and "validation" not in model.message.lower():
            result.add_warning("Error type doesn't match message content")

        # Check for sensitive information in error messages
        sensitive_patterns = ["password", "token", "key", "secret"]
        for pattern in sensitive_patterns:
            if pattern in model.message.lower():
                result.add_warning(f"Error message may contain sensitive information: '{pattern}'")

        return result


class PaginationValidator(BaseValidator[PaginationParams]):
    def validate(self, model: PaginationParams) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for very large page sizes
        if model.per_page > 100:
            result.add_warning("Large page size may impact performance")

        # Validate sort field if provided
        if model.sort_by:
            if not model.sort_by.replace("_", "").isalnum():
                result.add_warning("Sort field should be alphanumeric with underscores")

        return result


# Composite validator for API models
def create_api_validator() -> CompositeValidator[TaskRequest]:
    validators = [
        TaskRequestValidator(TaskRequest),
    ]
    return CompositeValidator(TaskRequest, validators)


# Re-export key models
__all__ = [
    "A2ATaskState",  # Re-exported from a2a.types as TaskState
    "TaskPriority",
    "ErrorType",
    "TaskRequest",
    "TaskResponse",
    "APIError",
    "PaginationParams",
    "PaginatedResponse",
    "HealthCheckResponse",
    "MetricsResponse",
    "TaskRequestValidator",
    "APIErrorValidator",
    "PaginationValidator",
    "create_api_validator",
]
