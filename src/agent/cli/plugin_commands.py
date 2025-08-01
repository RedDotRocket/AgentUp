"""
CLI commands for plugin management with trusted publishing support.

This module provides comprehensive CLI commands for managing AgentUp plugins
including installation, verification, and trust management.
"""

import asyncio
import sys
from typing import Any

import click
import structlog

logger = structlog.get_logger(__name__)


def create_plugin_commands():
    """Create the plugin management command group"""

    @click.group(name="plugin")
    @click.pass_context
    def plugin_group(ctx):
        """Manage AgentUp plugins with security verification"""
        pass

    @plugin_group.command()
    @click.argument("package_name")
    @click.option("--version", "-v", help="Specific version to install")
    @click.option("--force", "-f", is_flag=True, help="Skip safety prompts")
    @click.option("--dry-run", "-n", is_flag=True, help="Verify only, don't install")
    @click.option(
        "--trust-level", type=click.Choice(["unknown", "community", "official"]), help="Minimum required trust level"
    )
    @click.option("--require-trusted", is_flag=True, help="Require trusted publishing")
    def install(
        package_name: str,
        version: str | None,
        force: bool,
        dry_run: bool,
        trust_level: str | None,
        require_trusted: bool,
    ):
        """Install an AgentUp plugin with security verification"""
        asyncio.run(_install_plugin(package_name, version, force, dry_run, trust_level, require_trusted))

    @plugin_group.command()
    @click.argument("package_name")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
    def uninstall(package_name: str, force: bool):
        """Uninstall an AgentUp plugin"""
        asyncio.run(_uninstall_plugin(package_name, force))

    @plugin_group.command()
    @click.argument("package_name")
    @click.option("--force", "-f", is_flag=True, help="Skip safety prompts")
    def upgrade(package_name: str, force: bool):
        """Upgrade an AgentUp plugin to the latest version"""
        asyncio.run(_upgrade_plugin(package_name, force))

    @plugin_group.command()
    @click.option(
        "--trust-level",
        type=click.Choice(["all", "unknown", "community", "official"]),
        default="all",
        help="Filter by trust level",
    )
    @click.option(
        "--format", "output_format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format"
    )
    def list(trust_level: str, output_format: str):
        """List installed AgentUp plugins"""
        asyncio.run(_list_plugins(trust_level, output_format))

    @plugin_group.command()
    @click.argument("query")
    @click.option("--max-results", "-n", default=10, help="Maximum number of results")
    def search(query: str, max_results: int):
        """Search for AgentUp plugins on PyPI"""
        asyncio.run(_search_plugins(query, max_results))

    @plugin_group.command()
    @click.argument("package_name")
    @click.option("--version", "-v", help="Specific version to verify")
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed verification info")
    def verify(package_name: str, version: str | None, verbose: bool):
        """Verify plugin authenticity via trusted publishing"""
        asyncio.run(_verify_plugin(package_name, version, verbose))

    @plugin_group.command()
    @click.option(
        "--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format"
    )
    def status(output_format: str):
        """Show plugin system status and trust summary"""
        asyncio.run(_show_status(output_format))

    @plugin_group.group(name="trust")
    def trust_group():
        """Manage trusted publishers"""
        pass

    @trust_group.command(name="list")
    @click.option(
        "--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format"
    )
    def list_publishers(output_format: str):
        """List trusted publishers"""
        asyncio.run(_list_trusted_publishers(output_format))

    @trust_group.command(name="add")
    @click.argument("publisher_id")
    @click.argument("repositories", nargs=-1, required=True)
    @click.option(
        "--trust-level", type=click.Choice(["community", "official"]), default="community", help="Trust level"
    )
    @click.option("--description", "-d", help="Publisher description")
    def add_publisher(publisher_id: str, repositories: tuple, trust_level: str, description: str | None):
        """Add a trusted publisher"""
        asyncio.run(_add_trusted_publisher(publisher_id, list(repositories), trust_level, description))

    @trust_group.command(name="remove")
    @click.argument("publisher_id")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
    def remove_publisher(publisher_id: str, force: bool):
        """Remove a trusted publisher"""
        asyncio.run(_remove_trusted_publisher(publisher_id, force))

    @plugin_group.command()
    @click.option("--plugin-id", help="Refresh specific plugin (all if not specified)")
    def refresh(plugin_id: str | None):
        """Refresh plugin trust verification"""
        asyncio.run(_refresh_verification(plugin_id))

    return plugin_group


