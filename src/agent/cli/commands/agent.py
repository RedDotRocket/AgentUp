import click


@click.group()
def agent():
    """Manage agents - create, run, validate, deploy."""
    pass


@agent.command()
@click.argument("name", required=False)
@click.option(
    "--template",
    "-t",
    default="standard",
    type=click.Choice(["minimal", "standard", "full", "demo"], case_sensitive=False),
    help="Project template (default: standard)",
)
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Use existing agent_config.yaml as template")
@click.option("--no-git", is_flag=True, help="Skip git repository initialization")
def create(name, template, output_dir, config, no_git):
    """Create a new agent project.

    \b
    Templates:
      minimal  - Barebone agent (no AI, no external dependencies)
      standard - AI-powered agent with MCP (recommended)
      full     - Enterprise agent with all features
      demo     - Example agent showcasing capabilities

    \b
    Examples:
      agentup agent create                      # Interactive mode (standard template)
      agentup agent create my-bot               # Standard template with name
      agentup agent create --template minimal   # Minimal template
      agentup agent create --template demo      # Demo template with examples
    """
    # Import and call the original create_agent functionality
    from . import create_agent

    return create_agent.create_agent.callback(name, template, False, False, output_dir, config, no_git)


@agent.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), default="agent_config.yaml", help="Path to agent config file"
)
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", type=click.IntRange(1, 65535), default=8000, help="Port to bind to")
@click.option("--reload/--no-reload", default=True, help="Enable auto-reload")
def serve(config, host, port, reload):
    """Start the development server.

    Examples:
        agentup agent serve                    # Start on default host:port
        agentup agent serve --port 8080        # Custom port
        agentup agent serve --host 0.0.0.0     # Bind to all interfaces
    """
    # Import and call the original dev functionality
    from pathlib import Path

    from . import dev

    return dev.dev.callback(Path(config), host, port, reload)


@agent.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), default="agent_config.yaml", help="Configuration file to validate"
)
@click.option("--check-env", "-e", is_flag=True, help="Check environment variables")
@click.option("--check-handlers", "-h", is_flag=True, help="Check handler implementations")
@click.option("--strict", "-s", is_flag=True, help="Strict validation (fail on warnings)")
def validate(config, check_env, check_handlers, strict):
    """Validate agent configuration and setup.

    Examples:
        agentup agent validate                 # Validate default config
        agentup agent validate --strict       # Strict validation
        agentup agent validate --check-env    # Check environment variables
    """
    # Import and call the original validate functionality
    from . import validate as validate_cmd

    return validate_cmd.validate.callback(config, check_env, check_handlers, strict)


@agent.command()
@click.option(
    "--type", "-t", type=click.Choice(["docker", "k8s", "helm"]), required=True, help="Deployment type to generate"
)
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--port", "-p", default=8080, help="Application port")
@click.option("--replicas", "-r", default=1, help="Number of replicas (k8s/helm only)")
@click.option("--image-name", help="Docker image name")
@click.option("--image-tag", default="latest", help="Docker image tag")
def deploy(type, output, port, replicas, image_name, image_tag):
    """Generate deployment files for your agent.

    Examples:
        agentup agent deploy --type docker     # Generate Docker files
        agentup agent deploy --type k8s        # Generate K8s manifests
        agentup agent deploy --type helm       # Generate Helm chart
    """
    # Import and call the original deploy functionality
    from . import deploy as deploy_cmd

    return deploy_cmd.deploy.callback(type, output, port, replicas, image_name, image_tag)
