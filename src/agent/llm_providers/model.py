"""
Pydantic models for AgentUp LLM providers system.

This module defines all LLM provider-related data structures using Pydantic models
for type safety and validation, with enhanced multimodal support.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..types import JsonValue
from ..utils.validation import BaseValidator, CompositeValidator, ValidationResult


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"
    TOOL = "tool"


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE_URL = "image_url"
    IMAGE_FILE = "image_file"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class FunctionCallType(str, Enum):
    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    COHERE = "cohere"
    CUSTOM = "custom"


class MultimodalContent(BaseModel):
    type: ContentType = Field(..., description="Content type")
    text: str | None = Field(None, description="Text content")
    image_url: dict[str, str] | None = Field(None, description="Image URL data")
    image_file: dict[str, str] | None = Field(None, description="Image file data")
    audio_data: dict[str, Any] | None = Field(None, description="Audio data")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Content metadata")

    @model_validator(mode="after")
    def validate_content_type(self) -> MultimodalContent:
        if self.type == ContentType.TEXT and not self.text:
            raise ValueError("Text content type requires text field")
        elif self.type == ContentType.IMAGE_URL and not self.image_url:
            raise ValueError("Image URL content type requires image_url field")
        elif self.type == ContentType.IMAGE_FILE and not self.image_file:
            raise ValueError("Image file content type requires image_file field")
        elif self.type == ContentType.AUDIO and not self.audio_data:
            raise ValueError("Audio content type requires audio_data field")

        return self


class ToolCall(BaseModel):
    id: str = Field(..., description="Tool call ID")
    type: Literal["function"] = Field("function", description="Tool call type")
    function: dict[str, str] = Field(..., description="Function call data")

    @field_validator("function")
    @classmethod
    def validate_function_call(cls, v: dict[str, str]) -> dict[str, str]:
        required_fields = {"name", "arguments"}
        if not all(field in v for field in required_fields):
            raise ValueError("Function call must have 'name' and 'arguments' fields")
        return v


class ChatMessage(BaseModel):
    role: MessageRole = Field(..., description="Message role")
    content: str | list[MultimodalContent] = Field(..., description="Message content")
    name: str | None = Field(None, description="Message author name", max_length=64)
    function_call: dict[str, str] | None = Field(None, description="Function call data (deprecated)")
    tool_calls: list[ToolCall] = Field(default_factory=list, description="Tool calls")
    tool_call_id: str | None = Field(None, description="Tool call ID for function responses")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | list[MultimodalContent]) -> str | list[MultimodalContent]:
        if isinstance(v, str):
            if len(v) > 1_000_000:  # 1MB limit for text content
                raise ValueError("Text content exceeds 1MB limit")
        elif isinstance(v, list):
            if len(v) == 0:
                raise ValueError("Multimodal content list cannot be empty")
            if len(v) > 20:  # Reasonable limit for multimodal items
                raise ValueError("Too many multimodal content items (max 20)")
        else:
            raise ValueError("Content must be string or list of MultimodalContent")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v and not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Name must contain only alphanumeric characters, hyphens, underscores, and dots")
        return v

    @model_validator(mode="after")
    def validate_message_consistency(self) -> ChatMessage:
        # Function role requires tool_call_id
        if self.role == MessageRole.FUNCTION and not self.tool_call_id:
            raise ValueError("Function messages require tool_call_id")

        # Tool role requires tool_call_id
        if self.role == MessageRole.TOOL and not self.tool_call_id:
            raise ValueError("Tool messages require tool_call_id")

        # Assistant messages with tool calls
        if self.role == MessageRole.ASSISTANT and self.tool_calls:
            for tool_call in self.tool_calls:
                if not tool_call.id:
                    raise ValueError("Tool calls must have valid IDs")

        return self


class FunctionParameter(BaseModel):
    type: str = Field(..., description="Parameter type (JSON Schema)")
    description: str | None = Field(None, description="Parameter description")
    enum: list[str] | None = Field(None, description="Allowed values for enum types")
    items: dict[str, Any] | None = Field(None, description="Array item definition")
    properties: dict[str, Any] | None = Field(None, description="Object property definitions")
    required: bool = Field(False, description="Whether parameter is required")

    @field_validator("type")
    @classmethod
    def validate_parameter_type(cls, v: str) -> str:
        valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}
        if v not in valid_types:
            raise ValueError(f"Parameter type must be one of {valid_types}")
        return v


class FunctionDefinition(BaseModel):
    name: str = Field(..., description="Function name", min_length=1, max_length=64)
    description: str = Field(..., description="Function description", min_length=1, max_length=1024)
    parameters: dict[str, Any] = Field(..., description="JSON schema for parameters")
    strict: bool = Field(False, description="Whether to use strict parameter validation")

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

    @field_validator("parameters")
    @classmethod
    def validate_parameters_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a valid JSON schema object")

        # Must have type property
        if "type" not in v:
            raise ValueError("Parameters schema must have 'type' property")

        # For object type, should have properties
        if v.get("type") == "object" and "properties" not in v:
            raise ValueError("Object type parameters should define 'properties'")

        return v

    @model_validator(mode="after")
    def validate_function_definition(self) -> FunctionDefinition:
        # Check description is meaningful
        if len(self.description.strip()) < 10:
            raise ValueError("Function description should be at least 10 characters")

        return self


class LLMConfig(BaseModel):
    provider: LLMProvider = Field(..., description="LLM provider")
    model: str = Field(..., description="Model name/identifier")
    api_key: str | None = Field(None, description="API key (handled securely)")
    api_base: str | None = Field(None, description="Custom API base URL")

    # Generation parameters
    max_tokens: int = Field(4096, description="Maximum tokens to generate", gt=0, le=128000)
    temperature: float = Field(0.7, description="Generation temperature", ge=0.0, le=2.0)
    top_p: float = Field(1.0, description="Nucleus sampling parameter", ge=0.0, le=1.0)
    frequency_penalty: float = Field(0.0, description="Frequency penalty", ge=-2.0, le=2.0)
    presence_penalty: float = Field(0.0, description="Presence penalty", ge=-2.0, le=2.0)

    # Request settings
    timeout: int = Field(120, description="Request timeout in seconds", gt=0, le=600)
    max_retries: int = Field(3, description="Maximum retry attempts", ge=0, le=10)
    retry_delay: float = Field(1.0, description="Initial retry delay in seconds", ge=0.1, le=60.0)

    # Function calling
    supports_functions: bool = Field(True, description="Whether provider supports function calling")
    supports_tools: bool = Field(True, description="Whether provider supports tool calling")
    supports_streaming: bool = Field(True, description="Whether provider supports streaming")
    supports_vision: bool = Field(False, description="Whether provider supports vision/multimodal")

    # Provider-specific settings
    extra_headers: dict[str, str] = Field(default_factory=dict, description="Additional HTTP headers")
    extra_params: dict[str, JsonValue] = Field(default_factory=dict, description="Provider-specific parameters")

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("API base URL must start with http:// or https://")
        return v

    @field_validator("model")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not v or len(v) > 256:
            raise ValueError("Model name must be 1-256 characters")
        return v

    @model_validator(mode="after")
    def validate_llm_config(self) -> LLMConfig:
        # Provider-specific validations
        if self.provider == LLMProvider.ANTHROPIC:
            if self.model.startswith("claude") and self.max_tokens > 100000:
                raise ValueError("Claude models have lower token limits")

        elif self.provider == LLMProvider.OLLAMA:
            if self.api_key:
                raise ValueError("Ollama provider typically doesn't use API keys")

        # Temperature and top_p interaction
        if self.temperature == 0.0 and self.top_p < 1.0:
            raise ValueError("When temperature is 0, top_p should be 1.0 for deterministic output")

        return self


class StreamingResponse(BaseModel):
    id: str = Field(..., description="Response ID")
    object: str = Field("chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: list[dict[str, Any]] = Field(..., description="Response choices")
    usage: dict[str, int] | None = Field(None, description="Token usage (final chunk)")

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not v:
            raise ValueError("Streaming response must have at least one choice")
        return v


class LLMResponse(BaseModel):
    id: str = Field(..., description="Response ID")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: list[dict[str, Any]] = Field(..., description="Response choices")
    usage: dict[str, int] = Field(..., description="Token usage statistics")
    system_fingerprint: str | None = Field(None, description="System fingerprint")

    @property
    def first_choice_message(self) -> dict[str, Any] | None:
        if self.choices:
            return self.choices[0].get("message")
        return None

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


# LLM Validators using validation framework
class ChatMessageValidator(BaseValidator[ChatMessage]):
    def validate(self, model: ChatMessage) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for excessively long messages
        if isinstance(model.content, str) and len(model.content) > 100000:  # 100KB
            result.add_warning("Message content is very long - may impact performance")

        # Check for potential prompt injection patterns
        if isinstance(model.content, str):
            injection_patterns = ["ignore previous", "system:", "assistant:", "jailbreak"]
            content_lower = model.content.lower()
            for pattern in injection_patterns:
                if pattern in content_lower:
                    result.add_warning(f"Potential prompt injection pattern detected: '{pattern}'")

        # Validate multimodal content safety
        if isinstance(model.content, list):
            image_count = sum(
                1 for item in model.content if item.type in [ContentType.IMAGE_URL, ContentType.IMAGE_FILE]
            )
            if image_count > 10:
                result.add_warning("Large number of images may impact processing time and costs")

        return result


class FunctionDefinitionValidator(BaseValidator[FunctionDefinition]):
    def validate(self, model: FunctionDefinition) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for dangerous function names
        dangerous_patterns = ["delete", "remove", "destroy", "kill", "terminate", "shutdown"]
        name_lower = model.name.lower()
        for pattern in dangerous_patterns:
            if pattern in name_lower:
                result.add_warning(f"Function name contains potentially dangerous pattern: '{pattern}'")

        # Validate parameter complexity
        params_str = str(model.parameters)
        if len(params_str) > 5000:  # 5KB
            result.add_warning("Function parameters schema is very complex")

        # Check for required parameters documentation
        if model.parameters.get("type") == "object":
            properties = model.parameters.get("properties", {})
            required = model.parameters.get("required", [])

            for req_param in required:
                if req_param in properties:
                    param_def = properties[req_param]
                    if not param_def.get("description"):
                        result.add_suggestion(f"Required parameter '{req_param}' should have a description")

        return result


class LLMConfigValidator(BaseValidator[LLMConfig]):
    def validate(self, model: LLMConfig) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for potentially expensive configurations
        if model.max_tokens > 50000:
            result.add_warning("High max_tokens setting may result in expensive API calls")

        # Validate provider-model compatibility
        known_models = {
            LLMProvider.OPENAI: ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
            LLMProvider.ANTHROPIC: ["claude-3", "claude-2", "claude-instant"],
            LLMProvider.OLLAMA: ["llama2", "codellama", "mistral"],
        }

        if model.provider in known_models:
            provider_models = known_models[model.provider]
            if not any(known_model in model.model for known_model in provider_models):
                result.add_suggestion(f"Model '{model.model}' may not be compatible with {model.provider}")

        # Check timeout settings
        if model.timeout < 30:
            result.add_warning("Short timeout may cause requests to fail for large responses")
        elif model.timeout > 300:
            result.add_suggestion("Long timeout may cause slow error detection")

        return result


# Composite validator for LLM models
def create_llm_validator() -> CompositeValidator[LLMConfig]:
    validators = [
        LLMConfigValidator(LLMConfig),
    ]
    return CompositeValidator(LLMConfig, validators)


# Re-export key models
__all__ = [
    "MessageRole",
    "ContentType",
    "FunctionCallType",
    "LLMProvider",
    "MultimodalContent",
    "ToolCall",
    "ChatMessage",
    "FunctionParameter",
    "FunctionDefinition",
    "LLMConfig",
    "StreamingResponse",
    "LLMResponse",
    "ChatMessageValidator",
    "FunctionDefinitionValidator",
    "LLMConfigValidator",
    "create_llm_validator",
]
