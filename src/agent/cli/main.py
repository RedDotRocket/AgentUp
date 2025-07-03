# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Luke Hinds <luke@rdrocket.com>

import click

from .commands.agent import agent
from .commands.plugin import plugin
from .commands.skill import skill


@click.group()
@click.version_option(version="0.1.0", prog_name="agentup")
def cli():
    """AgentUp - Create, build, manage, and deploy AI agents."""
    pass


# Register command groups
cli.add_command(agent)
cli.add_command(skill)
cli.add_command(plugin)


if __name__ == "__main__":
    cli()
