"""
Data models for the AgentUp plugin system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from a2a.types import Task


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


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""

    name: str
    version: str
    author: str | None = None
    description: str | None = None
    status: PluginStatus = PluginStatus.LOADED
    error: str | None = None
    module_name: str | None = None
    entry_point: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityInfo:
    """Information about a capability provided by a plugin."""

    id: str
    name: str
    version: str
    description: str | None = None
    plugin_name: str | None = None  # Name of the plugin providing this capability
    capabilities: list[CapabilityType] = field(default_factory=list)
    input_mode: str = "text"
    output_mode: str = "text"
    tags: list[str] = field(default_factory=list)
    priority: int = 50
    config_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    system_prompt: str | None = None
    required_scopes: list[str] = field(default_factory=list)


@dataclass
class AIFunction:
    """AI function definition for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Any  # Callable[[Task, CapabilityContext], CapabilityResult]
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CapabilityContext:
    """Runtime context provided to capability execution."""

    task: Task
    config: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityResult:
    """Result from capability execution."""

    content: str
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    state_updates: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result from configuration validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
