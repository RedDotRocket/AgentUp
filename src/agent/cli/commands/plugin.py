import click

from ...utils.version import get_version
from ..cli_utils import OrderedGroup
from .plugin_info import config, info, list_plugins, validate

# Import subcommands from specialized modules
from .plugin_init import init
from .plugin_manage import add, manage, reload, remove, sync

# Export all commands and functions
__all__ = [
    "plugin",
    "init",
    "add",
    "remove",
    "sync",
    "reload",
    "list_plugins",
    "info",
    "config",
    "validate",
    "get_version",
    "manage",
]


@click.group("plugin", cls=OrderedGroup, help="Manage plugins and their configurations.")
@click.version_option(version=get_version(), prog_name="agentup")
def plugin():
    """Plugin management commands."""
    pass


# Register all subcommands
plugin.add_command(init)
plugin.add_command(add)
plugin.add_command(remove)
plugin.add_command(sync)
plugin.add_command(reload)
plugin.add_command(list_plugins)
plugin.add_command(info)
plugin.add_command(config)
plugin.add_command(validate)
plugin.add_command(manage)
