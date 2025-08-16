import click


@click.command()
@click.argument("name", required=False)
@click.argument("version", required=False)
@click.option("--quick", "-q", is_flag=True, help="Quick setup with minimal features (non-interactive)")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Use existing agentup.yml as template")
@click.option("--no-git", is_flag=True, help="Skip git repository initialization")
def init(name, version, quick, output_dir, config, no_git):
    """Initializes a new agent project."""
    # Import and call the original init_agent functionality
    from . import init_agent

    return init_agent.init_agent.callback(name, version, quick, output_dir, config, no_git)
