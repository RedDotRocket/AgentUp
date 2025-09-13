"""
MCP Registry client service for discovering and managing MCP servers.

This module provides functionality to interact with the Model Context Protocol
registry API for server discovery and configuration.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator

from ..types import ServiceName


class RegistryRepository(BaseModel):
    """Repository information for a registry server."""

    url: str
    source: str = Field(..., description="Repository platform (e.g., 'github')")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Allow empty URLs from registry."""
        return v


class RegistryTransport(BaseModel):
    """Transport configuration for a package."""

    type: str = Field(..., description="Transport type (stdio, sse, streamable-http)")
    url: str | None = Field(None, description="URL for HTTP transports")


class RegistryPackage(BaseModel):
    """Package information for installing an MCP server."""

    registry_type: str = Field(..., description="Package registry type (npm, pypi, docker)")
    identifier: str = Field(..., description="Package identifier")
    version: str = Field(..., description="Package version")
    transport: RegistryTransport = Field(..., description="Transport configuration")
    environment_variables: list[dict[str, Any]] = Field(default_factory=list, description="Environment variables")
    package_arguments: list[dict[str, Any]] = Field(default_factory=list, description="Package arguments")
    runtime_hint: str | None = Field(None, description="Runtime hint")
    registry_base_url: str | None = Field(None, description="Registry base URL")
    file_sha256: str | None = Field(None, description="File SHA256 hash")


class RegistryRemote(BaseModel):
    """Remote endpoint configuration."""

    type: str = Field(..., description="Remote type (sse, streamable-http)")
    url: str = Field(..., description="Remote URL")


class RegistryServer(BaseModel):
    """MCP server entry from the registry."""

    name: ServiceName = Field(..., description="Unique server identifier")
    description: str = Field(..., description="Server description")
    status: str = Field(..., description="Server status")
    version: str = Field(..., description="Server version")
    repository: RegistryRepository
    packages: list[RegistryPackage] = Field(default_factory=list, description="Available packages")
    remotes: list[RegistryRemote] = Field(default_factory=list, description="Remote endpoints")
    schema_: str | None = Field(None, alias="$schema", description="JSON schema URL")
    meta: dict[str, Any] = Field(default_factory=dict, alias="_meta", description="Registry metadata")


class MCPRegistryClient:
    """Client for interacting with the MCP registry API."""

    def __init__(self, base_url: str = "https://registry.modelcontextprotocol.io"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def list_servers(self, search: str | None = None, status: str = "active") -> list[RegistryServer]:
        """List servers from registry with optional filtering."""
        try:
            response = await self.client.get(f"{self.base_url}/v0/servers")
            response.raise_for_status()

            data = response.json()
            servers_data = data.get("servers", [])
            servers = [RegistryServer(**server) for server in servers_data]

            # Filter by status
            if status:
                servers = [s for s in servers if s.status == status]

            # Filter by search term
            if search:
                search_lower = search.lower()
                servers = [
                    s for s in servers if search_lower in s.name.lower() or search_lower in s.description.lower()
                ]

            return servers

        except httpx.HTTPError as e:
            raise MCPRegistryError(f"Failed to list servers: {e}") from e

    async def get_server(self, server_id: str) -> RegistryServer:
        """Get full server details including packages."""
        try:
            # First, try to find the server by name to get its UUID
            servers = await self.list_servers()
            target_server = None

            for server in servers:
                if server.name == server_id:
                    target_server = server
                    break

            if not target_server:
                raise MCPRegistryError(f"Server '{server_id}' not found in registry")

            # Get the UUID from metadata
            server_uuid = target_server.meta.get("io.modelcontextprotocol.registry/official", {}).get("id")

            if not server_uuid:
                raise MCPRegistryError(f"No UUID found for server '{server_id}'")

            # Now fetch the full server details using UUID
            response = await self.client.get(f"{self.base_url}/v0/servers/{server_uuid}")
            response.raise_for_status()

            server_data = response.json()
            return RegistryServer(**server_data)

        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise MCPRegistryError(f"Server '{server_id}' not found in registry") from e
            raise MCPRegistryError(f"Failed to get server details: {e}") from e

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class MCPRegistryError(Exception):
    """Exception raised for MCP registry operations."""

    pass
