"""
Decorator-based plugin system for AgentUp.

This module provides decorators and base classes that replace the Pluggy-based
hook system with a more intuitive decorator approach.
"""

import functools
from collections.abc import Callable
from dataclasses import dataclass, field

from .models import CapabilityType


@dataclass
class CapabilityMetadata:
    """Stores all metadata for a capability"""

    id: str
    name: str
    description: str
    method_name: str
    scopes: list[str] = field(default_factory=list)
    ai_function: bool = False
    ai_parameters: dict = field(default_factory=dict)
    input_mode: str = "text"
    output_mode: str = "text"
    tags: list[str] = field(default_factory=list)
    priority: int = 50
    middleware: list[dict] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)
    state_schema: dict = field(default_factory=dict)
    streaming: bool = False
    multimodal: bool = False
    handler: Callable | None = None
    # A2A AgentSkill fields
    examples: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    output_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    security: list[dict[str, list[str]]] = field(default_factory=list)

    def to_capability_types(self) -> list[CapabilityType]:
        """Convert metadata to CapabilityType list"""
        types = [CapabilityType.TEXT]  # Default

        if self.ai_function:
            types.append(CapabilityType.AI_FUNCTION)
        if self.streaming:
            types.append(CapabilityType.STREAMING)
        if self.multimodal:
            types.append(CapabilityType.MULTIMODAL)
        if self.state_schema:
            types.append(CapabilityType.STATEFUL)

        return types


def capability(
    id: str,
    name: str | None = None,
    description: str | None = None,
    scopes: list[str] | None = None,
    ai_function: bool = False,
    ai_parameters: dict | None = None,
    input_mode: str = "text",
    output_mode: str = "text",
    tags: list[str] | None = None,
    priority: int = 50,
    middleware: list[dict] | None = None,
    config_schema: dict | None = None,
    state_schema: dict | None = None,
    streaming: bool = False,
    multimodal: bool = False,
    # A2A AgentSkill parameters
    examples: list[str] | None = None,
    input_modes: list[str] | None = None,
    output_modes: list[str] | None = None,
    security: list[dict[str, list[str]]] | None = None,
) -> Callable:
    """
    Decorator that marks a method as a plugin capability.

    This decorator replaces the need for manual hook implementations by
    automatically generating all necessary plugin metadata and handlers.

    Args:
        id: Unique capability identifier
        name: Human-readable capability name
        description: Capability description
        scopes: Required permission scopes
        ai_function: Whether this capability can be called by AI
        ai_parameters: JSON schema for AI function parameters
        input_mode: Input mode (text, json, binary, stream, multimodal)
        output_mode: Output mode (text, json, binary, stream, multimodal)
        tags: Tags for capability discovery and routing
        priority: Capability priority (0-100, higher = more priority)
        middleware: Middleware configuration for this capability
        config_schema: JSON schema for capability configuration
        state_schema: JSON schema for capability state
        streaming: Whether capability supports streaming
        multimodal: Whether capability supports multimodal input/output
        examples: Example usage strings for A2A AgentSkill
        input_modes: List of supported input MIME types (A2A AgentSkill)
        output_modes: List of supported output MIME types (A2A AgentSkill)
        security: Security requirements for A2A AgentSkill


    Returns:
        Decorated function with capability metadata attached

    Example:
        @capability(
            "weather",
            name="Weather Lookup",
            description="Get current weather for a location",
            scopes=["web:search"],
            ai_function=True,
            ai_parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                }
            }
        )
        async def get_weather(self, context: CapabilityContext) -> str:
            return "Weather data"
    """

    def decorator(func: Callable) -> Callable:
        # Create metadata object
        metadata = CapabilityMetadata(
            id=id,
            name=name or id.replace("_", " ").title(),
            description=description or func.__doc__ or f"Capability {id}",
            method_name=func.__name__,
            scopes=scopes or [],
            ai_function=ai_function,
            ai_parameters=ai_parameters or {},
            input_mode=input_mode,
            output_mode=output_mode,
            tags=tags or [],
            priority=priority,
            middleware=middleware or [],
            config_schema=config_schema or {},
            state_schema=state_schema or {},
            streaming=streaming,
            multimodal=multimodal,
            handler=func,
            # A2A AgentSkill parameters
            examples=examples or [],
            input_modes=input_modes if input_modes is not None else ["text/plain"],
            output_modes=output_modes if output_modes is not None else ["text/plain"],
            security=security or [],
        )

        # Store metadata on the function
        if not hasattr(func, "_agentup_capabilities"):
            func._agentup_capabilities = []
        func._agentup_capabilities.append(metadata)

        # Mark the function as a capability handler
        func._is_agentup_capability = True

        # Preserve original function metadata
        functools.update_wrapper(func, func)

        return func

    return decorator


