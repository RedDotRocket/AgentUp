"""
AgentUp Plugin System

This relies on the `pluggy` library to manage plugins and their capabilities.
It provides a structured way to define, manage, and validate plugins and their capabilities.
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
    PluginValidationResult,
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
    "PluginValidationResult",
]
