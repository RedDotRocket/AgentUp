from __future__ import annotations

from enum import Enum
from typing import Any

from a2a.types import Task
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator, model_validator

from ..types import JsonValue


class PluginStatus(str, Enum):
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class CapabilityType(str, Enum):
    TEXT = "text"
    MULTIMODAL = "multimodal"
    AI_FUNCTION = "ai_function"
    STREAMING = "streaming"
    STATEFUL = "stateful"


class PluginDefinition(BaseModel):
    name: str = Field(..., description="Plugin name", min_length=1, max_length=100)
    version: str = Field(..., description="Plugin version")
    author: str | None = Field(None, description="Plugin author")
    description: str | None = Field(None, description="Plugin description")
    status: PluginStatus = Field(PluginStatus.LOADED, description="Plugin status")
    error: str | None = Field(None, description="Error message if plugin failed")
    module_name: str | None = Field(None, description="Python module name")
    entry_point: str | None = Field(None, description="Plugin entry point")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Plugin metadata")

    @field_validator("name")
    @classmethod
    def validate_plugin_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z][a-z0-9_-]*$", v):
            raise ValueError("Plugin name must be lowercase with hyphens/underscores")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[\w\.-]+)?(\+[\w\.-]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v

    @model_validator(mode="after")
    def validate_plugin_consistency(self) -> PluginDefinition:
        if self.status == PluginStatus.ERROR and not self.error:
            raise ValueError("ERROR status requires error message")

        if self.status != PluginStatus.ERROR and self.error:
            self.error = None  # Clear error for non-error states

        return self

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_operational(self) -> bool:
        return self.status in (PluginStatus.ENABLED, PluginStatus.LOADED)

    @computed_field
    @property
    def has_error(self) -> bool:
        return self.status == PluginStatus.ERROR or self.error is not None

    @computed_field
    @property
    def display_name(self) -> str:
        if self.author:
            return f"{self.name} by {self.author}"
        return self.name

    @computed_field
    @property
    def full_version_info(self) -> str:
        return f"{self.name}@{self.version}"

    @field_serializer("status")
    def serialize_status(self, value: PluginStatus) -> str:
        return value.value


class CapabilityDefinition(BaseModel):
    id: str = Field(..., description="Capability identifier", min_length=1, max_length=128)
    name: str = Field(..., description="Human-readable capability name", min_length=1, max_length=100)
    version: str = Field(..., description="Capability version")
    description: str | None = Field(None, description="Capability description")
    plugin_name: str | None = Field(None, description="Name of the plugin providing this capability")
    capabilities: list[CapabilityType] = Field(default_factory=list, description="Capability types")
    input_mode: str = Field("text", description="Input mode format")
    output_mode: str = Field("text", description="Output mode format")
    tags: list[str] = Field(default_factory=list, description="Capability tags")
    priority: int = Field(50, description="Capability priority", ge=0, le=100)
    config_schema: dict[str, Any] = Field(default_factory=dict, description="Configuration schema")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Capability metadata")
    system_prompt: str | None = Field(None, description="System prompt for AI capabilities")
    required_scopes: list[str] = Field(default_factory=list, description="Required permission scopes")

    @field_validator("id")
    @classmethod
    def validate_capability_id(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", v):
            raise ValueError("Capability ID must start with letter, contain only alphanumeric, hyphens, underscores")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[\w\.-]+)?(\+[\w\.-]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v

    @field_validator("input_mode", "output_mode")
    @classmethod
    def validate_modes(cls, v: str) -> str:
        valid_modes = {"text", "json", "binary", "stream", "multimodal"}
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of {valid_modes}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not tag or not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid tag format: '{tag}'")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_ai_capability(self) -> bool:
        return CapabilityType.AI_FUNCTION in self.capabilities

    @computed_field
    @property
    def is_multimodal(self) -> bool:
        return (
            CapabilityType.MULTIMODAL in self.capabilities
            or self.input_mode == "multimodal"
            or self.output_mode == "multimodal"
        )

    @computed_field
    @property
    def is_streaming(self) -> bool:
        return (
            CapabilityType.STREAMING in self.capabilities or self.input_mode == "stream" or self.output_mode == "stream"
        )

    @computed_field
    @property
    def is_high_priority(self) -> bool:
        return self.priority >= 80

    @computed_field
    @property
    def full_id(self) -> str:
        if self.plugin_name:
            return f"{self.plugin_name}.{self.id}"
        return self.id

    @computed_field
    @property
    def security_score(self) -> float:
        if not self.required_scopes:
            return 0.0  # No scopes = low security

        # More scopes = higher security requirements
        scope_count = len(self.required_scopes)
        score = min(1.0, scope_count / 5 * 0.8)  # Max 0.8 from scope count

        # AI functions get extra security weight
        if self.is_ai_capability:
            score += 0.2

        return min(1.0, score)

    @field_serializer("capabilities")
    def serialize_capabilities(self, value: list[CapabilityType]) -> list[str]:
        return [cap.value for cap in value]


class AIFunction(BaseModel):
    name: str = Field(..., description="Function name", min_length=1, max_length=64)
    description: str = Field(..., description="Function description", min_length=10, max_length=1024)
    parameters: dict[str, Any] = Field(..., description="JSON schema for parameters")
    handler: Any = Field(..., description="Function handler callable")
    examples: list[dict[str, Any]] = Field(default_factory=list, description="Usage examples")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow callable types

    @field_validator("name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Function name must be valid Python identifier")

        # Check for reserved names
        reserved_names = {"eval", "exec", "import", "__import__", "compile"}
        if v in reserved_names:
            raise ValueError(f"Function name '{v}' is reserved")
        return v

    @field_validator("parameters")
    @classmethod
    def validate_parameters_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a valid JSON schema object")

        # Must have type property
        if "type" not in v:
            raise ValueError("Parameters schema must have 'type' property")

        return v


class CapabilityContext(BaseModel):
    task: Task = Field(..., description="Task being executed")
    config: dict[str, JsonValue] = Field(default_factory=dict, description="Capability configuration")
    services: Any = Field(default_factory=dict, description="Service registry instance")
    state: dict[str, JsonValue] = Field(default_factory=dict, description="Execution state")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Context metadata")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Task type and service registry


class CapabilityResult(BaseModel):
    content: str = Field(..., description="Result content")
    success: bool = Field(True, description="Whether execution was successful")
    error: str | None = Field(None, description="Error message if execution failed")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Result metadata")
    artifacts: list[dict[str, Any]] = Field(default_factory=list, description="Generated artifacts")
    state_updates: dict[str, JsonValue] = Field(default_factory=dict, description="State updates")

    @model_validator(mode="after")
    def validate_result_consistency(self) -> CapabilityResult:
        if not self.success and not self.error:
            raise ValueError("Failed execution must have error message")

        if self.success and self.error:
            self.error = None  # Clear error for successful execution

        return self


class PluginValidationResult(BaseModel):
    valid: bool = Field(..., description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: list[str] = Field(default_factory=list, description="Validation suggestions")

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def summary(self) -> str:
        if self.valid:
            parts = ["Validation passed"]
            if self.warnings:
                parts.append(f"{len(self.warnings)} warnings")
            if self.suggestions:
                parts.append(f"{len(self.suggestions)} suggestions")
            return ", ".join(parts)
        else:
            return f"Validation failed: {len(self.errors)} errors"


# Re-export key models
__all__ = [
    "PluginStatus",
    "CapabilityType",
    "PluginDefinition",
    "CapabilityDefinition",
    "AIFunction",
    "CapabilityContext",
    "CapabilityResult",
    "PluginValidationResult",
]
