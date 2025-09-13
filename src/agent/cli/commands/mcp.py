"""
MCP registry CLI commands for managing MCP servers.

This module provides CLI commands for discovering, installing, and managing
MCP servers from the official registry.
"""

from __future__ import annotations

import asyncio
import sys

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ...config.intent import load_intent_config, save_intent_config
from ...config.model import MCPServerConfig
from ...services.mcp_config_mapper import MCPConfigError, MCPConfigMapper
from ...services.mcp_package_installer import MCPPackageError, MCPPackageInstaller
from ...services.mcp_registry import MCPRegistryClient, MCPRegistryError, RegistryServer

console = Console()


# Styling functions
def error(message: str) -> None:
    """Print error message."""
    click.secho(f"Error: {message}", fg="red", err=True)


def success(message: str) -> None:
    """Print success message."""
    click.secho(f"✓ {message}", fg="green")


def show_info(message: str) -> None:
    """Print info message."""
    click.secho(f"ℹ {message}", fg="blue")


def warning(message: str) -> None:
    """Print warning message."""
    click.secho(f"⚠ {message}", fg="yellow")


@click.group(name="mcp", help="Manage MCP servers from registry")
def mcp():
    """MCP server management commands."""
    pass


@mcp.command()
@click.argument("server_id", required=True)
@click.option("--name", help="Custom server name")
@click.option("--package", "package_index", default=0, type=int, help="Package index to use (default: 0)")
@click.option(
    "--scopes", help="Semicolon-separated tool:scope mappings (e.g., read:files:read,files:write;write:api:write)"
)
@click.option(
    "--discover-scopes", is_flag=True, help="Connect to server and discover actual tools to generate accurate scopes"
)
@click.option("--dry-run", is_flag=True, help="Preview configuration without installing")
@click.option("--config", "config_file", default="agentup.yml", help="Configuration file path")
def add(
    server_id: str,
    name: str | None,
    package_index: int,
    scopes: str | None,
    discover_scopes: bool,
    dry_run: bool,
    config_file: str,
):
    """Add MCP server from registry."""
    asyncio.run(_add_server(server_id, name, package_index, scopes, discover_scopes, dry_run, config_file))


@mcp.command()
@click.option("--search", help="Search keyword")
@click.option("--status", default="active", help="Filter by status")
def list(search: str | None, status: str):
    """List available servers in registry."""
    asyncio.run(_list_servers(search, status))


@mcp.command()
@click.argument("server_id", required=True)
def info(server_id: str):
    """Show server details from registry."""
    asyncio.run(_show_server_info(server_id))


@mcp.command()
@click.argument("server_name", required=True)
@click.option("--config", "config_file", default="agentup.yml", help="Configuration file path")
def remove(server_name: str, config_file: str):
    """Remove MCP server from configuration."""
    _remove_server(server_name, config_file)


@mcp.command()
@click.option("--config", "config_file", default="agentup.yml", help="Configuration file path")
def validate(config_file: str):
    """Validate current MCP configuration."""
    _validate_config(config_file)


@mcp.command()
@click.argument("server_name", required=True)
@click.option("--config", "config_file", default="agentup.yml", help="Configuration file path")
@click.option("--apply", is_flag=True, help="Apply the suggested scopes to configuration")
def discover_tools(server_name: str, config_file: str, apply: bool):
    """Discover tools from an MCP server and suggest scopes."""
    asyncio.run(_discover_tools(server_name, config_file, apply))


