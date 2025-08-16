from typing import Any

import structlog
from pydantic import BaseModel, Field

from agent.config import Config
from agent.config.model import AgentConfig
from agent.mcp_support.mcp_client import MCPClientService
from agent.mcp_support.mcp_server import MCPServerComponent

logger = structlog.get_logger(__name__)


class ServiceError(Exception):
    pass


class Service(BaseModel):
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


class ServiceRegistry(BaseModel):
    """
    Registry for managing services with LLM provider support.
    """

    config: AgentConfig = Field(..., description="Agent configuration")
    services: dict[str, str] = Field(default_factory=dict, description="Registered services")
    service_instances: dict[str, Service] = Field(
        default_factory=dict, exclude=True, description="Internal service instances"
    )
    service_types: dict[str, Any] = Field(default_factory=dict, exclude=True, description="Service type mappings")

    def __init__(self, config: AgentConfig | None = None, **data):
        raw = Config.model_dump() if config is None else config.model_dump()
        # Filter out orchestrator field which only exists in Settings, not AgentConfig
        raw.pop("orchestrator", None)
        agent_config = AgentConfig.model_validate(raw)

        # Initialize Pydantic fields
        super().__init__(config=agent_config, **data)

        if self.config.mcp_enabled:
            if MCPClientService:
                self.service_types["mcp_client"] = MCPClientService
            if MCPServerComponent:
                self.service_types["mcp_server"] = MCPServerComponent

    # Backward compatibility properties
    @property
    def _services(self) -> dict[str, Service]:
        return self.service_instances

    @property
    def _service_types(self) -> dict[str, Any]:
        return self.service_types

    def get_service(self, name: str) -> Service | None:
        return self.service_instances.get(name)

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
