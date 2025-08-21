from typing import Any

import structlog
from pydantic import BaseModel, Field

from agent.config import Config
from agent.config.model import AgentConfig, ServiceConfig
from agent.llm_providers.anthropic import AnthropicProvider
from agent.llm_providers.ollama import OllamaProvider
from agent.llm_providers.openai import OpenAIProvider
from agent.mcp_support.mcp_client import MCPClientService
from agent.mcp_support.mcp_server import MCPServerComponent
from agent.utils.helpers import load_callable

logger = structlog.get_logger(__name__)


class ServiceError(Exception):
    pass


class Service(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(..., description="Service name")
    config: dict[str, Any] = Field(default_factory=dict, description="Service configuration")
    initialized: bool = Field(default=False, exclude=True, description="Initialization status", alias="_initialized")

    def __init__(self, name: str = None, config: dict[str, Any] = None, **data):
        if name is not None and config is not None:
            # Old-style positional arguments
            super().__init__(name=name, config=config, **data)
        else:
            # New-style keyword arguments
            super().__init__(**data)

    async def initialize(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def health_check(self) -> dict[str, Any]:
        return {"status": "unknown"}

    @property
    def is_initialized(self) -> bool:
        return self.initialized


class CacheService(Service):
    """
    Service for caching (Valkey, Memcached, etc.).
    """

    url: str = Field(default="valkey://localhost:6379", description="Cache service URL")
    ttl: int = Field(default=3600, description="Default TTL in seconds")
    client: Any = Field(default=None, exclude=True, description="Cache client instance")

    def __init__(self, name: str, config: dict[str, Any], **data):
        # Extract cache-specific config with defaults
        url = config.get("url", "valkey://localhost:6379")
        ttl = config.get("ttl", 3600)

        super().__init__(name=name, config=config, url=url, ttl=ttl, **data)

    async def initialize(self) -> None:
        logger.info(f"Cache service {self.name} initialized with URL: {self.url}")
        self.initialized = True

    async def close(self) -> None:
        if self.client:
            pass
        self.initialized = False

    async def health_check(self) -> dict[str, Any]:
        try:
            return {"status": "healthy", "url": self.url}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get(self, key: str) -> Any | None:
        if not self.initialized:
            await self.initialize()

        logger.info(f"Cache GET: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if not self.initialized:
            await self.initialize()

        logger.info(f"Cache SET: {key}")
        # Use provided ttl or default from instance
        _ = ttl or self.ttl  # Acknowledge the parameters

    async def delete(self, key: str) -> None:
        if not self.initialized:
            await self.initialize()

        logger.info(f"Cache DELETE: {key}")


class WebAPIService(Service):
    base_url: str = Field(default="", description="Base URL for API")
    api_key: str = Field(default="", description="API key for authentication")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")

    def __init__(self, name: str, config: dict[str, Any], **data):
        # Extract web API specific config with defaults
        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30.0)

        super().__init__(
            name=name, config=config, base_url=base_url, api_key=api_key, headers=headers, timeout=timeout, **data
        )

    async def initialize(self) -> None:
        logger.info(f"Web API service {self.name} initialized with base URL: {self.base_url}")
        self.initialized = True

    async def close(self) -> None:
        self.initialized = False

    async def health_check(self) -> dict[str, Any]:
        try:
            return {"status": "healthy", "base_url": self.base_url}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get(self, endpoint: str, params: dict | None = None) -> Any:
        if not self.initialized:
            await self.initialize()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.info(f"API GET: {url}")
        # Acknowledge params parameter
        _ = params
        return {"result": "api_response"}

    async def post(self, endpoint: str, data: dict | None = None) -> Any:
        if not self.initialized:
            await self.initialize()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.info(f"API POST: {url}")
        # Acknowledge data parameter
        _ = data
        return {"result": "api_response"}


class ServiceRegistry(BaseModel):
    """
    Registry for managing services with LLM provider support.
    """

    model_config = {"arbitrary_types_allowed": True}  # Allow non-serializable types

    config: AgentConfig = Field(..., description="Agent configuration")
    services: dict[str, str] = Field(default_factory=dict, description="Registered services")
    service_instances: dict[str, Service] = Field(
        default_factory=dict, exclude=True, description="Internal service instances"
    )
    llm_providers: dict[str, Any] = Field(default_factory=dict, exclude=True, description="LLM provider classes")
    service_types: dict[str, Any] = Field(default_factory=dict, exclude=True, description="Service type mappings")
    factories: dict[str, Any] = Field(default_factory=dict, exclude=True, description="Service factories")

    def __init__(self, config: AgentConfig | None = None, **data):
        raw = Config.model_dump() if config is None else config.model_dump()
        # Filter out orchestrator field which only exists in Settings, not AgentConfig
        raw.pop("orchestrator", None)
        # Handle ai_provider conversion from Settings (which can be None) to AgentConfig (which expects dict)
        if raw.get("ai_provider") is None:
            raw["ai_provider"] = {}
        agent_config = AgentConfig.model_validate(raw)

        # Initialize Pydantic fields
        super().__init__(config=agent_config, **data)

        # Set up internal mappings after Pydantic initialization
        self.llm_providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "ollama": OllamaProvider,
        }
        # Service type mapping for registration
        self.service_types = {
            "llm": "llm",
            "cache": CacheService,
            "web_api": WebAPIService,
        }
        self.factories = {
            "llm": "llm",
            "cache": CacheService,
            "web_api": WebAPIService,
        }

        if self.config.mcp_enabled:
            if MCPClientService:
                self.factories["mcp_client"] = MCPClientService
                self.service_types["mcp_client"] = MCPClientService
            if MCPServerComponent:
                self.factories["mcp_server"] = MCPServerComponent
                self.service_types["mcp_server"] = MCPServerComponent

    # Backward compatibility properties
    @property
    def _services(self) -> dict[str, Service]:
        return self.service_instances

    @property
    def _llm_providers(self) -> dict[str, Any]:
        return self.llm_providers

    @property
    def _service_types(self) -> dict[str, Any]:
        return self.service_types

    @property
    def _factories(self) -> dict[str, Any]:
        return self.factories

    def initialize_all(self):
        for name, raw_svc in (self.config.services or {}).items():
            svc_conf = ServiceConfig.model_validate(raw_svc)

            if svc_conf.init_path:
                factory = load_callable(svc_conf.init_path)
                if not factory:
                    continue
            else:
                factory = self.factories.get(svc_conf.type)
                if not factory:
                    continue

            # call the factory with the name + its own config dict
            instance = factory(name=name, config=svc_conf.settings or {})
            self.service_instances[name] = instance
            # Update Pydantic field with string representation
            self.services[name] = str(instance)

    def _create_llm_service(self, name: str, config: dict[str, Any]) -> Service:
        """
        Create LLM service based on provider.
        """
        provider = config.get("provider")
        if not provider:
            raise ServiceError(f"LLM service '{name}' missing 'provider' configuration")

        logger.info(f"Creating LLM service '{name}' with provider '{provider}'")

        if provider not in self.llm_providers:
            available_providers = list(self.llm_providers.keys())
            raise ServiceError(f"Unknown LLM provider '{provider}'. Available providers: {available_providers}")

        provider_class = self.llm_providers[provider]
        logger.info(f"Using provider class: {provider_class}")
        service = provider_class(name, config)
        logger.info(
            f"Created service instance: {type(service)} with has_capability: {hasattr(service, 'has_capability')}"
        )
        return service

    def register_service_type(self, type_name: str, service_class: type[Service]) -> None:
        self.service_types[type_name] = service_class

    async def register_service(self, name: str, service_type: str, config: dict[str, Any]) -> None:
        logger.info(f"Registering service '{name}' with type '{service_type}'")

        if service_type not in self.factories:
            raise ServiceError(f"Unknown service type: {service_type}")

        try:
            factory = self.factories[service_type]

            # Handle different factory types
            if service_type == "llm":
                logger.info(f"Creating LLM service for '{name}'")
                service = self._create_llm_service(name, config)
            elif callable(factory):
                logger.info(f"Using callable factory for '{name}'")
                service = factory(name, config)
            else:
                logger.info(f"Using service class {factory} for '{name}'")
                service_class = factory
                service = service_class(name, config)

            logger.info(f"Created service instance of type: {type(service)}")

            if config.get("enabled", True):
                await service.initialize()

            self.service_instances[name] = service
            # Update Pydantic field with string representation
            self.services[name] = str(service)
            logger.info(f"Successfully registered service {name} of type {service_type} as {type(service)}")
        except Exception as e:
            logger.error(f"Failed to register service {name}: {e}")
            raise ServiceError(f"Failed to register service {name}: {e}") from e

    def get_service(self, name: str) -> Service | None:
        return self.service_instances.get(name)

    def get_llm(self, name: str) -> Service | None:
        service = self.get_service(name)
        if service and hasattr(service, "chat_complete"):
            return service
        return None

    def get_cache(self, name: str = "cache") -> CacheService | None:
        service = self.get_service(name)
        if isinstance(service, CacheService):
            return service
        return None

    def get_web_api(self, name: str) -> WebAPIService | None:
        service = self.get_service(name)
        if isinstance(service, WebAPIService):
            return service
        return None

    def get_mcp_client(self, name: str = "mcp_client") -> Any | None:
        service = self.get_service(name)
        if MCPClientService and isinstance(service, MCPClientService):
            return service
        return None

    def get_mcp_server(self, name: str = "mcp_server") -> Any | None:
        service = self.get_service(name)
        if MCPServerComponent and isinstance(service, MCPServerComponent):
            return service
        return None

    def get_any_mcp_client(self) -> Any | None:
        """Get the unified MCP client that supports all transport types."""
        return self.get_mcp_client()

    async def close_all(self) -> None:
        for service in self.service_instances.values():
            try:
                await service.close()
            except Exception as e:
                logger.error(f"Error closing service {service.name}: {e}")

    def list_services(self) -> list[str]:
        return list(self.service_instances.keys())

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        results = {}
        for name, service in self.service_instances.items():
            try:
                results[name] = await service.health_check()
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        return results


# Global service registry
_registry: ServiceRegistry | None = None


def get_services() -> ServiceRegistry:
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry


async def close_services() -> None:
    global _registry
    if _registry:
        await _registry.close_all()
        _registry = None
