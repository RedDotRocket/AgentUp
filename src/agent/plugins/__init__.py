"""
AgentUp Plugin System

A modern plugin architecture using pluggy for extensible AI agent skills.
"""

from .hookspecs import CapabilitySpec, hookspec
from .manager import PluginManager, get_plugin_manager
from .models import (
    AIFunction,
    CapabilityContext,
    CapabilityInfo,
    CapabilityResult,
    CapabilityType,
    PluginInfo,
    ValidationResult,
)

__all__ = [
    # Hook specifications
    "CapabilitySpec",
    "hookspec",
    # Plugin management
    "PluginManager",
    "get_plugin_manager",
    # Data models
    "CapabilityContext",
    "CapabilityInfo",
    "CapabilityResult",
    "CapabilityType",
    "PluginInfo",
    "AIFunction",
    "ValidationResult",
]
