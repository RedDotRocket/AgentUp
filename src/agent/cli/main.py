import logging

import click

from .commands.agent import agent
from .commands.plugin import plugin


def configure_cli_logging():
    """Configure logging for CLI commands."""
    # Suppress most logs for CLI usage unless explicitly set
    import os

    # Check for explicit log level from environment
    log_level = os.environ.get("AGENTUP_LOG_LEVEL", "WARNING").upper()

    # Configure basic logging first
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(message)s",  # Simple format for CLI
    )

    # Try to configure structlog if available
    try:
        from agent.config.logging import setup_logging
        from agent.config.models import LoggingConfig

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
    except ImportError:
        # If structlog isn't available, just use basic logging
        pass

    # Suppress specific noisy loggers
    logging.getLogger("agent.plugins").setLevel(logging.WARNING)
    logging.getLogger("agent.plugins.manager").setLevel(logging.WARNING)
    logging.getLogger("pluggy").setLevel(logging.WARNING)


@click.group()
@click.version_option(version="0.1.0", prog_name="agentup")
def cli():
    """AgentUp - Create, build, manage, and deploy AI agents."""
    # Configure logging for all CLI commands
    configure_cli_logging()


# Register command groups
cli.add_command(agent)
cli.add_command(plugin)


if __name__ == "__main__":
    cli()