# === Command Implementation Functions ===


async def _install_plugin(
    package_name: str, version: str | None, force: bool, dry_run: bool, trust_level: str | None, require_trusted: bool
):
    """Install plugin implementation"""
    try:
        from agent.config import Config
        from agent.plugins.installer import SecurePluginInstaller

        config = Config.model_dump()

        # Override config with CLI options
        if trust_level:
            config.setdefault("plugin_installation", {})["minimum_trust_level"] = trust_level
        if require_trusted:
            config.setdefault("plugin_installation", {})["require_trusted_publishing"] = True

        installer = SecurePluginInstaller(config)

        click.echo(f"🔍 Installing {package_name}" + (f" v{version}" if version else ""))

        result = await installer.install_plugin(
            package_name=package_name, version=version, force=force, dry_run=dry_run
        )

        # Display results
        _display_operation_result(result)

        if result["success"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _uninstall_plugin(package_name: str, force: bool):
    """Uninstall plugin implementation"""
    try:
        from agent.config import Config
        from agent.plugins.installer import SecurePluginInstaller

        config = Config.model_dump()
        installer = SecurePluginInstaller(config)

        click.echo(f"🗑️  Uninstalling {package_name}")

        result = await installer.uninstall_plugin(package_name, force)

        _display_operation_result(result)

        if result["success"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _upgrade_plugin(package_name: str, force: bool):
    """Upgrade plugin implementation"""
    try:
        from agent.config import Config
        from agent.plugins.installer import SecurePluginInstaller

        config = Config.model_dump()
        installer = SecurePluginInstaller(config)

        click.echo(f"⬆️  Upgrading {package_name}")

        result = await installer.upgrade_plugin(package_name, force)

        _display_operation_result(result)

        if result["success"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _list_plugins(trust_level: str, output_format: str):
    """List plugins implementation"""
    try:
        from agent.config import Config
        from agent.plugins.installer import SecurePluginInstaller
        from agent.plugins.trusted_registry import get_trusted_plugin_registry

        config = Config.model_dump()
        installer = SecurePluginInstaller(config)

        # Get installed plugins
        plugins = await installer.list_installed_plugins()

        # Get trust information from registry
        try:
            registry = get_trusted_plugin_registry()
            await registry.discover_plugins()  # Ensure plugins are discovered

            # Enhance plugin info with trust data
            for plugin in plugins:
                plugin_id = plugin["package_name"].replace("-", "_").replace("agentup_", "")
                trust_info = registry.get_plugin_trust_info(plugin_id)
                plugin.update(
                    {
                        "trust_level": trust_info.get("trust_level", "unknown"),
                        "trusted_publishing": trust_info.get("trusted_publishing", False),
                        "publisher": trust_info.get("publisher"),
                    }
                )
        except Exception as e:
            logger.debug(f"Could not get trust information: {e}")

        # Filter by trust level
        if trust_level != "all":
            plugins = [p for p in plugins if p.get("trust_level") == trust_level]

        # Display results
        if output_format == "table":
            _display_plugins_table(plugins)
        elif output_format == "json":
            import json

            click.echo(json.dumps(plugins, indent=2))
        elif output_format == "yaml":
            import yaml

            click.echo(yaml.dump(plugins, default_flow_style=False))

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _search_plugins(query: str, max_results: int):
    """Search plugins implementation"""
    try:
        from agent.config import Config
        from agent.plugins.installer import SecurePluginInstaller

        config = Config.model_dump()
        installer = SecurePluginInstaller(config)

        click.echo(f"🔍 Searching for '{query}'...")

        results = await installer.search_plugins(query, max_results)

        if results:
            click.echo(f"\n📦 Found {len(results)} plugins:")
            for plugin in results:
                click.echo(f"  • {plugin['name']} v{plugin['version']}")
                click.echo(f"    {plugin['summary']}")
                click.echo(f"    Author: {plugin['author']}")
                click.echo()
        else:
            click.echo("No plugins found matching your search.")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _verify_plugin(package_name: str, version: str | None, verbose: bool):
    """Verify plugin implementation"""
    try:
        from agent.config import Config
        from agent.plugins.trusted_publishing import TrustedPublishingVerifier

        config = Config.model_dump()
        verifier = TrustedPublishingVerifier(config)

        click.echo(f"🔍 Verifying {package_name}" + (f" v{version}" if version else ""))

        verification = await verifier.verify_plugin_authenticity(package_name, version)

        # Display verification results
        click.echo("\n" + "=" * 50)
        click.echo(f"📋 Verification Report: {package_name}")
        click.echo("=" * 50)

        if verification["trusted_publishing"]:
            click.echo("✅ Trusted Publishing: Yes")
            click.echo(f"   Publisher: {verification.get('publisher', 'Unknown')}")
            click.echo(f"   Repository: {verification.get('repository', 'Unknown')}")
            click.echo(f"   Trust Level: {verification.get('trust_level', 'Unknown')}")
            click.echo(f"   Workflow: {verification.get('workflow', 'Unknown')}")
        else:
            click.echo("⚠️  Trusted Publishing: No")

        if verification.get("errors"):
            click.echo("\n❌ Verification Errors:")
            for error in verification["errors"]:
                click.echo(f"   • {error}")

        if verbose:
            click.echo("\n📊 Full Verification Data:")
            import json

            click.echo(json.dumps(verification, indent=2))

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _show_status(output_format: str):
    """Show status implementation"""
    try:
        from agent.plugins.trusted_registry import get_trusted_plugin_registry

        registry = get_trusted_plugin_registry()
        await registry.discover_plugins()

        status = await registry.get_health_status()

        if output_format == "table":
            click.echo("🔒 AgentUp Plugin System Status")
            click.echo("=" * 40)

            click.echo(f"Total Plugins: {status['total_plugins']}")
            click.echo(f"Total Capabilities: {status['total_capabilities']}")

            tp_info = status.get("trusted_publishing", {})
            click.echo("\n🛡️  Trusted Publishing:")
            click.echo(f"   Enabled: {tp_info.get('enabled', False)}")
            click.echo(f"   Required: {tp_info.get('require_trusted_publishing', False)}")
            click.echo(f"   Min Trust Level: {tp_info.get('minimum_trust_level', 'unknown')}")

            ts = tp_info.get("trust_summary", {})
            click.echo("\n📊 Trust Summary:")
            click.echo(f"   Trusted Published: {ts.get('trusted_published', 0)}")
            click.echo(f"   Official: {ts.get('trust_levels', {}).get('official', 0)}")
            click.echo(f"   Community: {ts.get('trust_levels', {}).get('community', 0)}")
            click.echo(f"   Unknown: {ts.get('trust_levels', {}).get('unknown', 0)}")

            publishers = ts.get("publishers", {})
            if publishers:
                click.echo("\n👥 Publishers:")
                for publisher, count in publishers.items():
                    click.echo(f"   {publisher}: {count} plugins")

        elif output_format == "json":
            import json

            click.echo(json.dumps(status, indent=2))

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _list_trusted_publishers(output_format: str):
    """List trusted publishers implementation"""
    try:
        from agent.config import Config
        from agent.plugins.trusted_publishing import TrustedPublishingVerifier

        config = Config.model_dump()
        verifier = TrustedPublishingVerifier(config)

        publishers = verifier.list_trusted_publishers()

        if output_format == "table":
            click.echo("👥 Trusted Publishers")
            click.echo("=" * 50)

            for publisher_id, config in publishers.items():
                click.echo(f"\n📋 {publisher_id}")
                click.echo(f"   Trust Level: {config['trust_level']}")
                click.echo(f"   Description: {config.get('description', 'No description')}")
                click.echo("   Repositories:")
                for repo in config["repositories"]:
                    click.echo(f"     • {repo}")

        elif output_format == "json":
            import json

            click.echo(json.dumps(publishers, indent=2))

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _add_trusted_publisher(publisher_id: str, repositories: list[str], trust_level: str, description: str | None):
    """Add trusted publisher implementation"""
    try:
        from agent.plugins.trusted_registry import get_trusted_plugin_registry

        registry = get_trusted_plugin_registry()

        success = registry.add_trusted_publisher(
            publisher_id=publisher_id,
            repositories=repositories,
            trust_level=trust_level,
            description=description or f"Publisher {publisher_id}",
        )

        if success:
            click.echo(f"✅ Added trusted publisher: {publisher_id}")
            click.echo(f"   Trust Level: {trust_level}")
            click.echo(f"   Repositories: {', '.join(repositories)}")
        else:
            click.echo(f"❌ Failed to add publisher: {publisher_id}")
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _remove_trusted_publisher(publisher_id: str, force: bool):
    """Remove trusted publisher implementation"""
    try:
        from agent.plugins.trusted_registry import get_trusted_plugin_registry

        registry = get_trusted_plugin_registry()

        if not force:
            click.echo(f"⚠️  This will remove trusted publisher '{publisher_id}' and may affect plugin trust.")
            if not click.confirm("Are you sure?"):
                click.echo("Operation cancelled.")
                return

        success = registry.remove_trusted_publisher(publisher_id)

        if success:
            click.echo(f"✅ Removed trusted publisher: {publisher_id}")
        else:
            click.echo(f"❌ Publisher not found: {publisher_id}")
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


async def _refresh_verification(plugin_id: str | None):
    """Refresh verification implementation"""
    try:
        from agent.plugins.trusted_registry import get_trusted_plugin_registry

        registry = get_trusted_plugin_registry()

        if plugin_id:
            click.echo(f"🔄 Refreshing verification for {plugin_id}...")
        else:
            click.echo("🔄 Refreshing verification for all plugins...")

        result = await registry.refresh_plugin_trust_verification(plugin_id)

        if "error" in result:
            click.echo(f"❌ {result['error']}")
            sys.exit(1)
        else:
            refreshed = result["refreshed"]
            click.echo(f"✅ Refreshed verification for {len(refreshed)} plugins")
            if plugin_id:  # Show specific plugin info
                for pid in refreshed:
                    trust_info = registry.get_plugin_trust_info(pid)
                    level = trust_info.get("trust_level", "unknown")
                    click.echo(f"   {pid}: {level}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


# === Display Helper Functions ===


def _display_operation_result(result: dict[str, Any]):
    """Display operation result in a formatted way"""

    # Display messages
    for message in result.get("messages", []):
        click.echo(message)

    # Display warnings
    for warning in result.get("warnings", []):
        click.echo(f"⚠️  {warning}")

    # Display errors
    for error in result.get("errors", []):
        click.echo(f"❌ {error}", err=True)

    # Display verification info if available
    verification = result.get("verification", {})
    if verification and verification.get("trusted_publishing"):
        click.echo(
            f"🔒 Trust: {verification.get('trust_level', 'unknown')} "
            f"(Publisher: {verification.get('publisher', 'unknown')})"
        )


def _display_plugins_table(plugins: list[dict[str, Any]]):
    """Display plugins in a formatted table"""
    if not plugins:
        click.echo("No plugins found.")
        return

    click.echo(f"📦 Installed AgentUp Plugins ({len(plugins)})")
    click.echo("=" * 80)

    # Header
    click.echo(f"{'Name':<30} {'Version':<10} {'Trust':<12} {'Publisher':<20}")
    click.echo("-" * 80)

    # Rows
    for plugin in plugins:
        name = plugin["package_name"][:29]
        version = plugin["version"][:9]
        trust = plugin.get("trust_level", "unknown")[:11]
        publisher = (plugin.get("publisher") or "")[:19]

        # Add trust indicator
        if trust == "official":
            trust_indicator = "✅"
        elif trust == "community":
            trust_indicator = "🟡"
        else:
            trust_indicator = "⚪"

        click.echo(f"{name:<30} {version:<10} {trust_indicator} {trust:<11} {publisher:<20}")

    click.echo("-" * 80)

    # Summary
    trust_counts = {}
    for plugin in plugins:
        trust = plugin.get("trust_level", "unknown")
        trust_counts[trust] = trust_counts.get(trust, 0) + 1

    summary_parts = []
    if trust_counts.get("official"):
        summary_parts.append(f"✅ {trust_counts['official']} official")
    if trust_counts.get("community"):
        summary_parts.append(f"🟡 {trust_counts['community']} community")
    if trust_counts.get("unknown"):
        summary_parts.append(f"⚪ {trust_counts['unknown']} unknown")

    if summary_parts:
        click.echo(f"Summary: {', '.join(summary_parts)}")


# Export the command group
plugin_commands = create_plugin_commands()
