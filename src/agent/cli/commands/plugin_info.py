import json
from collections import OrderedDict

import click
import structlog
import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logger = structlog.get_logger(__name__)


@click.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plugin information and logging")
@click.option("--capabilities", "-c", is_flag=True, help="Show available capabilities/AI functions")
@click.option(
    "--format", "-f", type=click.Choice(["table", "json", "yaml", "agentup-cfg"]), default="table", help="Output format"
)
@click.option("--agentup-cfg", is_flag=True, help="Output in agentup.yml format (same as --format agentup-cfg)")
@click.option("--debug", is_flag=True, help="Show debug logging output")
def list_plugins(verbose: bool, capabilities: bool, format: str, agentup_cfg: bool, debug: bool):
    """List all available plugins and their capabilities."""
    # Handle --agentup-cfg flag (shortcut for --format agentup-cfg)
    if agentup_cfg:
        format = "agentup-cfg"

    try:
        # Configure logging based on verbose/debug flags
        import logging
        import os

        if debug:
            os.environ["AGENTUP_LOG_LEVEL"] = "DEBUG"
            logging.getLogger("agent.plugins").setLevel(logging.DEBUG)
            logging.getLogger("agent.plugins.manager").setLevel(logging.DEBUG)
        elif verbose:
            # Show INFO level for verbose mode
            logging.getLogger("agent.plugins").setLevel(logging.INFO)
            logging.getLogger("agent.plugins.manager").setLevel(logging.INFO)
        else:
            # Suppress all plugin discovery logs for clean output
            logging.getLogger("agent.plugins").setLevel(logging.WARNING)
            logging.getLogger("agent.plugins.manager").setLevel(logging.WARNING)

        from agent.plugins.manager import PluginRegistry

        # Create a registry without auto-discovery to avoid allowlist warnings during listing
        try:
            from agent.config import get_settings

            config = get_settings().model_dump()
        except ImportError:
            config = None

        manager = PluginRegistry(config)

        # Use the discovery method that bypasses allowlist for listing purposes
        all_available_plugins = manager.discover_all_available_plugins()

        if format == "json":
            output = {
                "plugins": [
                    {
                        "name": plugin_info["name"],
                        "version": plugin_info["version"],
                        "package": plugin_info["package"],
                        "status": plugin_info["status"],
                        "loaded": plugin_info["loaded"],
                        "configured": plugin_info["configured"],
                    }
                    for plugin_info in all_available_plugins
                ]
            }

            # Only include capabilities if -c flag is used
            if capabilities:
                capabilities_for_json = []
                for plugin_info in all_available_plugins:
                    plugin_name = plugin_info["name"]
                    plugin_capabilities = _load_plugin_capabilities(plugin_name, verbose, debug)

                    for cap in plugin_capabilities:
                        capabilities_for_json.append(
                            {
                                "id": cap["id"],
                                "name": cap["name"],
                                "description": cap["description"],
                                "plugin": plugin_name,
                                "required_scopes": cap["required_scopes"],
                                "ai_function": cap["is_ai_function"],
                            }
                        )

                output["capabilities"] = capabilities_for_json

            click.secho(json.dumps(output, indent=2))
            return

        if format == "yaml":
            output = {
                "plugins": [
                    {
                        "plugin_name": plugin_info["name"],
                        "version": plugin_info["version"],
                        "package": plugin_info["package"],
                        "status": plugin_info["status"],
                        "loaded": plugin_info["loaded"],
                        "configured": plugin_info["configured"],
                    }
                    for plugin_info in all_available_plugins
                ]
            }

            # Only include capabilities if -c flag is used (same logic as JSON)
            if capabilities:
                capabilities_for_yaml = []
                for plugin_info in all_available_plugins:
                    plugin_name = plugin_info["name"]
                    plugin_capabilities = _load_plugin_capabilities(plugin_name, verbose, debug)

                    for cap in plugin_capabilities:
                        capabilities_for_yaml.append(
                            {
                                "id": cap["id"],
                                "name": cap["name"],
                                "description": cap["description"],
                                "plugin": plugin_name,
                                "required_scopes": cap["required_scopes"],
                                "ai_function": cap["is_ai_function"],
                            }
                        )

                output["capabilities"] = capabilities_for_yaml

            click.secho(yaml.dump(output, default_flow_style=False))
            return

        if format == "agentup-cfg":
            console = Console()

            # Custom representer to maintain field order
            def represent_ordereddict(dumper, data):
                return dumper.represent_dict(data.items())

            yaml.add_representer(OrderedDict, represent_ordereddict)

            # For agentup-cfg format, always include capabilities (no -c flag needed)
            plugins_config = []

            for plugin_info in all_available_plugins:
                plugin_name = plugin_info["name"]
                package_name = plugin_info["package"]

                # Generate better name and description
                base_name = plugin_name.replace("_", " ").replace("-", " ").title()
                if base_name.lower().endswith("plugin"):
                    display_name = base_name
                else:
                    display_name = base_name + " Plugin"

                # Use OrderedDict to maintain field order
                plugin_config = OrderedDict()
                plugin_config["package"] = package_name
                plugin_config["name"] = display_name
                plugin_config["description"] = (
                    f"A plugin for {plugin_name.replace('_', ' ').replace('-', ' ')} functionality"
                )
                plugin_config["tags"] = [plugin_name.replace("_", "-").replace(" ", "-").lower()]
                plugin_config["input_mode"] = "text"
                plugin_config["output_mode"] = "text"
                plugin_config["priority"] = 50
                plugin_config["capabilities"] = []

                # Load capabilities for this plugin
                plugin_capabilities = _load_plugin_capabilities(plugin_name, verbose, debug)

                for cap in plugin_capabilities:
                    capability_config = OrderedDict(
                        [
                            ("capability_id", cap["id"]),
                            ("required_scopes", cap["required_scopes"]),
                            ("enabled", True),
                        ]
                    )
                    plugin_config["capabilities"].append(capability_config)

                # Only add plugins that have capabilities
                if plugin_config["capabilities"]:
                    plugins_config.append(plugin_config)

            if plugins_config:
                output = {"plugins": plugins_config}
                # Use sort_keys=False to preserve order, default_flow_style=False for block style
                yaml_output = yaml.dump(
                    output, default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000, indent=2
                )
                console.print(yaml_output)
            else:
                console.print("plugins: []")
            return

        # Table format (default)
        if not all_available_plugins:
            click.secho("No plugins found", fg="yellow")
            click.secho(
                "\nTo create a plugin: "
                + click.style("agentup plugin init ", fg="cyan")
                + click.style("<plugin_name>", fg="blue")
            )
            click.secho(
                "To install from registry: "
                + click.style("uv add ", fg="cyan")
                + click.style("<plugin_name>", fg="blue")
                + click.style(" && agentup plugin sync", fg="cyan")
            )
            return

        # Plugins table - show all available plugins
        plugin_table = Table(title="Available Plugins", box=box.ROUNDED, title_style="bold cyan")
        plugin_table.add_column("Plugin", style="cyan")
        plugin_table.add_column("Package", style="white")
        plugin_table.add_column("Version", style="green", justify="center")
        plugin_table.add_column("Status", style="blue", justify="center")

        if verbose:
            plugin_table.add_column("Configured", style="dim", justify="center")
            plugin_table.add_column("Module", style="dim")

        for plugin_info in all_available_plugins:
            # Determine status display
            status = plugin_info["status"]
            if plugin_info["loaded"]:
                status = "loaded"
            elif plugin_info["configured"]:
                status = "configured"
            else:
                status = "available"

            row = [
                plugin_info["name"],
                plugin_info["package"],
                plugin_info["version"],
                status,
            ]

            if verbose:
                configured = "✓" if plugin_info["configured"] else "✗"
                row.extend([configured, plugin_info.get("module", "unknown")])

            plugin_table.add_row(*row)

        console = Console()
        console.print(plugin_table)

        # Only show capabilities table if --capabilities flag is used
        if capabilities:
            click.secho()  # Blank line

            # For capabilities display, we need to temporarily load plugins to get their capabilities
            # This is only done when explicitly requested with -c flag
            all_capabilities_info = []

            for plugin_info in all_available_plugins:
                plugin_name = plugin_info["name"]
                plugin_capabilities = _load_plugin_capabilities(plugin_name, verbose, debug)

                for cap in plugin_capabilities:
                    all_capabilities_info.append(
                        {
                            "id": cap["id"],
                            "name": cap["name"],
                            "description": cap["description"],
                            "plugin": plugin_name,
                            "scopes": cap["required_scopes"],
                            "ai_function": cap["is_ai_function"],
                            "tags": cap["tags"],
                        }
                    )

            if all_capabilities_info:
                capabilities_table = Table(title="Available Capabilities", box=box.ROUNDED, title_style="bold cyan")
                capabilities_table.add_column("Capability", style="cyan")
                capabilities_table.add_column("Plugin", style="dim")
                capabilities_table.add_column("AI Function", style="green", justify="center")
                capabilities_table.add_column("Required Scopes", style="yellow")

                if verbose:
                    capabilities_table.add_column("Description", style="white")

                for cap_info in all_capabilities_info:
                    ai_indicator = "✓" if cap_info["ai_function"] else "✗"
                    scopes_str = ", ".join(cap_info["scopes"]) if cap_info["scopes"] else "none"

                    row = [
                        cap_info["id"],  # Show ID instead of name - this is what goes in config
                        cap_info["plugin"],
                        ai_indicator,
                        scopes_str,
                    ]

                    if verbose:
                        description = cap_info["description"] or "No description"
                        row.append(description[:80] + "..." if len(description) > 80 else description)

                    capabilities_table.add_row(*row)

                console.print(capabilities_table)
            else:
                click.secho("No capabilities found. This may indicate:", fg="yellow")
                click.secho("  • No plugins are installed", fg="yellow")
                click.secho("  • Plugins have issues loading", fg="yellow")
                click.secho("  • Use --verbose to see loading details", fg="yellow")

    except ImportError:
        click.secho("Plugin system not available. Please check your installation.", fg="red")
    except Exception as e:
        click.secho(f"Error listing plugins: {e}", fg="red")


