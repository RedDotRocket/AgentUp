import logging

import click

from .commands.agent import agent
from .commands.plugin import plugin


def configure_cli_logging():
    # Suppress most logs for CLI usage unless explicitly set
    import os

    # Check for explicit log level from environment
    log_level = os.environ.get("AGENTUP_LOG_LEVEL", "WARNING").upper()

    # Configure basic logging first
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(message)s",  # Simple format for CLI
    )

    # Try to configure structlog if available, but don't fail if config is missing
    try:
        from agent.config.logging import setup_logging
        from agent.config.model import LoggingConfig

        # Create CLI-appropriate logging config
        cli_logging_config = LoggingConfig(
            level=log_level,
            format="text",
            console={"colors": True},
            modules={
                "agent.plugins": "WARNING",  # Suppress plugin discovery logs
                "agent.plugins.manager": "WARNING",
                "pluggy": "WARNING",  # Suppress pluggy logs
            },
        )

        setup_logging(cli_logging_config)
    except (ImportError, Exception):
        # If structlog isn't available or config loading fails, just use basic logging
        pass

    # Suppress specific noisy loggers
    logging.getLogger("agent.plugins").setLevel(logging.WARNING)
    logging.getLogger("agent.plugins.manager").setLevel(logging.WARNING)
    logging.getLogger("pluggy").setLevel(logging.WARNING)


@click.group(help="AgentUp CLI - Create and Manage agents and plugins.\n\nUse one of the subcommands below.")
@click.version_option(version="0.5.1", prog_name="agentup")
def cli():
    # Configure logging for all CLI commands
    configure_cli_logging()


# Register command groups
cli.add_command(agent)
cli.add_command(plugin)


if __name__ == "__main__":
    cli()
