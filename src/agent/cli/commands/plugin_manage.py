from pathlib import Path

import click
import structlog
import yaml

from agent.cli.cli_utils import MutuallyExclusiveOption
from agent.config.intent import load_intent_config, save_intent_config

# Note: Resolver imports removed - using uv-based workflow instead

logger = structlog.get_logger(__name__)


def _find_similar_plugin_names(target_name: str, available_names: list[str], max_suggestions: int = 3) -> list[str]:
    """Find similar plugin names using simple string similarity."""
    if not available_names:
        return []

    suggestions = []

    # 1. Exact match (case-insensitive)
    for name in available_names:
        if name.lower() == target_name.lower():
            return [name]  # Exact match found

    # 2. Simple character replacement (- <-> _)
    target_normalized = target_name.replace("_", "-")
    for name in available_names:
        name_normalized = name.replace("_", "-")
        if target_normalized.lower() == name_normalized.lower():
            suggestions.append(name)

    # 3. Basic edit distance for other close matches
    if len(suggestions) < max_suggestions:

        def simple_edit_distance(s1: str, s2: str) -> int:
            """Simple Levenshtein distance calculation."""
            if len(s1) < len(s2):
                return simple_edit_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)

            previous_row = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]

        # Calculate similarity for remaining names
        similarities = []
        for name in available_names:
            if name not in suggestions:
                distance = simple_edit_distance(target_name.lower(), name.lower())
                # Only suggest if distance is reasonable (less than half the length)
                if distance <= min(len(target_name), len(name)) // 2:
                    similarities.append((name, distance))

        # Sort by distance and add to suggestions
        similarities.sort(key=lambda x: x[1])
        suggestions.extend([name for name, _ in similarities[: max_suggestions - len(suggestions)]])

    return suggestions[:max_suggestions]


