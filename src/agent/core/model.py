"""
Pydantic models for AgentUp core system.

This module defines all core function dispatch and execution data structures
using Pydantic models for type safety and validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from ..types import JsonValue
from ..utils.validation import BaseValidator, CompositeValidator, ValidationResult


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class FunctionType(str, Enum):
    BUILTIN = "builtin"
    PLUGIN = "plugin"
    LLM_FUNCTION = "llm_function"
    ASYNC = "async"
    STREAMING = "streaming"


class ParameterType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    ANY = "any"


class FunctionParameter(BaseModel):
    name: str = Field(..., description="Parameter name", min_length=1, max_length=64)
    type: ParameterType = Field(..., description="Parameter type")
    description: str = Field("", description="Parameter description")
    required: bool = Field(True, description="Whether parameter is required")
    default: JsonValue | None = Field(None, description="Default value")
    enum: list[JsonValue] | None = Field(None, description="Allowed values for enum types")
    min_value: float | None = Field(None, description="Minimum value for numeric types")
    max_value: float | None = Field(None, description="Maximum value for numeric types")
    min_length: int | None = Field(None, description="Minimum length for string/array types")
    max_length: int | None = Field(None, description="Maximum length for string/array types")

    @field_validator("name")
    @classmethod
    def validate_parameter_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Parameter name must be valid Python identifier")
        return v

    @model_validator(mode="after")
    def validate_parameter_constraints(self) -> FunctionParameter:
        # Validate numeric constraints
        if self.type in (ParameterType.INTEGER, ParameterType.FLOAT):
            if self.min_value is not None and self.max_value is not None:
                if self.min_value > self.max_value:
                    raise ValueError("min_value cannot be greater than max_value")

        # Validate length constraints
        if self.type in (ParameterType.STRING, ParameterType.ARRAY):
            if self.min_length is not None and self.max_length is not None:
                if self.min_length > self.max_length:
                    raise ValueError("min_length cannot be greater than max_length")

        # Validate default value type
        if self.default is not None and self.required:
            self.required = False  # If default provided, parameter is not required

        return self


class FunctionSignature(BaseModel):
    name: str = Field(..., description="Function name", min_length=1, max_length=64)
    module: str = Field(..., description="Module path", min_length=1, max_length=256)
    function_type: FunctionType = Field(..., description="Function type")
    parameters: list[FunctionParameter] = Field(default_factory=list, description="Function parameters")
    return_type: str | None = Field(None, description="Return type annotation")
    description: str = Field("", description="Function description")
    examples: list[dict[str, JsonValue]] = Field(default_factory=list, description="Usage examples")
    tags: list[str] = Field(default_factory=list, description="Function tags")
    deprecated: bool = Field(False, description="Whether function is deprecated")
    version: str = Field("1.0.0", description="Function version")
    async_function: bool = Field(False, description="Whether function is async")
    streaming: bool = Field(False, description="Whether function supports streaming")

    @field_validator("name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Function name must be valid Python identifier")

        # Check for reserved names
        reserved_names = {"eval", "exec", "import", "__import__", "compile", "open"}
        if v in reserved_names:
            raise ValueError(f"Function name '{v}' is reserved")
        return v

    @field_validator("module")
    @classmethod
    def validate_module_path(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", v):
            raise ValueError("Module path must be valid Python module path")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not tag or not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid tag format: '{tag}'")
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
    def required_parameters(self) -> list[FunctionParameter]:
        return [param for param in self.parameters if param.required]

    @property
    def optional_parameters(self) -> list[FunctionParameter]:
        return [param for param in self.parameters if not param.required]


class ExecutionContext(BaseModel):
    request_id: str = Field(..., description="Request identifier", min_length=1, max_length=128)
    function_name: str = Field(..., description="Function being executed")
    user_id: str | None = Field(None, description="User identifier")
    session_id: str | None = Field(None, description="Session identifier")
    correlation_id: str | None = Field(None, description="Correlation identifier for tracing")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Context metadata")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution start time")
    timeout_seconds: int = Field(300, description="Execution timeout", gt=0, le=3600)
    retry_count: int = Field(0, description="Current retry attempt", ge=0)
    max_retries: int = Field(3, description="Maximum retry attempts", ge=0)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Request ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

    @property
    def is_retry(self) -> bool:
        return self.retry_count > 0

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()


class ExecutionResult(BaseModel):
    request_id: str = Field(..., description="Request identifier")
    function_name: str = Field(..., description="Function that was executed")
    status: ExecutionStatus = Field(..., description="Execution status")
    result: JsonValue | None = Field(None, description="Execution result")
    error: str | None = Field(None, description="Error message if failed")
    error_type: str | None = Field(None, description="Error type classification")
    stack_trace: str | None = Field(None, description="Stack trace for errors")
    started_at: datetime = Field(..., description="Execution start time")
    completed_at: datetime | None = Field(None, description="Execution completion time")
    execution_time_ms: float | None = Field(None, description="Execution time in milliseconds")
    memory_usage_mb: float | None = Field(None, description="Memory usage in MB")
    retry_count: int = Field(0, description="Number of retry attempts", ge=0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Result metadata")

    @property
    def is_successful(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status in (ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT)

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @model_validator(mode="after")
    def validate_execution_result(self) -> ExecutionResult:
        # Failed executions should have error message
        if self.is_failed and not self.error:
            raise ValueError("Failed executions must have error message")

        # Successful executions should not have error
        if self.is_successful and self.error:
            self.error = None

        # Set completion time for finished executions
        if self.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.CANCELLED,
        ):
            if self.completed_at is None:
                self.completed_at = datetime.now(timezone.utc)

        # Calculate execution time if not provided
        if self.execution_time_ms is None and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.execution_time_ms = duration * 1000

        return self


class FunctionRegistry(BaseModel):
    functions: dict[str, FunctionSignature] = Field(default_factory=dict, description="Registered functions")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Last registry update"
    )
    version: str = Field("1.0.0", description="Registry version")

    def register_function(self, signature: FunctionSignature) -> None:
        self.functions[signature.name] = signature
        self.last_updated = datetime.now(timezone.utc)

    def get_function(self, name: str) -> FunctionSignature | None:
        return self.functions.get(name)

    def list_functions(self, function_type: FunctionType | None = None) -> list[FunctionSignature]:
        if function_type:
            return [sig for sig in self.functions.values() if sig.function_type == function_type]
        return list(self.functions.values())

    @property
    def function_count(self) -> int:
        return len(self.functions)


# Core Validators using validation framework
class FunctionSignatureValidator(BaseValidator[FunctionSignature]):
    def validate(self, model: FunctionSignature) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for dangerous function names
        dangerous_patterns = ["delete", "remove", "destroy", "kill", "terminate", "shutdown"]
        name_lower = model.name.lower()
        for pattern in dangerous_patterns:
            if pattern in name_lower:
                result.add_warning(f"Function name contains potentially dangerous pattern: '{pattern}'")

        # Validate parameter count
        if len(model.parameters) > 20:
            result.add_warning("Large number of parameters may indicate complex interface")

        # Check for missing descriptions
        if not model.description and model.function_type == FunctionType.LLM_FUNCTION:
            result.add_suggestion("LLM functions should have descriptions for better AI understanding")

        # Validate deprecated functions
        if model.deprecated and not model.description:
            result.add_warning("Deprecated functions should explain deprecation reason")

        # Check for missing examples on complex functions
        if len(model.parameters) > 5 and not model.examples:
            result.add_suggestion("Complex functions should include usage examples")

        return result


class ExecutionContextValidator(BaseValidator[ExecutionContext]):
    def validate(self, model: ExecutionContext) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check timeout values
        if model.timeout_seconds < 5:
            result.add_warning("Very short timeout may cause premature failures")
        elif model.timeout_seconds > 1800:  # 30 minutes
            result.add_warning("Very long timeout may block resources")

        # Validate retry configuration
        if model.max_retries > 10:
            result.add_warning("High retry count may cause excessive resource usage")

        # Check if retry count exceeds max
        if model.retry_count > model.max_retries:
            result.add_error("Retry count cannot exceed max retries")

        return result


class ExecutionResultValidator(BaseValidator[ExecutionResult]):
    def validate(self, model: ExecutionResult) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for very long execution times
        if model.execution_time_ms and model.execution_time_ms > 300000:  # 5 minutes
            result.add_warning("Very long execution time may indicate performance issues")

        # Check for high memory usage
        if model.memory_usage_mb and model.memory_usage_mb > 1000:  # 1GB
            result.add_warning("High memory usage detected")

        # Validate error information consistency
        if model.error and not model.error_type:
            result.add_suggestion("Consider specifying error type for better error categorization")

        # Check for sensitive information in error messages
        if model.error:
            sensitive_patterns = ["password", "token", "key", "secret"]
            error_lower = model.error.lower()
            for pattern in sensitive_patterns:
                if pattern in error_lower:
                    result.add_warning(f"Error message may contain sensitive information: '{pattern}'")

        return result


# Composite validator for core models
def create_core_validator() -> CompositeValidator[FunctionSignature]:
    validators: list[BaseValidator[FunctionSignature]] = [
        FunctionSignatureValidator(FunctionSignature),
    ]
    return CompositeValidator(FunctionSignature, validators)


# Re-export key models
__all__ = [
    "ExecutionStatus",
    "FunctionType",
    "ParameterType",
    "FunctionParameter",
    "FunctionSignature",
    "ExecutionContext",
    "ExecutionResult",
    "FunctionRegistry",
    "FunctionSignatureValidator",
    "ExecutionContextValidator",
    "ExecutionResultValidator",
    "create_core_validator",
]