@click.command()
@click.argument("capability_id")
def info(capability_id: str):
    """Show detailed information about a specific capability."""
    try:
        from agent.plugins.manager import get_plugin_registry

        manager = get_plugin_registry()
        capability = manager.get_capability(capability_id)

        if not capability:
            click.secho(f"Capability '{capability_id}' not found", fg="yellow")
            return

        # Get plugin info
        plugin_name = manager.capability_to_plugin.get(capability_id, "unknown")
        plugin = manager.plugins.get(plugin_name)

        # Build info panel
        info_lines = [
            f"[bold]Capability ID:[/bold] {capability.id}",
            f"[bold]Name:[/bold] {capability.name}",
            f"[bold]Version:[/bold] {capability.version}",
            f"[bold]Description:[/bold] {capability.description or 'No description'}",
            f"[bold]Plugin:[/bold] {plugin_name}",
            f"[bold]Features:[/bold] {', '.join([cap.value if hasattr(cap, 'value') else str(cap) for cap in capability.capabilities])}",
            f"[bold]Tags:[/bold] {', '.join(capability.tags) if capability.tags else 'None'}",
            f"[bold]Priority:[/bold] {capability.priority}",
            f"[bold]Input Mode:[/bold] {capability.input_mode}",
            f"[bold]Output Mode:[/bold] {capability.output_mode}",
        ]

        if plugin:
            info_lines.extend(
                [
                    "",
                    "[bold cyan]Plugin Information:[/bold cyan]",
                    f"[bold]Status:[/bold] {plugin.status.value}",
                    f"[bold]Author:[/bold] {plugin.author or 'Unknown'}",
                    f"[bold]Source:[/bold] {plugin.metadata.get('source', 'entry_point')}",
                ]
            )

            if plugin.error:
                info_lines.append(f"[bold red]Error:[/bold red] {plugin.error}")

        # Configuration schema
        if capability.config_schema:
            info_lines.extend(["", "[bold cyan]Configuration Schema:[/bold cyan]"])
            schema_str = json.dumps(capability.config_schema, indent=2)
            info_lines.append(f"[dim]{schema_str}[/dim]")

        # AI functions
        ai_functions = manager.get_ai_functions(capability_id)
        if ai_functions:
            info_lines.extend(["", "[bold cyan]AI Functions:[/bold cyan]"])
            for func in ai_functions:
                info_lines.append(f"  • [green]{func.name}[/green]: {func.description}")

        # Health status
        if hasattr(manager.capability_hooks.get(capability_id), "get_health_status"):
            try:
                health = manager.capability_hooks[capability_id].get_health_status()
                info_lines.extend(["", "[bold cyan]Health Status:[/bold cyan]"])
                for key, value in health.items():
                    info_lines.append(f"  • {key}: {value}")
            except Exception:
                click.secho("[red]Error getting health status[/red]", err=True)
                pass

        # Create panel
        panel = Panel(
            "\n".join(info_lines),
            title=f"[bold cyan]{capability.name}[/bold cyan]",
            border_style="blue",
            padding=(1, 2),
        )

        console = Console()
        console.print(panel)

    except ImportError:
        click.secho("Plugin system not available.", fg="red")
    except Exception as e:
        click.secho(f"Error getting capability info: {e}", fg="red")


