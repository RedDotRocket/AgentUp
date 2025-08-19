from pathlib import Path

import click
import structlog
import yaml

from agent.config.intent import load_intent_config, save_intent_config

# Note: Resolver imports removed - using uv-based workflow instead

logger = structlog.get_logger(__name__)


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@click.pass_context
def sync(ctx, dry_run: bool):
    """Sync agentup.yml with installed AgentUp plugins."""

    project_root = Path.cwd()
    intent_config_path = project_root / "agentup.yml"

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="yellow")

    click.secho("Synchronizing agentup.yml with installed plugins...", fg="cyan")

    # Load current intent configuration
    try:
        intent_config = load_intent_config(str(intent_config_path))
        current_plugins = set(intent_config.plugins.keys()) if intent_config.plugins else set()
        click.secho(f"Current agentup.yml has {len(current_plugins)} configured plugins", fg="green")
    except (FileNotFoundError, yaml.YAMLError, KeyError, ValueError) as e:
        click.secho(f"Failed to load agentup.yml: {e}", fg="red")
        ctx.exit(1)

    # Discover installed AgentUp plugins with capabilities (bypass allowlist)
    try:
        from agent.plugins.manager import PluginRegistry

        # Create registry to discover available plugins (bypass allowlist)
        registry = PluginRegistry()
        available_plugins_info = registry.discover_all_available_plugins()

        installed_plugins = {}
        for plugin_info in available_plugins_info:
            plugin_name = plugin_info["name"]

            # Try to load the plugin and discover capabilities
            capabilities = []
            try:
                # Get the entry point and load the plugin
                import importlib.metadata as metadata

                entry_points = metadata.entry_points()
                if hasattr(entry_points, "select"):
                    plugin_entries = entry_points.select(group="agentup.plugins")
                else:
                    plugin_entries = entry_points.get("agentup.plugins", [])

                for entry_point in plugin_entries:
                    if entry_point.name == plugin_name:
                        plugin_class = entry_point.load()
                        plugin_instance = plugin_class()

                        # Get capability definitions if available
                        if hasattr(plugin_instance, "get_capability_definitions"):
                            cap_definitions = plugin_instance.get_capability_definitions()

                            for cap_def in cap_definitions:
                                capabilities.append(
                                    {
                                        "capability_id": cap_def.id,
                                        "name": cap_def.name,
                                        "description": cap_def.description,
                                        "required_scopes": cap_def.required_scopes,
                                        "enabled": True,
                                    }
                                )
                        break

            except (ImportError, AttributeError, TypeError, ValueError) as e:
                # If we can't load the plugin, still include it without capabilities
                click.secho(
                    f"  Warning: Could not discover capabilities for {plugin_name}: {e}",
                    fg="yellow",
                )

            installed_plugins[plugin_info["package"]] = {
                "plugin_name": plugin_name,
                "version": plugin_info["version"],
                "capabilities": capabilities,
            }

        click.secho(f"Found {len(installed_plugins)} installed AgentUp plugins", fg="green")

    except (ImportError, AttributeError, KeyError, ValueError) as e:
        click.secho(f"Failed to discover installed plugins: {e}", fg="red")
        ctx.exit(1)

    # Calculate changes needed - use package names for consistent comparison
    installed_package_names = set(installed_plugins.keys())

    # Plugins to add (installed but not in config)
    packages_to_add = installed_package_names - current_plugins

    # Plugins to remove (in config but not installed)
    packages_to_remove = current_plugins - installed_package_names

    # Get packages to add (package names that need to be added)
    plugins_to_add = []
    for package_name, info in installed_plugins.items():
        if package_name in packages_to_add:
            plugins_to_add.append((info["plugin_name"], package_name))

    # Keep package names for removals since that's how they're stored in config
    packages_to_remove_list = list(packages_to_remove)

    # Show summary of changes
    if plugins_to_add:
        click.secho(f"\nPlugins to add ({len(plugins_to_add)}):", fg="green")
        for plugin_name, package_name in sorted(plugins_to_add):
            package_info = installed_plugins[package_name]
            click.secho(
                f"  + {package_name} (plugin: {plugin_name}, v{package_info['version']})",
                fg="green",
            )

    if packages_to_remove_list:
        click.secho(f"\nPlugins to remove ({len(packages_to_remove_list)}):", fg="red")
        for package_name in sorted(packages_to_remove_list):
            click.secho(f"  - {package_name} (package no longer installed)", fg="red")

    if not plugins_to_add and not packages_to_remove_list:
        click.secho("\n✓ agentup.yml is already in sync with installed plugins", fg="green")
        return

    if dry_run:
        click.secho(
            f"\nWould add {len(plugins_to_add)} and remove {len(packages_to_remove_list)} plugins",
            fg="cyan",
        )
        click.secho("Run without --dry-run to apply changes", fg="cyan")
        return

    # Apply changes
    changes_made = False

    # Add new plugins with discovered capabilities
    for _plugin_name, package_name in plugins_to_add:
        try:
            plugin_info = installed_plugins[package_name]

            # Create plugin override with package name and capabilities
            from agent.config.intent import CapabilityOverride, PluginOverride

            capability_overrides = {}
            if plugin_info["capabilities"]:
                for cap in plugin_info["capabilities"]:
                    capability_overrides[cap["capability_id"]] = CapabilityOverride(
                        enabled=cap["enabled"], required_scopes=cap["required_scopes"]
                    )

            # Create plugin override (package name is the key)
            plugin_override = PluginOverride(
                enabled=True,
                capabilities=capability_overrides,
            )
            # Use package name as key for intuitive user experience
            intent_config.add_plugin(package_name, plugin_override)

            if plugin_info["capabilities"]:
                click.secho(
                    f"  ✓ Added {package_name} with {len(plugin_info['capabilities'])} capabilities",
                    fg="green",
                )
            else:
                click.secho(
                    f"  ✓ Added {package_name} with no capabilities",
                    fg="green",
                )

            changes_made = True
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            click.secho(f"  ✗ Failed to add {package_name}: {e}", fg="red")

    # Remove plugins no longer installed
    for package_name in packages_to_remove_list:
        try:
            if package_name in intent_config.plugins:
                del intent_config.plugins[package_name]
                click.secho(f"  ✓ Removed {package_name}", fg="green")
                changes_made = True
        except (KeyError, AttributeError) as e:
            click.secho(f"  ✗ Failed to remove {package_name}: {e}", fg="red")

    # Save updated configuration
    if changes_made:
        try:
            save_intent_config(intent_config, str(intent_config_path))
            click.secho(
                f"\n✓ Updated agentup.yml with {len(plugins_to_add)} additions and {len(packages_to_remove_list)} removals",
                fg="green",
            )
        except (FileNotFoundError, yaml.YAMLError, PermissionError, OSError) as e:
            click.secho(f"\n✗ Failed to save agentup.yml: {e}", fg="red")
    else:
        click.secho("\nNo changes were made", fg="yellow")


