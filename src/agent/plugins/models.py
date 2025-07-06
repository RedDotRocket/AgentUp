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


class SkillCapability(str, Enum):
    """Skill capability types."""

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
class SkillInfo:
    """Information about a skill provided by a plugin."""

    id: str
    name: str
    version: str
    description: str | None = None
    capabilities: list[SkillCapability] = field(default_factory=list)
    input_mode: str = "text"
    output_mode: str = "text"
    tags: list[str] = field(default_factory=list)
    priority: int = 50
    config_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    system_prompt: str | None = None


@dataclass
class AIFunction:
    """AI function definition for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Any  # Callable[[Task, SkillContext], SkillResult]
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SkillContext:
    """Runtime context provided to skill execution."""

    task: Task
    config: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result from skill execution."""

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