async def _add_server(
    server_id: str,
    custom_name: str | None,
    package_index: int,
    scopes_str: str | None,
    discover_scopes: bool,
    dry_run: bool,
    config_file: str,
):
    """Add MCP server implementation."""
    try:
        # Initialize services
        async with MCPRegistryClient() as registry_client:
            mapper = MCPConfigMapper()
            installer = MCPPackageInstaller()

            # Get server from registry
            show_info("Fetching server details from registry...")
            server = await registry_client.get_server(server_id)

            # Parse custom scopes if provided
            custom_scopes = None
            if scopes_str:
                try:
                    custom_scopes = _parse_scopes_string(scopes_str)
                except ValueError as e:
                    error(str(e))
                    sys.exit(1)

            # Generate configuration
            server_config = mapper.registry_to_config(server, package_index, custom_name, custom_scopes)

            if dry_run:
                # For dry-run, simulate the package installation to get command
                package = server.packages[package_index]
                command, args = await installer.install_package(package, dry_run=True)
                server_config.command = command
                server_config.args = args
                _show_dry_run_preview(server, server_config)
                return

            # Validate package
            if not server.packages:
                error(f"No packages available for server '{server_id}'")
                sys.exit(1)

            package = server.packages[package_index]
            if not installer.validate_package(package):
                error("Invalid package configuration")
                sys.exit(1)

            # Install package and update command configuration
            show_info("Installing package...")
            command, args = await installer.install_package(package)
            server_config.command = command
            server_config.args = args

            # Load current configuration
            try:
                config = load_intent_config(config_file)
            except Exception as e:
                error(f"Failed to load configuration: {e}")
                sys.exit(1)

            # Initialize MCP config if it doesn't exist
            if config.mcp is None:
                config.mcp = {"enabled": True, "servers": []}

            # Ensure servers list exists
            if "servers" not in config.mcp:
                config.mcp["servers"] = []

            # If discover-scopes flag is set, connect to server and get real tool scopes
            if discover_scopes and not dry_run:
                show_info("Discovering tools from server for accurate scopes...")
                try:
                    # Create temporary server dict to test connection
                    temp_server_dict = server_config.model_dump(exclude_defaults=True, exclude_none=True)
                    discovered_tools = await _discover_real_tools(temp_server_dict)

                    if discovered_tools:
                        # Generate scopes from discovered tools
                        discovered_scopes = mapper._generate_tool_scopes_from_runtime(
                            discovered_tools, server_config.name
                        )
                        server_config.tool_scopes = discovered_scopes
                        success(f"Discovered {len(discovered_tools)} tools and generated accurate scopes")
                    else:
                        warning("No tools discovered, using default scopes")
                except Exception as e:
                    warning(f"Could not discover tools: {e}. Using default scopes.")

            # Convert server_config to dict for storage in IntentConfig
            server_dict = server_config.model_dump(exclude_defaults=True, exclude_none=True)

            # Check for existing server with same name
            existing_servers = config.mcp["servers"]
            existing_names = [s.get("name") for s in existing_servers if isinstance(s, dict)]
            if server_config.name in existing_names:
                if not click.confirm(f"Server '{server_config.name}' already exists. Replace it?"):
                    show_info("Installation cancelled.")
                    return
                # Remove existing server
                config.mcp["servers"] = [s for s in existing_servers if s.get("name") != server_config.name]

            # Add new server
            config.mcp["servers"].append(server_dict)
            config.mcp["enabled"] = True

            # Save configuration
            save_intent_config(config, config_file)

            success(f"Successfully added MCP server '{server_config.name}' from registry")
            _show_server_summary(server, server_config)

    except MCPRegistryError as e:
        error(f"Registry error: {e}")
        sys.exit(1)
    except MCPConfigError as e:
        error(f"Configuration error: {e}")
        sys.exit(1)
    except MCPPackageError as e:
        error(f"Package installation error: {e}")
        sys.exit(1)
    except Exception as e:
        error(f"Unexpected error: {e}")
        sys.exit(1)


