"""AgentUp Service Layer

This module provides a service-oriented architecture for the AgentUp framework,
encapsulating core functionality into cohesive, testable services.

New Services:
- ConfigurationManager: Singleton configuration management with caching
- BuiltinCapabilityRegistry: Unified capability registration and execution
- AgentBootstrapper: Orchestrates service initialization and plugin integration
- SecurityService: Authentication and authorization
- MiddlewareManager: Middleware configuration and application
- StateManager: Conversation and application state management
- MCPService: Model Context Protocol integration
- PushNotificationService: Push notification handling

Legacy Services (for backwards compatibility):
- ServiceRegistry: External service integration
- CacheService, WebAPIService: External service types
- MultiModalProcessor: Multimodal processing
"""

# New service layer
# Legacy services for backwards compatibility

from .base import Service
from .bootstrap import AgentBootstrapper
from .builtin_capabilities import BuiltinCapabilityRegistry, CapabilityMetadata
from .config import ConfigurationManager
from .mcp import MCPService
from .middleware import MiddlewareManager
from .multimodal import MultiModalProcessor
from .push import PushNotificationService
from .registry import (
    CacheService,
    ServiceError,
    ServiceRegistry,
    WebAPIService,
    get_services,
)
from .security import SecurityService
from .state import StateManager

__all__ = [
    # New service layer
    "Service",
    "ConfigurationManager",
    "BuiltinCapabilityRegistry",
    "CapabilityMetadata",
    "AgentBootstrapper",
    "SecurityService",
    "MiddlewareManager",
    "StateManager",
    "MCPService",
    "PushNotificationService",
    # Legacy services
    "get_services",
    "initialize_services",
    "initialize_services_from_config",
    "ServiceError",
    "ServiceRegistry",
    "CacheService",
    "WebAPIService",
    "MultiModalProcessor",
    "Config",
]