@click.command()
@click.argument("plugin_name", required=True)
@click.option(
    "--add-scope",
    "-a",
    multiple=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["remove_scope"],
    help="Add scopes: -a capability_id::scope (repeatable).",
)
@click.option(
    "--remove-scope",
    "-r",
    multiple=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["add_scope"],
    help="Remove scopes: -r capability_id::scope (repeatable).",
)
@click.option("-n", "--dry-run", is_flag=True, help="Show planned changes only (File diff, no write).")
@click.option("--config", type=click.Path(path_type=Path), show_default=True)
@click.pass_context
def manage(
    ctx: click.Context,
    plugin_name: str,
    add_scope: tuple[str, ...],
    remove_scope: tuple[str, ...],
    dry_run: bool,
    config: Path | None = None,
):
    """Add or remove scopes on a plugin capability in agentup.yml.

    Examples:
    agentup plugin manage brave_search -a search_images::search:images:query
    agentup plugin manage brave_search -r search_internet::search:web:query
    """
    # Resolve config path
    intent_config_path = config if config else (Path.cwd() / "agentup.yml")

    # Load config
    try:
        intent_config = load_intent_config(str(intent_config_path))
    except (FileNotFoundError, yaml.YAMLError) as e:
        click.secho(f"Failed to load agentup.yml: {e}", fg="red")
        ctx.exit(1)

    # Validate plugin exists in config
    if not intent_config.plugins or plugin_name not in intent_config.plugins:
        click.secho(f"Plugin '{plugin_name}' not found in {intent_config_path}", fg="red")
        ctx.exit(1)

    if not add_scope and not remove_scope:
        click.secho("Nothing to do. Use -a/--add-scope or -r/--remove-scope.", fg="yellow")
        ctx.exit(0)

    # Collect planned changes (only what will be applied)
    planned_changes: list[str] = []
    changed = False

    plugin_override = intent_config.plugins[plugin_name]

    for arg in add_scope:
        if "::" not in arg:
            click.secho(f"Invalid scope format '{arg}'. Use 'capability_id::scope'.", fg="red")
            continue
        capability_id, scope_name = arg.split("::", 1)
        if capability_id not in plugin_override.capabilities:
            click.secho(f"Capability '{capability_id}' not found for plugin '{plugin_name}'.", fg="yellow")
            continue

        cap_override = plugin_override.capabilities[capability_id]

        if isinstance(cap_override, dict):
            scopes = cap_override.get("required_scopes")
        else:
            scopes = getattr(cap_override, "required_scopes", None)

        if scopes is None:
            scopes = []
        elif isinstance(scopes, str):
            scopes = [scopes]
        else:
            scopes = list(scopes)

        if scope_name not in scopes:
            scopes.append(scope_name)
            scopes = sorted(set(scopes))
            planned_changes.append(f"ADD scope '{scope_name}' → capability '{capability_id}' (plugin '{plugin_name}')")
            if isinstance(cap_override, dict):
                cap_override["required_scopes"] = scopes
            else:
                cap_override.required_scopes = scopes
            changed = True
        else:
            click.secho(
                f"Scope '{scope_name}' already exists for capability '{capability_id}'.",
                fg="yellow",
            )

    for arg in remove_scope:
        if "::" not in arg:
            click.secho(f"Invalid scope format '{arg}'. Use 'capability_id::scope'.", fg="red")
            continue
        capability_id, scope_name = arg.split("::", 1)
        if capability_id not in plugin_override.capabilities:
            click.secho(f"Capability '{capability_id}' not found for plugin '{plugin_name}'.", fg="yellow")
            continue

        cap_override = plugin_override.capabilities[capability_id]

        if isinstance(cap_override, dict):
            scopes = cap_override.get("required_scopes")
        else:
            scopes = getattr(cap_override, "required_scopes", None)

        if scopes is None:
            scopes = []
        elif isinstance(scopes, str):
            scopes = [scopes]
        else:
            scopes = list(scopes)

        if scope_name in scopes:
            scopes.remove(scope_name)
            planned_changes.append(f"DROP scope '{scope_name}' ← capability '{capability_id}' (plugin '{plugin_name}')")
            if isinstance(cap_override, dict):
                cap_override["required_scopes"] = scopes
            else:
                cap_override.required_scopes = scopes
            changed = True
        else:
            click.secho(
                f"Scope '{scope_name}' not found for capability '{capability_id}'.",
                fg="yellow",
            )

    if not changed:
        click.secho("No changes made.", fg="yellow")
        ctx.exit(0)

    # Dry run output
    if dry_run:
        click.secho("\n--- DRY RUN: planned changes ---\n", fg="cyan")
        for line in planned_changes:
            click.echo(f"• {line}")
        click.secho("\nNo files were written.", fg="cyan")
        ctx.exit(0)

    if getattr(plugin_override, "capabilities", None):
        for _cid, _cap in plugin_override.capabilities.items():
            if isinstance(_cap, dict):
                rs = _cap.get("required_scopes")
                _cap["required_scopes"] = [] if rs is None else ([rs] if isinstance(rs, str) else list(rs))
            else:
                rs = getattr(_cap, "required_scopes", None)
                _cap.required_scopes = [] if rs is None else [rs] if isinstance(rs, str) else list(rs)

    # Persist changes
    try:
        save_intent_config(intent_config, str(intent_config_path))
        click.secho("\n✓ agentup.yml has been updated.", fg="green")
        for line in planned_changes:
            click.echo(f" {line}")
    except (yaml.YAMLError, PermissionError, OSError) as e:
        click.secho(f"Failed to save agentup.yml: {e}", fg="red")
        ctx.exit(1)


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

            installed_plugins[plugin_name] = {
                "package_name": plugin_info["package"],
                "version": plugin_info["version"],
                "capabilities": capabilities,
            }

        click.secho(f"Found {len(installed_plugins)} installed AgentUp plugins", fg="green")

    except (ImportError, AttributeError, KeyError, ValueError) as e:
        click.secho(f"Failed to discover installed plugins: {e}", fg="red")
        ctx.exit(1)

    # Calculate changes needed - use plugin (entry point) names for comparison
    installed_plugin_names = set(installed_plugins.keys())

    # Plugins to add (installed but not in config)
    plugins_to_add = installed_plugin_names - current_plugins

    # Plugins to remove (in config but not installed)
    plugins_to_remove = current_plugins - installed_plugin_names

    # Convert to list for processing
    plugins_to_add_list = list(plugins_to_add)
    plugins_to_remove_list = list(plugins_to_remove)

    # Show summary of changes
    if plugins_to_add_list:
        click.secho(f"\nPlugins to add ({len(plugins_to_add_list)}):", fg="green")
        for plugin_name in sorted(plugins_to_add_list):
            plugin_info = installed_plugins[plugin_name]
            click.secho(
                f"  + {plugin_name} (package: {plugin_info['package_name']}, v{plugin_info['version']})",
                fg="green",
            )

    if plugins_to_remove_list:
        click.secho(f"\nPlugins to remove ({len(plugins_to_remove_list)}):", fg="red")
        for plugin_name in sorted(plugins_to_remove_list):
            click.secho(f"  - {plugin_name} (plugin no longer installed)", fg="red")

    if not plugins_to_add_list and not plugins_to_remove_list:
        click.secho("\n✓ agentup.yml is already in sync with installed plugins", fg="green")
        return

    if dry_run:
        click.secho(
            f"\nWould add {len(plugins_to_add_list)} and remove {len(plugins_to_remove_list)} plugins",
            fg="cyan",
        )
        click.secho("Run without --dry-run to apply changes", fg="cyan")
        return

    # Apply changes
    changes_made = False

    # Add new plugins with discovered capabilities
    for plugin_name in plugins_to_add_list:
        try:
            plugin_info = installed_plugins[plugin_name]

            # Create plugin override with capabilities
            from agent.config.intent import CapabilityOverride, PluginOverride

            capability_overrides = {}
            if plugin_info["capabilities"]:
                for cap in plugin_info["capabilities"]:
                    capability_overrides[cap["capability_id"]] = CapabilityOverride(
                        enabled=cap["enabled"], required_scopes=cap["required_scopes"]
                    )

            # Create plugin override (plugin name is the key)
            plugin_override = PluginOverride(
                enabled=True,
                capabilities=capability_overrides,
            )
            # Use plugin (entry point) name as key to match plugin loading logic
            intent_config.add_plugin(plugin_name, plugin_override)

            if plugin_info["capabilities"]:
                click.secho(
                    f"  ✓ Added {plugin_name} (from {plugin_info['package_name']}) with {len(plugin_info['capabilities'])} capabilities",
                    fg="green",
                )
            else:
                click.secho(
                    f"  ✓ Added {plugin_name} (from {plugin_info['package_name']}) with no capabilities",
                    fg="green",
                )

            changes_made = True
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            click.secho(f"  ✗ Failed to add {plugin_name}: {e}", fg="red")

    # Remove plugins no longer installed
    for plugin_name in plugins_to_remove_list:
        try:
            if plugin_name in intent_config.plugins:
                del intent_config.plugins[plugin_name]
                click.secho(f"  ✓ Removed {plugin_name}", fg="green")
                changes_made = True
        except (KeyError, AttributeError) as e:
            click.secho(f"  ✗ Failed to remove {plugin_name}: {e}", fg="red")

    # Save updated configuration
    if changes_made:
        try:
            save_intent_config(intent_config, str(intent_config_path))
            click.secho(
                f"\n✓ Updated agentup.yml with {len(plugins_to_add_list)} additions and {len(plugins_to_remove_list)} removals",
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

            # Suggest similar plugin names from available installed plugins
            try:
                from agent.plugins.manager import PluginRegistry

                registry = PluginRegistry()
                available_plugins_info = registry.discover_all_available_plugins()
                available_plugins = [p["name"] for p in available_plugins_info]
                suggestions = _find_similar_plugin_names(plugin_name, available_plugins)
                if suggestions:
                    if len(suggestions) == 1:
                        click.secho(f"Did you mean: {suggestions[0]}?", fg="cyan")
                    else:
                        click.secho(f"Did you mean one of: {', '.join(suggestions)}?", fg="cyan")
            except Exception:
                pass  # nosec
            return

        click.secho(
            f"Found plugin '{actual_plugin_name}' from package {package_name} v{version}",
            fg="green",
        )

    except (ImportError, AttributeError, KeyError, TypeError) as e:
        click.secho(f"Failed to verify plugin installation: {e}", fg="red")
        ctx.exit(1)

    # Add plugin to configuration with capability discovery
    try:
        from agent.config.intent import CapabilityOverride, PluginOverride

        # Discover capabilities from the plugin (same logic as sync)
        capability_overrides = {}

        try:
            # Load the plugin and discover capabilities
            import importlib.metadata as metadata

            entry_points = metadata.entry_points()
            if hasattr(entry_points, "select"):
                plugin_entries = entry_points.select(group="agentup.plugins")
            else:
                plugin_entries = entry_points.get("agentup.plugins", [])

            for entry_point in plugin_entries:
                if entry_point.name == actual_plugin_name:
                    plugin_class = entry_point.load()
                    plugin_instance = plugin_class()

                    # Get capability definitions if available
                    if hasattr(plugin_instance, "get_capability_definitions"):
                        cap_definitions = plugin_instance.get_capability_definitions()

                        for cap_def in cap_definitions:
                            capability_overrides[cap_def.id] = CapabilityOverride(
                                enabled=True, required_scopes=cap_def.required_scopes
                            )
                    break
        except (ImportError, AttributeError, TypeError, ValueError) as e:
            click.secho(
                f"  Warning: Could not discover capabilities for {actual_plugin_name}: {e}",
                fg="yellow",
            )

        plugin_override = PluginOverride(
            enabled=True,
            capabilities=capability_overrides,
        )

        # Use plugin (entry point) name as key to match plugin loading logic
        intent_config.add_plugin(actual_plugin_name, plugin_override)
        save_intent_config(intent_config, str(intent_config_path))

        if capability_overrides:
            click.secho(
                f"✓ Added {actual_plugin_name} (from package {package_name}) with {len(capability_overrides)} capabilities to agentup.yml",
                fg="green",
            )
        else:
            click.secho(
                f"✓ Added {actual_plugin_name} (from package {package_name}) with no capabilities to agentup.yml",
                fg="green",
            )

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

        # Suggest similar plugin names from configured plugins
        if intent_config.plugins:
            configured_plugins = list(intent_config.plugins.keys())
            suggestions = _find_similar_plugin_names(plugin_name, configured_plugins)
            if suggestions:
                if len(suggestions) == 1:
                    click.secho(f"Did you mean: {suggestions[0]}?", fg="cyan")
                else:
                    click.secho(f"Did you mean one of: {', '.join(suggestions)}?", fg="cyan")

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

        click.secho("Restart the agent to reload plugin changes.", fg="cyan")

    except ImportError:
        click.secho("Plugin system not available.", fg="red")
    except (AttributeError, KeyError, RuntimeError) as e:
        click.secho(f"Error accessing plugin: {e}", fg="red")
