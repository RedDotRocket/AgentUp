"""
Pydantic models for the AgentUp plugin system.

This module defines all plugin-related data structures using Pydantic models
for type safety and validation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from a2a.types import Task
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator, model_validator

from ..types import JsonValue
from ..utils.validation import BaseValidator, CompositeValidator
from ..utils.validation import ValidationResult as FrameworkValidationResult


class PluginStatus(str, Enum):
    """Plugin status states."""

    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class CapabilityType(str, Enum):
    """Capability feature types."""

    TEXT = "text"
    MULTIMODAL = "multimodal"
    AI_FUNCTION = "ai_function"
    STREAMING = "streaming"
    STATEFUL = "stateful"


class PluginInfo(BaseModel):
    """Information about a loaded plugin."""

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
        """Validate plugin name format."""
        import re

        if not re.match(r"^[a-z][a-z0-9_-]*$", v):
            raise ValueError("Plugin name must be lowercase with hyphens/underscores")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[\w\.-]+)?(\+[\w\.-]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v

    @model_validator(mode="after")
    def validate_plugin_consistency(self) -> PluginInfo:
        """Validate plugin state consistency."""
        if self.status == PluginStatus.ERROR and not self.error:
            raise ValueError("ERROR status requires error message")

        if self.status != PluginStatus.ERROR and self.error:
            self.error = None  # Clear error for non-error states

        return self

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_operational(self) -> bool:
        """Check if plugin is operational (enabled or loaded)."""
        return self.status in (PluginStatus.ENABLED, PluginStatus.LOADED)

    @computed_field
    @property
    def has_error(self) -> bool:
        """Check if plugin has an error."""
        return self.status == PluginStatus.ERROR or self.error is not None

    @computed_field
    @property
    def display_name(self) -> str:
        """Get display name with author if available."""
        if self.author:
            return f"{self.name} by {self.author}"
        return self.name

    @computed_field
    @property
    def full_version_info(self) -> str:
        """Get full version information."""
        return f"{self.name}@{self.version}"

    @field_serializer("status")
    def serialize_status(self, value: PluginStatus) -> str:
        """Serialize status to string."""
        return value.value


class CapabilityInfo(BaseModel):
    """Information about a capability provided by a plugin."""

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
        """Validate capability ID format."""
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", v):
            raise ValueError("Capability ID must start with letter, contain only alphanumeric, hyphens, underscores")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[\w\.-]+)?(\+[\w\.-]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v

    @field_validator("input_mode", "output_mode")
    @classmethod
    def validate_modes(cls, v: str) -> str:
        """Validate input/output modes."""
        valid_modes = {"text", "json", "binary", "stream", "multimodal"}
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of {valid_modes}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tags format."""
        for tag in v:
            if not tag or not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid tag format: '{tag}'")
        return v

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_ai_capability(self) -> bool:
        """Check if this is an AI function capability."""
        return CapabilityType.AI_FUNCTION in self.capabilities

    @computed_field
    @property
    def is_multimodal(self) -> bool:
        """Check if capability supports multimodal input/output."""
        return (
            CapabilityType.MULTIMODAL in self.capabilities
            or self.input_mode == "multimodal"
            or self.output_mode == "multimodal"
        )

    @computed_field
    @property
    def is_streaming(self) -> bool:
        """Check if capability supports streaming."""
        return (
            CapabilityType.STREAMING in self.capabilities or self.input_mode == "stream" or self.output_mode == "stream"
        )

    @computed_field
    @property
    def is_high_priority(self) -> bool:
        """Check if capability has high priority."""
        return self.priority >= 80

    @computed_field
    @property
    def full_id(self) -> str:
        """Get full capability identifier with plugin name."""
        if self.plugin_name:
            return f"{self.plugin_name}.{self.id}"
        return self.id

    @computed_field
    @property
    def security_score(self) -> float:
        """Calculate security score based on required scopes (0.0 to 1.0)."""
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
        """Serialize capability types to strings."""
        return [cap.value for cap in value]


