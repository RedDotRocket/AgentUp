from typing import Any

import structlog

from agent.config import load_config
from agent.config.models import AgentConfig, ServiceConfig
from agent.llm_providers.anthropic import AnthropicProvider
from agent.llm_providers.ollama import OllamaProvider
from agent.llm_providers.openai import OpenAIProvider
from agent.mcp_support.mcp_client import MCPClientService
from agent.mcp_support.mcp_http_client import MCPHTTPClientService
from agent.mcp_support.mcp_server import MCPServerComponent
from agent.utils.helpers import load_callable

logger = structlog.get_logger(__name__)


class ServiceError(Exception):
    """Custom exception for service-related errors."""

    pass


class Service:
    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self._initialized = False

    async def initialize(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def health_check(self) -> dict[str, Any]:
        return {"status": "unknown"}

    @property
    def is_initialized(self) -> bool:
        return self._initialized


class CacheService(Service):
    """
    Service for caching (Valkey, Memcached, etc.).
    """

    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        self.url = config.get("url", "valkey://localhost:6379")
        self.ttl = config.get("ttl", 3600)
        self.client = None

    async def initialize(self) -> None:
        logger.info(f"Cache service {self.name} initialized with URL: {self.url}")
        self._initialized = True

    async def close(self) -> None:
        if self.client:
            pass
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        try:
            return {"status": "healthy", "url": self.url}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get(self, key: str) -> Any | None:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Cache GET: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Cache SET: {key}")

    async def delete(self, key: str) -> None:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Cache DELETE: {key}")


class WebAPIService(Service):

    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30.0)

    async def initialize(self) -> None:
        logger.info(f"Web API service {self.name} initialized with base URL: {self.base_url}")
        self._initialized = True

    async def close(self) -> None:
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        try:
            return {"status": "healthy", "base_url": self.base_url}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get(self, endpoint: str, params: dict | None = None) -> Any:
        if not self._initialized:
            await self.initialize()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.info(f"API GET: {url}")
        return {"result": "api_response"}

    async def post(self, endpoint: str, data: dict | None = None) -> Any:
        """Make POST request."""
        if not self._initialized:
            await self.initialize()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.info(f"API POST: {url}")
        return {"result": "api_response"}


class ServiceRegistry:
    """
    Registry for managing services with LLM provider support.
    """

    def __init__(self, config: AgentConfig | None = None):
        raw = load_config() if config is None else config.dict()
        self.config = AgentConfig.model_validate(raw)

        self._services: dict[str, Service] = {}
        # Map LLM providers to their classes
        self._llm_providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "ollama": OllamaProvider,
        }
        # Service type mapping for registration
        self._service_types: dict[str, Any] = {
            "llm": "llm",
            "cache": CacheService,
            "web_api": WebAPIService,
        }
        self._factories: dict[str, Any] = {
            "llm": "llm",
            "cache": CacheService,
            "web_api": WebAPIService,
        }

        if self.config.mcp_enabled:
            if MCPClientService:
                self._factories["mcp_client"] = MCPClientService
                self._service_types["mcp_client"] = MCPClientService
            if MCPServerComponent:
                self._factories["mcp_server"] = MCPServerComponent
                self._service_types["mcp_server"] = MCPServerComponent

    def initialize_all(self):
        """Instantiate every service declared in `config.services`."""
        for name, raw_svc in (self.config.services or {}).items():
            svc_conf = ServiceConfig.model_validate(raw_svc)

            if svc_conf.init_path:
                factory = load_callable(svc_conf.init_path)
                if not factory:
                    continue
            else:
                factory = self._factories.get(svc_conf.type)
                if not factory:
                    continue

            # 5) call the factory with the name + its own config dict
            instance = factory(name=name, config=svc_conf.settings or {})
            self._services[name] = instance

    def _create_llm_service(self, name: str, config: dict[str, Any]) -> Service:
        """
        Create LLM service based on provider.
        """
        provider = config.get("provider")
        if not provider:
            raise ServiceError(f"LLM service '{name}' missing 'provider' configuration")

        logger.info(f"Creating LLM service '{name}' with provider '{provider}'")

        if provider not in self._llm_providers:
            available_providers = list(self._llm_providers.keys())
            raise ServiceError(f"Unknown LLM provider '{provider}'. Available providers: {available_providers}")

        provider_class = self._llm_providers[provider]
        logger.info(f"Using provider class: {provider_class}")
        service = provider_class(name, config)
        logger.info(
            f"Created service instance: {type(service)} with has_capability: {hasattr(service, 'has_capability')}"
        )
        return service

    def register_service_type(self, type_name: str, service_class: type[Service]) -> None:
        self._service_types[type_name] = service_class

    async def register_service(self, name: str, service_type: str, config: dict[str, Any]) -> None:
        logger.info(f"Registering service '{name}' with type '{service_type}'")

        if service_type not in self._factories:
            raise ServiceError(f"Unknown service type: {service_type}")

        try:
            factory = self._factories[service_type]

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

            self._services[name] = service
            logger.info(f"Successfully registered service {name} of type {service_type} as {type(service)}")
        except Exception as e:
            logger.error(f"Failed to register service {name}: {e}")
            raise ServiceError(f"Failed to register service {name}: {e}") from e

    def get_service(self, name: str) -> Service | None:
        return self._services.get(name)

    def get_llm(self, name: str) -> Service | None:
        """Get LLM service by name."""
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

    def get_mcp_http_client(self, name: str = "mcp_http_client") -> Any | None:
        service = self.get_service(name)
        if MCPHTTPClientService and isinstance(service, MCPHTTPClientService):
            return service
        return None

    def get_mcp_server(self, name: str = "mcp_server") -> Any | None:
        service = self.get_service(name)
        if MCPServerComponent and isinstance(service, MCPServerComponent):
            return service
        return None

    def get_any_mcp_client(self) -> Any | None:
        # TODO: Look at this logic again, I am not that happy with it.
        # Try HTTP client first
        http_client = self.get_mcp_http_client()
        if http_client:
            return http_client

        # Fall back to stdio client
        stdio_client = self.get_mcp_client()
        return stdio_client

    async def close_all(self) -> None:
        for service in self._services.values():
            try:
                await service.close()
            except Exception as e:
                logger.error(f"Error closing service {service.name}: {e}")

    def list_services(self) -> list[str]:
        return list(self._services.keys())

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        results = {}
        for name, service in self._services.items():
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
