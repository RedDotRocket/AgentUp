"""
MCP configuration mapper service for converting registry data to AgentUp configuration.

This module provides functionality to map MCP registry server data to AgentUp's
MCPServerConfig format with intelligent defaults and scope generation.
"""

from __future__ import annotations

import re

from ..config.model import MCPServerConfig
from .mcp_registry import RegistryPackage, RegistryServer


class MCPConfigMapper:
    """Maps registry server data to AgentUp MCPServerConfig."""

    # Common scope mappings based on server type patterns
    # Order matters - more specific patterns should come first
    SCOPE_PATTERNS = {
        r"code-runner|code.*runner": {
            "run-code": ["system:write"],
            "execute": ["system:write"],
            "run_code": ["system:write"],
            "list-languages": ["api:read"],
        },
        r"filesystem|file|directory": {
            "read_file": ["files:read"],
            "write_file": ["files:write"],
            "list_directory": ["files:read"],
            "create_directory": ["files:write"],
            "delete_file": ["files:write"],
            "move_file": ["files:write"],
        },
        r"database|sql|postgres|mysql|sqlite": {
            "query": ["db:read"],
            "execute": ["db:write"],
            "transaction": ["db:write"],
            "schema": ["db:read"],
        },
        r"web|http|api|fetch|search": {
            "get": ["web:read"],
            "post": ["web:write"],
            "fetch": ["web:read"],
            "search": ["web:read"],
            "webhook": ["web:write"],
        },
        r"git|github|gitlab": {
            "clone": ["git:read"],
            "push": ["git:write"],
            "pull": ["git:read"],
            "commit": ["git:write"],
            "branch": ["git:write"],
        },
        r"docker|container": {
            "run": ["docker:write"],
            "exec": ["docker:write"],
            "inspect": ["docker:read"],
            "logs": ["docker:read"],
        },
        r"email|smtp|mail": {
            "send": ["email:write"],
            "read": ["email:read"],
            "list": ["email:read"],
        },
        r"calendar|schedule": {
            "create_event": ["calendar:write"],
            "list_events": ["calendar:read"],
            "update_event": ["calendar:write"],
        },
        r"code|runner|execute|run": {
            "run-code": ["system:write"],
            "execute": ["system:write"],
            "compile": ["system:write"],
            "run_code": ["system:write"],
            "execute_code": ["system:write"],
        },
        r"browser|selenium|web": {
            "navigate": ["web:write"],
            "click": ["web:write"],
            "type": ["web:write"],
            "screenshot": ["web:read"],
            "get_page": ["web:read"],
        },
    }

    def registry_to_config(
        self,
        registry_server: RegistryServer,
        package_index: int = 0,
        custom_name: str | None = None,
        custom_scopes: dict[str, list[str]] | None = None,
    ) -> MCPServerConfig:
        """Convert registry server to AgentUp MCPServerConfig."""

        if not registry_server.packages:
            raise ValueError(f"No packages available for server '{registry_server.name}'")

        if package_index >= len(registry_server.packages):
            raise ValueError(f"Package index {package_index} out of range (0-{len(registry_server.packages) - 1})")

        package = registry_server.packages[package_index]
        server_name = custom_name or self._generate_server_name(registry_server.name)

        # Extract transport configuration
        transport, command, args = self._extract_transport_config(package)

        # Generate tool scopes
        tool_scopes = custom_scopes or self._generate_tool_scopes(registry_server)

        # Build config data for MCPServerConfig with all required fields
        config_data = {
            "name": server_name,
            "enabled": True,
            "transport": transport,
            "tool_scopes": tool_scopes,
            "registry_id": registry_server.name,
            "registry_version": registry_server.version,
            "registry_package_index": package_index,
        }

        # Add transport-specific settings
        if transport == "stdio":
            config_data["command"] = command
            config_data["args"] = args
            # Convert environment_variables list to env dict
            env = {}
            if hasattr(package, "environment_variables"):
                for env_var in package.environment_variables:
                    if isinstance(env_var, dict) and "name" in env_var and "value" in env_var:
                        env[env_var["name"]] = env_var["value"]
            config_data["env"] = env
        else:
            # For sse/streamable_http transports
            config_data["url"] = command  # URL is stored in command for HTTP transports
            config_data["timeout"] = 30

        config = MCPServerConfig(**config_data)

        return config

    def _generate_server_name(self, registry_id: str) -> str:
        """Generate a clean server name from registry ID."""
        # Extract the last part after the last slash or dot
        name_parts = registry_id.replace("/", ".").split(".")
        base_name = name_parts[-1].lower()

        # Clean up the name
        clean_name = re.sub(r"[^a-z0-9-]", "-", base_name)
        clean_name = re.sub(r"-+", "-", clean_name).strip("-")

        return clean_name or "mcp-server"

    def _extract_transport_config(self, package: RegistryPackage) -> tuple[str, str | None, list[str]]:
        """Extract transport, command, and args from package info."""
        transport = package.transport.type

        if transport == "stdio":
            command = self._get_package_command(package)
            args = self._get_package_args(package)
            return transport, command, args

        elif transport in ("sse", "streamable-http"):
            # For HTTP transports, use the transport URL
            url = package.transport.url or f"http://localhost:8080/{package.identifier}"
            return transport, url, []

        else:
            raise ValueError(f"Unsupported transport type: {transport}")

    def _get_package_command(self, package: RegistryPackage) -> str:
        """Get the appropriate command for the package type."""
        # Use runtime hint if available
        if package.runtime_hint:
            return package.runtime_hint

        # Generate command based on package type
        if package.registry_type == "npm":
            return "npx"
        elif package.registry_type == "pypi":
            return "uvx"
        elif package.registry_type == "docker" or package.registry_type == "oci":
            return "docker"
        else:
            return package.identifier

    def _get_package_args(self, package: RegistryPackage) -> list[str]:
        """Get the appropriate arguments for the package."""
        # Extract args from package_arguments if available
        base_args = []
        for arg in package.package_arguments:
            if arg.get("is_required"):
                # Include required arguments
                if "default" in arg:
                    base_args.extend([f"--{arg.get('name')}", str(arg.get("default"))])

        if package.registry_type == "npm":
            return ["-y", f"{package.identifier}@{package.version}"] + base_args
        elif package.registry_type == "pypi":
            return [f"{package.identifier}=={package.version}"] + base_args
        elif package.registry_type == "docker" or package.registry_type == "oci":
            return ["run", "--rm", "-i", f"{package.identifier}:{package.version}"] + base_args
        else:
            return base_args

    def _generate_tool_scopes_from_runtime(self, tool_names: list[str], server_name: str) -> dict[str, list[str]]:
        """Generate tool scopes from actual MCP tool names discovered at runtime."""
        scopes = {}

        for tool_name in tool_names:
            # Extract the actual tool function name (remove server prefix if present)
            if ":" in tool_name:
                _, func_name = tool_name.split(":", 1)
            else:
                func_name = tool_name

            # Match against all patterns
            matched_scope = None
            for pattern, scope_mapping in self.SCOPE_PATTERNS.items():
                if re.search(pattern, f"{server_name} {func_name}", re.IGNORECASE):
                    for tool_pattern, scopes_list in scope_mapping.items():
                        if re.search(tool_pattern.replace("_", "[-_]"), func_name, re.IGNORECASE):
                            matched_scope = scopes_list
                            break
                    if matched_scope:
                        break

            # If no specific pattern matched, infer from tool name
            if not matched_scope:
                if any(keyword in func_name.lower() for keyword in ["read", "get", "list", "show", "view"]):
                    matched_scope = ["api:read"]
                elif any(
                    keyword in func_name.lower()
                    for keyword in ["write", "create", "update", "delete", "run", "execute"]
                ):
                    matched_scope = ["api:write"]
                else:
                    matched_scope = ["api:read"]  # Default to read

            scopes[tool_name] = matched_scope

        return scopes

    def _generate_tool_scopes(self, server: RegistryServer) -> dict[str, list[str]]:
        """Generate default tool scopes based on server description and name."""
        scopes = {}

        # Combine name and description for pattern matching
        text_to_analyze = f"{server.name} {server.description}".lower()

        # Find matching patterns and generate scopes
        for pattern, scope_mapping in self.SCOPE_PATTERNS.items():
            if re.search(pattern, text_to_analyze, re.IGNORECASE):
                scopes.update(scope_mapping)
                break

        # If no pattern matched, provide generic scopes
        if not scopes:
            scopes = {
                "read": ["api:read"],
                "write": ["api:write"],
                "execute": ["api:write"],
                "list": ["api:read"],
            }

        return scopes


class MCPConfigError(Exception):
    """Exception raised for MCP configuration mapping errors."""

    pass