class AIFunction(BaseModel):
    """AI function definition for LLM function calling."""

    name: str = Field(..., description="Function name", min_length=1, max_length=64)
    description: str = Field(..., description="Function description", min_length=10, max_length=1024)
    parameters: dict[str, Any] = Field(..., description="JSON schema for parameters")
    handler: Any = Field(..., description="Function handler callable")
    examples: list[dict[str, Any]] = Field(default_factory=list, description="Usage examples")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow callable types

    @field_validator("name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        """Validate function name format."""
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
        """Validate JSON schema for parameters."""
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a valid JSON schema object")

        # Must have type property
        if "type" not in v:
            raise ValueError("Parameters schema must have 'type' property")

        return v


class CapabilityContext(BaseModel):
    """Runtime context provided to capability execution."""

    task: Task = Field(..., description="Task being executed")
    config: dict[str, JsonValue] = Field(default_factory=dict, description="Capability configuration")
    services: Any = Field(default_factory=dict, description="Service registry instance")
    state: dict[str, JsonValue] = Field(default_factory=dict, description="Execution state")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Context metadata")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Task type and service registry


class CapabilityResult(BaseModel):
    """Result from capability execution."""

    content: str = Field(..., description="Result content")
    success: bool = Field(True, description="Whether execution was successful")
    error: str | None = Field(None, description="Error message if execution failed")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Result metadata")
    artifacts: list[dict[str, Any]] = Field(default_factory=list, description="Generated artifacts")
    state_updates: dict[str, JsonValue] = Field(default_factory=dict, description="State updates")

    @model_validator(mode="after")
    def validate_result_consistency(self) -> CapabilityResult:
        """Validate result consistency."""
        if not self.success and not self.error:
            raise ValueError("Failed execution must have error message")

        if self.success and self.error:
            self.error = None  # Clear error for successful execution

        return self


class PluginValidationResult(BaseModel):
    """Result from plugin configuration validation."""

    valid: bool = Field(..., description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: list[str] = Field(default_factory=list, description="Validation suggestions")

    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0

    @property
    def summary(self) -> str:
        """Get validation summary."""
        if self.valid:
            parts = ["Validation passed"]
            if self.warnings:
                parts.append(f"{len(self.warnings)} warnings")
            if self.suggestions:
                parts.append(f"{len(self.suggestions)} suggestions")
            return ", ".join(parts)
        else:
            return f"Validation failed: {len(self.errors)} errors"


# Plugin Validators using validation framework
class PluginInfoValidator(BaseValidator[PluginInfo]):
    """Business rule validator for plugin information."""

    def validate(self, model: PluginInfo) -> FrameworkValidationResult:
        result = FrameworkValidationResult(valid=True)

        # Check for suspicious plugin names
        suspicious_patterns = ["malware", "virus", "hack", "exploit"]
        name_lower = model.name.lower()
        for pattern in suspicious_patterns:
            if pattern in name_lower:
                result.add_warning(f"Plugin name contains suspicious pattern: '{pattern}'")

        # Validate author field for public plugins
        if not model.author and model.status == PluginStatus.ENABLED:
            result.add_suggestion("Consider adding author information for enabled plugins")

        # Check for very long error messages
        if model.error and len(model.error) > 500:
            result.add_warning("Error message is very long - consider summarizing")

        return result


class CapabilityInfoValidator(BaseValidator[CapabilityInfo]):
    """Business rule validator for capability information."""

    def validate(self, model: CapabilityInfo) -> FrameworkValidationResult:
        result = FrameworkValidationResult(valid=True)

        # Check for missing descriptions on important capabilities
        if not model.description and CapabilityType.AI_FUNCTION in model.capabilities:
            result.add_suggestion("AI functions should have descriptions for better user understanding")

        # Validate priority ranges for different capability types
        if CapabilityType.AI_FUNCTION in model.capabilities and model.priority < 20:
            result.add_warning("AI functions typically should have higher priority (>= 20)")

        # Check for excessive required scopes
        if len(model.required_scopes) > 10:
            result.add_warning("Capability requires many scopes - consider if all are necessary")

        # Validate tags are meaningful
        meaningless_tags = {"test", "debug", "temp", "todo"}
        for tag in model.tags:
            if tag.lower() in meaningless_tags:
                result.add_suggestion(f"Consider using more descriptive tag instead of '{tag}'")

        return result


class AIFunctionValidator(BaseValidator[AIFunction]):
    """Business rule validator for AI function definitions."""

    def validate(self, model: AIFunction) -> FrameworkValidationResult:
        result = FrameworkValidationResult(valid=True)

        # Check for dangerous function names
        dangerous_patterns = ["delete", "remove", "destroy", "kill", "terminate"]
        name_lower = model.name.lower()
        for pattern in dangerous_patterns:
            if pattern in name_lower:
                result.add_warning(f"Function name contains potentially dangerous pattern: '{pattern}'")

        # Validate parameter complexity
        params_str = str(model.parameters)
        if len(params_str) > 3000:  # 3KB
            result.add_warning("Function parameters schema is very complex")

        # Check for examples on complex functions
        if not model.examples and len(params_str) > 1000:
            result.add_suggestion("Complex functions should include usage examples")

        return result


# Composite validator for plugin models
def create_plugin_validator() -> CompositeValidator[PluginInfo]:
    """Create a comprehensive plugin validator."""
    validators = [
        PluginInfoValidator(PluginInfo),
    ]
    return CompositeValidator(PluginInfo, validators)


# Re-export key models
__all__ = [
    "PluginStatus",
    "CapabilityType",
    "PluginInfo",
    "CapabilityInfo",
    "AIFunction",
    "CapabilityContext",
    "CapabilityResult",
    "PluginValidationResult",
    "PluginInfoValidator",
    "CapabilityInfoValidator",
    "AIFunctionValidator",
    "create_plugin_validator",
]
