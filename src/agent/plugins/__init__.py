"""
AgentUp Plugin System

A modern plugin architecture using pluggy for extensible AI agent skills.
"""

from .hookspecs import SkillSpec, hookspec
from .manager import PluginManager, get_plugin_manager
from .models import (
    AIFunction,
    PluginInfo,
    SkillCapability,
    SkillContext,
    SkillInfo,
    SkillResult,
    ValidationResult,
)

__all__ = [
    # Hook specifications
    "SkillSpec",
    "hookspec",
    # Plugin management
    "PluginManager",
    "get_plugin_manager",
    # Data models
    "PluginInfo",
    "SkillCapability",
    "SkillInfo",
    "SkillContext",
    "SkillResult",
    "AIFunction",
    "ValidationResult",
]