async def _list_servers(search: str | None, status: str):
    """List servers implementation."""
    try:
        async with MCPRegistryClient() as client:
            show_info("Fetching servers from registry...")
            servers = await client.list_servers(search, status)

            if not servers:
                warning("No servers found matching your criteria.")
                return

            table = Table(title=f"MCP Registry Servers ({len(servers)} found)")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")
            table.add_column("Version", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Packages", style="blue")

            for server in servers:
                package_count = len(server.packages)
                table.add_row(
                    server.name,
                    server.description[:60] + "..." if len(server.description) > 60 else server.description,
                    server.version,
                    server.status,
                    str(package_count),
                )

            console.print(table)

    except MCPRegistryError as e:
        error(f"Registry error: {e}")
        sys.exit(1)


async def _show_server_info(server_id: str):
    """Show server info implementation."""
    try:
        async with MCPRegistryClient() as client:
            server = await client.get_server(server_id)

            # Server details panel
            server_info = f"""[bold]Name:[/bold] {server.name}
[bold]Description:[/bold] {server.description}
[bold]Version:[/bold] {server.version}
[bold]Status:[/bold] {server.status}
[bold]Repository:[/bold] {server.repository.url}"""

            console.print(Panel(server_info, title="Server Information", expand=False))

            # Packages table
            if server.packages:
                table = Table(title="Available Packages")
                table.add_column("Index", style="cyan", width=6)
                table.add_column("Type", style="yellow", width=8)
                table.add_column("Identifier", style="green")
                table.add_column("Version", style="blue", width=10)
                table.add_column("Transport", style="magenta", width=12)

                for i, package in enumerate(server.packages):
                    table.add_row(
                        str(i), package.registry_type, package.identifier, package.version, package.transport.type
                    )

                console.print(table)
            else:
                warning("No packages available for this server.")

    except MCPRegistryError as e:
        error(f"Registry error: {e}")
        sys.exit(1)


def _remove_server(server_name: str, config_file: str):
    """Remove server implementation."""
    try:
        config = load_intent_config(config_file)

        # Check if MCP config exists
        if config.mcp is None or "servers" not in config.mcp:
            error(f"Server '{server_name}' not found in configuration.")
            sys.exit(1)

        # Find and remove server
        existing_servers = config.mcp["servers"]
        original_count = len(existing_servers)
        config.mcp["servers"] = [s for s in existing_servers if s.get("name") != server_name]

        if len(config.mcp["servers"]) == original_count:
            error(f"Server '{server_name}' not found in configuration.")
            sys.exit(1)

        # Save configuration
        save_intent_config(config, config_file)
        success(f"Removed MCP server '{server_name}' from configuration.")

    except Exception as e:
        error(f"Failed to remove server: {e}")
        sys.exit(1)


def _validate_config(config_file: str):
    """Validate configuration implementation."""
    try:
        config = load_intent_config(config_file)

        if config.mcp is None or not config.mcp.get("enabled", False):
            warning("MCP is not enabled in configuration.")
            return

        servers = config.mcp.get("servers", [])
        if not servers:
            warning("No MCP servers configured.")
            return

        table = Table(title="MCP Server Configuration Validation")
        table.add_column("Name", style="cyan")
        table.add_column("Transport", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Scopes", style="blue")

        for server_dict in servers:
            if not isinstance(server_dict, dict):
                continue

            name = server_dict.get("name", "Unknown")
            transport = server_dict.get("transport", "Unknown")
            enabled = server_dict.get("enabled", True)
            tool_scopes = server_dict.get("tool_scopes", {})

            status = "✓ Valid" if enabled else "✗ Disabled"
            scope_count = len(tool_scopes)

            table.add_row(name, transport, status, f"{scope_count} tools")

        console.print(table)
        success("MCP configuration is valid.")

    except Exception as e:
        error(f"Configuration validation failed: {e}")
        sys.exit(1)


async def _discover_real_tools(server_config: dict) -> list[str]:  # pyright: ignore[reportGeneralTypeIssues]
    """Connect to MCP server and discover actual tools."""
    try:
        from ...mcp_support.mcp_client import MCPClientService

        # Create temporary MCP client with just this server
        temp_config = {"enabled": True, "servers": [server_config]}

        mcp_client = MCPClientService("temp", temp_config)
        await mcp_client.initialize()

        # Get available tools
        tools_info = await mcp_client.get_available_tools()
        tool_names = [f"{tool['server']}:{tool['name']}" for tool in tools_info]

        await mcp_client.close()
        return tool_names

    except Exception as e:
        warning(f"Could not connect to server for tool discovery: {e}")
        return []


async def _discover_tools(server_name: str, config_file: str, apply: bool):
    """Discover tools from MCP server implementation."""
    try:
        config = load_intent_config(config_file)

        if config.mcp is None or not config.mcp.get("servers"):
            error("No MCP servers configured.")
            sys.exit(1)

        # Find the server configuration
        server_config = None
        for server_dict in config.mcp["servers"]:
            if isinstance(server_dict, dict) and server_dict.get("name") == server_name:
                server_config = server_dict
                break

        if not server_config:
            error(f"Server '{server_name}' not found in configuration.")
            sys.exit(1)

        show_info(f"Discovering tools from MCP server '{server_name}'...")

        # Actually connect to the MCP server to discover real tools
        discovered_tools = await _discover_real_tools(server_config)

        if not discovered_tools:
            warning("No tools discovered from the server.")
            return

        # Generate suggested scopes using the enhanced mapper
        mapper = MCPConfigMapper()
        suggested_scopes = mapper._generate_tool_scopes_from_runtime(discovered_tools, server_name)

        # Display suggestions
        table = Table(title=f"Discovered Tools from '{server_name}'")
        table.add_column("Tool Name", style="cyan")
        table.add_column("Suggested Scopes", style="green")
        table.add_column("Reasoning", style="yellow")

        for tool_name, scopes in suggested_scopes.items():
            reasoning = "Inferred from tool name patterns"
            if "run" in tool_name or "execute" in tool_name:
                reasoning = "Code execution detected - requires system:write"

            table.add_row(tool_name, ", ".join(scopes), reasoning)

        console.print(table)

        if apply:
            # Apply the suggested scopes to configuration
            current_scopes = server_config.get("tool_scopes", {})
            current_scopes.update(suggested_scopes)
            server_config["tool_scopes"] = current_scopes

            save_intent_config(config, config_file)
            success(f"Applied suggested scopes to '{server_name}' configuration.")
        else:
            show_info(f"Run with --apply to add these scopes to '{server_name}' configuration.")

    except Exception as e:
        error(f"Tool discovery failed: {e}")
        sys.exit(1)


def _parse_scopes_string(scopes_str: str) -> dict[str, list[str]]:  # pyright: ignore[reportGeneralTypeIssues]
    """Parse scopes string into dictionary format."""
    scopes = {}

    for scope_mapping in scopes_str.split(";"):
        scope_mapping = scope_mapping.strip()
        if not scope_mapping:
            continue
        if ":" not in scope_mapping:
            raise ValueError(f"Invalid scope format: '{scope_mapping}'. Use 'tool:scope1,scope2' format.")

        parts = scope_mapping.split(":", 1)
        tool_name = parts[0].strip()
        scope_list = [s.strip() for s in parts[1].strip().split(",")]

        scopes[tool_name] = scope_list

    return scopes


def _show_dry_run_preview(server: RegistryServer, config: MCPServerConfig):
    """Show dry run preview."""
    show_info("Dry run mode - showing configuration preview:")

    # Convert config to dict for YAML display
    config_dict = {
        "name": config.name,
        "enabled": config.enabled,
        "transport": config.transport,
        "command": config.command,
        "args": config.args,
        "env": config.env,
        "tool_scopes": config.tool_scopes,
        "registry_id": config.registry_id,
        "registry_version": config.registry_version,
    }

    yaml_content = yaml.dump({"mcp": {"servers": [config_dict]}}, default_flow_style=False)
    syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)

    console.print(Panel(syntax, title="Configuration Preview", expand=False))


def _show_server_summary(server: RegistryServer, config: MCPServerConfig):
    """Show server installation summary."""
    summary = f"""[bold green]✓ Installation Complete[/bold green]

[bold]Server:[/bold] {config.name}
[bold]Registry ID:[/bold] {server.name}
[bold]Transport:[/bold] {config.transport}
[bold]Command:[/bold] {config.command}
[bold]Tool Scopes:[/bold] {len(config.tool_scopes)} configured

The server has been added to your configuration and is ready to use.
Run [bold cyan]agentup run[/bold cyan] to start your agent with the new MCP server."""

    console.print(Panel(summary, title="Installation Summary", expand=False))