@click.command()
@click.argument("plugin_name")
@click.pass_context
def add(ctx, plugin_name: str):
    """Add a specific installed plugin to agentup.yml configuration."""

    project_root = Path.cwd()
    intent_config_path = project_root / "agentup.yml"

    click.secho(f"Adding plugin '{plugin_name}' to agentup.yml...", fg="cyan")

    # Load current intent configuration
    try:
        intent_config = load_intent_config(str(intent_config_path))
    except (FileNotFoundError, yaml.YAMLError, KeyError, ValueError) as e:
        click.secho(f"Failed to load agentup.yml: {e}", fg="red")
        ctx.exit(1)

    # Check if plugin is already configured
    if intent_config.plugins and plugin_name in intent_config.plugins:
        click.secho(f"Plugin '{plugin_name}' is already configured in agentup.yml", fg="yellow")
        return

    # Verify the plugin is installed and get its information
    try:
        import importlib.metadata as metadata

        plugin_found = False
        package_name = None
        actual_plugin_name = None

        for dist in metadata.distributions():
            try:
                entry_points = dist.entry_points
                if hasattr(entry_points, "select"):
                    plugin_entries = entry_points.select(group="agentup.plugins")
                else:
                    plugin_entries = entry_points.get("agentup.plugins", [])

                # Check if this distribution provides the requested plugin
                # Try both plugin_name as plugin ID and as package name
                for entry_point in plugin_entries:
                    # Match by plugin name (entry point name)
                    if entry_point.name == plugin_name:
                        plugin_found = True
                        actual_plugin_name = entry_point.name
                        package_name = dist.metadata["Name"]
                        version = dist.version
                        break
                    # Match by package name (what user typed in uv add)
                    elif dist.metadata["Name"] == plugin_name:
                        plugin_found = True
                        actual_plugin_name = entry_point.name
                        package_name = dist.metadata["Name"]
                        version = dist.version
                        break

                if plugin_found:
                    break

            except (AttributeError, KeyError, TypeError, ValueError):
                continue

        if not plugin_found:
            click.secho(f"Plugin '{plugin_name}' is not installed or is not an AgentUp plugin", fg="red")
            click.secho(f"Install it first with: uv add {plugin_name}", fg="cyan")
            return

        click.secho(
            f"Found plugin '{actual_plugin_name}' from package {package_name} v{version}",
            fg="green",
        )

    except (ImportError, AttributeError, KeyError, TypeError) as e:
        click.secho(f"Failed to verify plugin installation: {e}", fg="red")
        ctx.exit(1)

    # Add plugin to configuration (package name is used as the key)
    try:
        from agent.config.intent import PluginOverride

        plugin_override = PluginOverride(enabled=True)

        # Use package name as key for consistent user experience
        intent_config.add_plugin(package_name, plugin_override)
        save_intent_config(intent_config, str(intent_config_path))
        click.secho(f"✓ Added {package_name} to agentup.yml", fg="green")

    except (
        KeyError,
        AttributeError,
        ValueError,
        TypeError,
        FileNotFoundError,
        yaml.YAMLError,
        PermissionError,
        OSError,
    ) as e:
        click.secho(f"Failed to add plugin to configuration: {e}", fg="red")