def ai_function(parameters: dict, name: str | None = None, description: str | None = None) -> Callable:
    """
    Decorator that marks a capability method as an AI function.

    This is a convenience decorator that combines @capability with ai_function=True.

    Args:
        parameters: JSON schema for AI function parameters
        name: Function name (defaults to method name)
        description: Function description (defaults to method docstring)

    Example:
        @ai_function(
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"}
                }
            }
        )
        async def analyze_text(self, context: CapabilityContext) -> str:
            return "Analysis result"
    """

    def decorator(func: Callable) -> Callable:
        # Extract capability ID from method name
        capability_id = func.__name__

        # Apply @capability decorator with AI function settings
        return capability(
            id=capability_id,
            name=name or capability_id.replace("_", " ").title(),
            description=description or func.__doc__,
            ai_function=True,
            ai_parameters=parameters,
        )(func)

    return decorator


def validate_capability_metadata(metadata: CapabilityMetadata) -> list[str]:
    """
    Validate capability metadata for common issues.

    Args:
        metadata: Capability metadata to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate ID format
    if not metadata.id or not metadata.id.replace("_", "").replace("-", "").isalnum():
        errors.append(f"Invalid capability ID: '{metadata.id}'. Must be alphanumeric with underscores/hyphens.")

    # Validate input/output modes
    valid_modes = {"text", "json", "binary", "stream", "multimodal"}
    if metadata.input_mode not in valid_modes:
        errors.append(f"Invalid input_mode: '{metadata.input_mode}'. Must be one of {valid_modes}")
    if metadata.output_mode not in valid_modes:
        errors.append(f"Invalid output_mode: '{metadata.output_mode}'. Must be one of {valid_modes}")

    # Validate priority range
    if not 0 <= metadata.priority <= 100:
        errors.append(f"Invalid priority: {metadata.priority}. Must be between 0 and 100.")

    # Validate AI function parameters
    if metadata.ai_function and not metadata.ai_parameters:
        errors.append("AI functions must specify ai_parameters schema")

    if metadata.ai_parameters:
        if not isinstance(metadata.ai_parameters, dict):
            errors.append("ai_parameters must be a dictionary (JSON schema)")
        elif "type" not in metadata.ai_parameters:
            errors.append("ai_parameters must have 'type' property")

    # Validate tags
    for tag in metadata.tags:
        if not tag or not tag.replace("-", "").replace("_", "").isalnum():
            errors.append(f"Invalid tag format: '{tag}'. Must be alphanumeric with hyphens/underscores.")

    # Validate scopes format
    for scope in metadata.scopes:
        if not scope:
            errors.append(f"Invalid scope format: '{scope}'. Scope cannot be empty")
        elif scope == "*":
            # Universal admin scope is valid
            continue
        elif scope == "admin":
            # System admin scope is valid
            continue
        elif ":" not in scope:
            errors.append(f"Invalid scope format: '{scope}'. Must be in format 'resource:action', 'admin', or '*'")
        else:
            # Validate resource:action format
            parts = scope.split(":")
            if len(parts) != 2:
                errors.append(f"Invalid scope format: '{scope}'. Must have exactly one ':'")
            elif not parts[0] or not parts[1]:
                errors.append(f"Invalid scope format: '{scope}'. Resource and action cannot be empty")

    return errors


def get_capability_metadata(func: Callable) -> list[CapabilityMetadata]:
    """
    Get capability metadata from a decorated function.

    Args:
        func: Function to inspect

    Returns:
        List of capability metadata objects
    """
    if hasattr(func, "_agentup_capabilities"):
        return func._agentup_capabilities
    return []


def is_capability_handler(func: Callable) -> bool:
    """
    Check if a function is decorated as a capability handler.

    Args:
        func: Function to check

    Returns:
        True if function is a capability handler
    """
    return hasattr(func, "_is_agentup_capability") and func._is_agentup_capability