@click.command()
@click.argument("plugin_name")
@click.option("--capability", "-c", help="Show configuration for specific capability")
@click.option("--format", "-f", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def config(plugin_name: str, capability: str | None, format: str):
    """Show effective plugin configuration including overrides and middleware."""

    try:
        from agent.config import get_plugin_resolver

        console = Console()

        # Get the plugin resolver
        resolver = get_plugin_resolver()
        if not resolver:
            click.secho("Plugin resolver not available. Ensure configuration is loaded.", fg="red")
            return

        # Get plugin override configuration
        try:
            plugin_override = resolver.get_plugin_override(plugin_name)
        except Exception as e:
            click.secho(f"Plugin '{plugin_name}' not found in configuration: {e}", fg="red")
            return

        if capability:
            # Show specific capability configuration
            try:
                cap_override = resolver.get_capability_override(plugin_name, capability)
                effective_scopes = resolver.get_effective_scopes(plugin_name, capability)
                effective_middleware = resolver.get_effective_middleware(plugin_name, capability)
                cap_config = resolver.get_capability_config(plugin_name, capability)

                if format == "json":
                    output = {
                        "plugin": plugin_name,
                        "capability": capability,
                        "enabled": cap_override.enabled,
                        "effective_scopes": effective_scopes,
                        "effective_middleware": effective_middleware,
                        "configuration": cap_config,
                        "middleware_overrides": [
                            {"name": mw.name, "params": mw.params} for mw in cap_override.middleware
                        ],
                    }
                    click.echo(json.dumps(output, indent=2))

                elif format == "yaml":
                    output = {
                        "plugin": plugin_name,
                        "capability": capability,
                        "enabled": cap_override.enabled,
                        "effective_scopes": effective_scopes,
                        "effective_middleware": effective_middleware,
                        "configuration": cap_config,
                        "middleware_overrides": [
                            {"name": mw.name, "params": mw.params} for mw in cap_override.middleware
                        ],
                    }
                    click.echo(yaml.dump(output, default_flow_style=False))

                else:  # table format
                    # Capability details table
                    table = Table(title=f"Configuration: {plugin_name}::{capability}", box=box.ROUNDED)
                    table.add_column("Property", style="cyan")
                    table.add_column("Value", style="white")

                    table.add_row("Plugin", plugin_name)
                    table.add_row("Capability", capability)
                    table.add_row("Enabled", "✓" if cap_override.enabled else "✗")
                    table.add_row("Effective Scopes", ", ".join(effective_scopes) if effective_scopes else "none")
                    table.add_row("Configuration", str(cap_config) if cap_config else "none")

                    console.print(table)

                    # Middleware table
                    if effective_middleware:
                        click.echo()
                        mw_table = Table(title="Effective Middleware", box=box.ROUNDED)
                        mw_table.add_column("Name", style="cyan")
                        mw_table.add_column("Parameters", style="white")

                        for mw in effective_middleware:
                            params_str = (
                                ", ".join(f"{k}={v}" for k, v in mw["params"].items()) if mw["params"] else "none"
                            )
                            mw_table.add_row(mw["name"], params_str)

                        console.print(mw_table)

            except Exception as e:
                click.secho(f"Error getting capability configuration: {e}", fg="red")
                return

        else:
            # Show plugin-level configuration
            plugin_config = resolver.get_plugin_config(plugin_name)
            effective_middleware = resolver.get_effective_middleware(plugin_name)

            if format == "json":
                output = {
                    "plugin": plugin_name,
                    "enabled": plugin_override.enabled,
                    "configuration": plugin_config,
                    "effective_middleware": effective_middleware,
                    "middleware_overrides": [
                        {"name": mw.name, "params": mw.params} for mw in plugin_override.middleware
                    ],
                    "capabilities": {},
                }

                # Add capability configurations
                for cap_id in plugin_override.capabilities.keys():
                    cap_override = resolver.get_capability_override(plugin_name, cap_id)
                    output["capabilities"][cap_id] = {
                        "enabled": cap_override.enabled,
                        "effective_scopes": resolver.get_effective_scopes(plugin_name, cap_id),
                        "configuration": resolver.get_capability_config(plugin_name, cap_id),
                        "middleware_overrides": [
                            {"name": mw.name, "params": mw.params} for mw in cap_override.middleware
                        ],
                    }

                click.echo(json.dumps(output, indent=2))

            elif format == "yaml":
                output = {
                    "plugin": plugin_name,
                    "enabled": plugin_override.enabled,
                    "configuration": plugin_config,
                    "effective_middleware": effective_middleware,
                    "middleware_overrides": [
                        {"name": mw.name, "params": mw.params} for mw in plugin_override.middleware
                    ],
                    "capabilities": {},
                }

                # Add capability configurations
                for cap_id in plugin_override.capabilities.keys():
                    cap_override = resolver.get_capability_override(plugin_name, cap_id)
                    output["capabilities"][cap_id] = {
                        "enabled": cap_override.enabled,
                        "effective_scopes": resolver.get_effective_scopes(plugin_name, cap_id),
                        "configuration": resolver.get_capability_config(plugin_name, cap_id),
                        "middleware_overrides": [
                            {"name": mw.name, "params": mw.params} for mw in cap_override.middleware
                        ],
                    }

                click.echo(yaml.dump(output, default_flow_style=False))

            else:  # table format
                # Plugin details table
                table = Table(title=f"Plugin Configuration: {plugin_name}", box=box.ROUNDED)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="white")

                table.add_row("Plugin", plugin_name)
                table.add_row("Enabled", "✓" if plugin_override.enabled else "✗")
                table.add_row("Configuration", str(plugin_config) if plugin_config else "none")

                console.print(table)

                # Plugin-level middleware
                if effective_middleware:
                    click.echo()
                    mw_table = Table(title="Plugin-Level Middleware", box=box.ROUNDED)
                    mw_table.add_column("Name", style="cyan")
                    mw_table.add_column("Parameters", style="white")

                    for mw in effective_middleware:
                        params_str = ", ".join(f"{k}={v}" for k, v in mw["params"].items()) if mw["params"] else "none"
                        mw_table.add_row(mw["name"], params_str)

                    console.print(mw_table)

                # Capabilities summary
                if plugin_override.capabilities:
                    click.echo()
                    cap_table = Table(title="Capability Overrides", box=box.ROUNDED)
                    cap_table.add_column("Capability", style="cyan")
                    cap_table.add_column("Enabled", style="green")
                    cap_table.add_column("Scopes", style="yellow")
                    cap_table.add_column("Middleware", style="blue")

                    for cap_id in plugin_override.capabilities.keys():
                        cap_override = resolver.get_capability_override(plugin_name, cap_id)
                        effective_scopes = resolver.get_effective_scopes(plugin_name, cap_id)
                        cap_middleware = resolver.get_effective_middleware(plugin_name, cap_id)

                        scopes_str = ", ".join(effective_scopes) if effective_scopes else "none"
                        middleware_str = ", ".join(mw["name"] for mw in cap_middleware) if cap_middleware else "none"

                        cap_table.add_row(cap_id, "✓" if cap_override.enabled else "✗", scopes_str, middleware_str)

                    console.print(cap_table)

                click.echo()
                click.secho("💡 Use --capability <name> to see detailed capability configuration", fg="cyan")
                click.secho("💡 Use --format json|yaml for machine-readable output", fg="cyan")

    except ImportError as e:
        click.secho(f"Required dependencies not available: {e}", fg="red")
    except Exception as e:
        click.secho(f"Error showing plugin configuration: {e}", fg="red")