@click.command()
@click.argument("plugin_name")
@click.pass_context
def remove(ctx, plugin_name: str):
    """Remove a plugin from agentup.yml configuration (does not uninstall the package)."""

    project_root = Path.cwd()
    intent_config_path = project_root / "agentup.yml"

    click.secho(f"Removing plugin '{plugin_name}' from agentup.yml...", fg="cyan")

    # Load current intent configuration
    try:
        intent_config = load_intent_config(str(intent_config_path))
    except (FileNotFoundError, yaml.YAMLError, KeyError, ValueError) as e:
        click.secho(f"Failed to load agentup.yml: {e}", fg="red")
        ctx.exit(1)

    # Check if plugin is configured
    if not intent_config.plugins or plugin_name not in intent_config.plugins:
        click.secho(f"Plugin '{plugin_name}' is not configured in agentup.yml", fg="yellow")
        return

    # Remove the plugin
    try:
        del intent_config.plugins[plugin_name]

        # Save updated configuration
        save_intent_config(intent_config, str(intent_config_path))
        click.secho(f"✓ Removed {plugin_name} from agentup.yml", fg="green")
        click.secho(f"Note: To uninstall the package completely, run: uv remove {plugin_name}", fg="cyan")

    except (
        KeyError,
        AttributeError,
        FileNotFoundError,
        yaml.YAMLError,
        PermissionError,
        OSError,
    ) as e:
        click.secho(f"Failed to remove plugin from configuration: {e}", fg="red")


@click.command()
@click.argument("plugin_name")
def reload(plugin_name: str):
    """Reload a plugin at runtime (for development)."""
    try:
        from agent.plugins.manager import get_plugin_registry

        manager = get_plugin_registry()

        if plugin_name not in manager.plugins:
            click.secho(f"Plugin '{plugin_name}' not found", fg="yellow")
            return

        click.secho(f"Reloading plugin '{plugin_name}'...", fg="cyan")

        if manager.reload_plugin(plugin_name):
            click.secho(f"✓ Successfully reloaded {plugin_name}", fg="green")
        else:
            click.secho(f"✗ Failed to reload {plugin_name}", fg="red")
            click.secho("[dim]Note: Entry point plugins cannot be reloaded[/dim]")

    except ImportError:
        click.secho("Plugin system not available.", fg="red")
    except (AttributeError, KeyError, RuntimeError) as e:
        click.secho(f"Error reloading plugin: {e}", fg="red")
