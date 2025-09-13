import logging
import os

import click

from ..utils.version import get_version
from .cli_utils import OrderedGroup
from .commands.deploy import deploy
from .commands.init import init
from .commands.mcp import mcp
from .commands.plugin import plugin
from .commands.run import run
from .commands.validate import validate


def setup_cli_logging():
    """Sets up unified logging for the CLI using structlog if available."""

    # Check for explicit log level from environment or default to WARNING
    log_level = os.environ.get("AGENTUP_LOG_LEVEL", "WARNING").upper()
    is_debug = log_level == "DEBUG"

    try:
        from agent.config.logging import setup_logging
        from agent.config.model import LogFormat, LoggingConfig, LoggingConsoleConfig

        # In debug mode, allow resolver logs through, otherwise suppress them
        resolver_level = "INFO" if is_debug else "CRITICAL"  # noqa: F841
        cache_level = (  # noqa: F841
            "WARNING" if is_debug else "CRITICAL"
        )  # Suppress cache debug logs even in debug mode

        # Create logging config
        console_config = LoggingConsoleConfig(
            enabled=True,
            colors=True,
            show_time=True,
            show_level=True,
        )
        cli_logging_config = LoggingConfig(
            enabled=True,
            level=log_level,
            format=LogFormat.TEXT,
            console=console_config,
            correlation_id=False,
            request_logging=False,
            structured_data=False,
            modules={
                "agent.plugins": "WARNING",  # Suppress plugin discovery logs
                "agent.plugins.manager": "WARNING",
            },
        )
        setup_logging(cli_logging_config)
    except (ImportError, Exception):
        # Fallback to standard library logging if structlog config fails
        logging.basicConfig(
            level=getattr(logging, log_level, logging.WARNING),
            format="%(message)s",
        )
        # Suppress specific noisy loggers in fallback mode
        # Suppress specific noisy loggers (but allow them in debug mode)
        resolver_log_level = logging.INFO if is_debug else logging.CRITICAL
        cache_log_level = logging.WARNING if is_debug else logging.CRITICAL  # Suppress cache debug logs

        logging.getLogger("agent.plugins").setLevel(logging.WARNING)
        logging.getLogger("agent.plugins.manager").setLevel(logging.WARNING)
        logging.getLogger("agent.config.plugin_resolver").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver.dependency_resolver").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver.error_handler").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver.reporters").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver.providers").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver.cache").setLevel(cache_log_level)  # Suppress cache debug logs
        logging.getLogger("agent.resolver.installer").setLevel(resolver_log_level)
        logging.getLogger("agent.resolver.lock_manager").setLevel(resolver_log_level)
        logging.getLogger("pluggy").setLevel(logging.WARNING)


@click.group(
    cls=OrderedGroup,
    help="AgentUp CLI - Create and Manage agents and plugins.\n\nUse one of the subcommands below.",
)
@click.version_option(version=get_version(), prog_name="agentup")
def cli():
    # Set up logging for all CLI commands
    setup_cli_logging()
    """Main entry point for the AgentUp CLI."""
    pass


# Register command groups
cli.add_command(init)
cli.add_command(run)
cli.add_command(deploy)
cli.add_command(validate)
cli.add_command(plugin)
cli.add_command(mcp)


if __name__ == "__main__":
    cli()
