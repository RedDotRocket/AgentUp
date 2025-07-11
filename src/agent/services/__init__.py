"""External services integration for AgentUp agents."""

# Import for backwards compatibility
from ..config import load_config
from .multimodal import MultiModalProcessor
from .registry import (
    CacheService,
    DatabaseService,
    Service,
    ServiceError,
    ServiceRegistry,
    WebAPIService,
    get_services,
)

__all__ = [
    "get_services",
    "initialize_services",
    "initialize_services_from_config",
    "Service",
    "ServiceError",
    "ServiceRegistry",
    "DatabaseService",
    "CacheService",
    "WebAPIService",
    "MultiModalProcessor",
    "load_config",
]
