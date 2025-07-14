"""AgentUp Service Layer

This module provides a service-oriented architecture for the AgentUp framework,
encapsulating core functionality into cohesive, testable services.

New Services:
- ConfigurationManager: Singleton configuration management with caching
- CapabilityRegistry: Unified capability registration and execution
- AgentBootstrapper: Orchestrates service initialization
- SecurityService: Authentication and authorization
- MiddlewareManager: Middleware configuration and application
- StateManager: Conversation and application state management
- PluginService: Plugin loading and capability registration
- MCPService: Model Context Protocol integration
- PushNotificationService: Push notification handling

Legacy Services (for backwards compatibility):
- ServiceRegistry: External service integration
- CacheService, WebAPIService: External service types
- MultiModalProcessor: Multimodal processing
"""

# New service layer
# Legacy services for backwards compatibility
from agent.config import load_config

from .base import Service
from .bootstrap import AgentBootstrapper
from .capabilities import CapabilityMetadata, CapabilityRegistry
from .config import ConfigurationManager
from .mcp import MCPService
from .middleware import MiddlewareManager
from .multimodal import MultiModalProcessor
from .plugins import PluginService
from .push import PushNotificationService
from .registry import (
    CacheService,
    ServiceError,
    ServiceRegistry,
    WebAPIService,
    get_services,
)
from .registry import (
    # DatabaseService,
    Service as LegacyService,
)
from .security import SecurityService
from .state import StateManager

__all__ = [
    # New service layer
    "Service",
    "ConfigurationManager",
    "CapabilityRegistry",
    "CapabilityMetadata",
    "AgentBootstrapper",
    "SecurityService",
    "MiddlewareManager",
    "StateManager",
    "PluginService",
    "MCPService",
    "PushNotificationService",
    # Legacy services
    "get_services",
    "initialize_services",
    "initialize_services_from_config",
    "LegacyService",
    "ServiceError",
    "ServiceRegistry",
    "CacheService",
    "WebAPIService",
    "MultiModalProcessor",
    "load_config",
]