@click.command()
def validate():
    """Validate plugin configurations against their schemas."""
    try:
        from agent.config import get_settings
        from agent.plugins.manager import get_plugin_registry

        manager = get_plugin_registry()

        click.secho("Validating plugins...", fg="cyan")

        # Get capability configurations
        try:
            config = get_settings()
            if hasattr(config, "plugins") and isinstance(config.plugins, dict):
                # New dictionary structure
                capability_configs = {
                    package_name: plugin_config.config or {}
                    for package_name, plugin_config in config.plugins.items()
                    if hasattr(plugin_config, "config")
                }
            else:
                # Legacy list structure
                capability_configs = {
                    getattr(plugin, "name", "unknown"): getattr(plugin, "config", {}) or {}
                    for plugin in getattr(config, "plugins", [])
                }
        except Exception as e:
            logger.warning(f"Error loading plugin configurations: {e}")
            capability_configs = {}

        all_valid = True
        results = []

        for capability_id, capability_info in manager.capabilities.items():
            capability_config = capability_configs.get(capability_id, {})
            validation = manager.validate_config(capability_id, capability_config)

            results.append(
                {
                    "capability_id": capability_id,
                    "capability_name": capability_info.name,
                    "plugin": manager.capability_to_plugin.get(capability_id),
                    "validation": validation,
                    "has_config": capability_id in capability_configs,
                }
            )

            if not validation.valid:
                all_valid = False

        # Display results
        console = Console()
        table = Table(title="Plugin Validation Results", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Capability", style="cyan")
        table.add_column("Plugin", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Issues", style="yellow")

        for result in results:
            capability_id = result["capability_id"]
            plugin = result["plugin"]
            validation = result["validation"]

            if validation.valid:
                status = "[green]✓ Valid[/green]"
                issues = ""
            else:
                status = "[red]✗ Invalid[/red]"
                issues = "; ".join(validation.errors)

            # Add warnings if any
            if validation.warnings:
                if issues:
                    issues += " | "
                issues += "Warnings: " + "; ".join(validation.warnings)

            table.add_row(capability_id, plugin, status, issues)

        console.print(table)

        if all_valid:
            click.secho("\n✓ All plugins validated successfully!", fg="green")
        else:
            click.secho("\n[red]✗ Some plugins have validation errors.[/red]")
            click.secho("Please check your agentup.yml and fix the issues.")

    except ImportError:
        click.secho("[red]Plugin system not available.[/red]")
    except Exception as e:
        click.secho(f"[red]Error validating plugins: {e}[/red]")


def _load_plugin_capabilities(plugin_name: str, verbose: bool = False, debug: bool = False) -> list[dict]:
    """Load capabilities for a given plugin.

    Args:
        plugin_name: Name of the plugin to load capabilities for
        verbose: Whether to show verbose output
        debug: Whether to show debug output

    Returns:
        List of capability definitions as dictionaries
    """
    capabilities = []

    try:
        import importlib.metadata

        entry_points = importlib.metadata.entry_points()

        if hasattr(entry_points, "select"):
            plugin_entries = entry_points.select(group="agentup.plugins", name=plugin_name)
        else:
            plugin_entries = [ep for ep in entry_points.get("agentup.plugins", []) if ep.name == plugin_name]

        for entry_point in plugin_entries:
            try:
                plugin_class = entry_point.load()
                plugin_instance = plugin_class()
                cap_definitions = plugin_instance.get_capability_definitions()

                for cap_def in cap_definitions:
                    capabilities.append(
                        {
                            "id": cap_def.id,
                            "name": cap_def.name,
                            "description": cap_def.description,
                            "required_scopes": cap_def.required_scopes,
                            "is_ai_function": cap_def.is_ai_capability,
                            "tags": getattr(cap_def, "tags", []),
                        }
                    )

            except Exception as e:
                if debug or verbose:
                    click.secho(f"Warning: Could not load plugin {plugin_name}: {e}", fg="yellow", err=True)
                continue

    except Exception as e:
        if debug or verbose:
            click.secho(f"Warning: Could not find entry point for {plugin_name}: {e}", fg="yellow", err=True)

    return capabilities
