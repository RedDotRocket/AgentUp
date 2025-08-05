import subprocess  # nosec
from pathlib import Path
from typing import Any

import click
import questionary
from questionary import Style

from agent.generator import ProjectGenerator
from agent.templates import get_feature_choices


def initialize_git_repo(project_path: Path) -> bool:
    """
    Initialize a git repository in the project directory.

    Returns:
        bool: True if git initialization was successful, False otherwise.

    Bandit:
        This function uses subprocess to run git commands, which is generally safe
        as long as the entry point is the CLI command and the project_path is controlled.
    """
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)  # nosec

        subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)  # nosec

        subprocess.run(["git", "add", "."], cwd=project_path, check=True, capture_output=True)  # nosec

        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, check=True, capture_output=True)  # nosec

        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


custom_style = Style(
    [
        ("qmark", "fg:#5f819d bold"),
        ("question", "bold"),
        ("answer", "fg:#85678f bold"),
        ("pointer", "fg:#5f819d bold"),
        ("highlighted", "fg:#5f819d bold"),
        ("selected", "fg:#85678f"),
        ("separator", "fg:#cc6666"),
        ("instruction", "fg:#969896"),
        ("text", ""),
    ]
)


@click.command()
@click.argument("name", required=False)
@click.option("--quick", "-q", is_flag=True, help="Quick setup with minimal features (basic handlers only)")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Use existing agentup.yml as template")
@click.option("--no-git", is_flag=True, help="Skip git repository initialization")
def create_agent(
    name: str | None,
    quick: bool,
    output_dir: str | None,
    config: str | None,
    no_git: bool,
):
    """Create a new Agent project.

    By default, this will initialize a git repository in the project directory
    with an initial commit. Use --no-git to skip git initialization.

    Examples:
        agentup agent create                    # Interactive mode with git init
        agentup agent create my-agent           # Interactive with name
        agentup agent create --quick my-agent   # Quick setup with minimal features
        agentup agent create --no-git my-agent  # Skip git initialization
        agentup agent create --quick my-chatbot
    """
    click.echo(click.style("-" * 40, fg="white", dim=True))
    click.echo(click.style("Create your AI agent:", fg="white", dim=True))
    click.echo(click.style("-" * 40, fg="white", dim=True))

    project_config = {}

    if not name:
        name = questionary.text("Agent name:", style=custom_style, validate=lambda x: len(x.strip()) > 0).ask()
        if not name:
            click.echo("Cancelled.")
            return

    project_config["name"] = name

    if not output_dir:
        # Normalize the name for directory: lowercase and replace spaces with underscores
        dir_name = name.lower().replace(" ", "_")
        output_dir = Path.cwd() / dir_name
    else:
        output_dir = Path(output_dir)

    if output_dir.exists():
        if quick:
            # In quick mode, automatically overwrite if directory exists
            click.echo(f"Directory {output_dir} already exists. Continuing in quick mode...")
        else:
            if not questionary.confirm(
                f"Directory {output_dir} already exists. Continue?", default=False, style=custom_style
            ).ask():
                click.echo("Cancelled.")
                return

    if quick:
        project_config["description"] = f"AI Agent {name} Project."
        project_config["features"] = []  # Empty features for quick mode
        project_config["feature_config"] = {}
    else:
        description = questionary.text("Description:", default=f"AI Agent {name} Project.", style=custom_style).ask()
        project_config["description"] = description

        project_config["features"] = []

        if questionary.confirm("Would you like to customize the features?", default=False, style=custom_style).ask():
            # Get all available feature choices
            feature_choices = get_feature_choices()

            # All features unchecked by default
            for choice in feature_choices:
                choice.checked = False

            # Let user modify selection
            selected_features = questionary.checkbox(
                "Select features to include:", choices=feature_choices, style=custom_style
            ).ask()

            if selected_features is not None:  # User didn't cancel
                # Configure detailed options for selected features
                feature_config = configure_features(selected_features)
                project_config["features"] = selected_features
                project_config["feature_config"] = feature_config

    # Configure AI provider if 'ai_provider' is in features
    final_features = project_config.get("features", [])
    if "ai_provider" in final_features:
        if quick:
            # Default to OpenAI in quick mode
            project_config["ai_provider_config"] = {"provider": "openai"}
        else:
            ai_provider_choice = questionary.select(
                "Please select an AI Provider:",
                choices=[
                    questionary.Choice("OpenAI", value="openai"),
                    questionary.Choice("Anthropic", value="anthropic"),
                    questionary.Choice("Ollama", value="ollama"),
                ],
                style=custom_style,
            ).ask()

            if ai_provider_choice:
                project_config["ai_provider_config"] = {"provider": ai_provider_choice}

    # Configure external services if 'services' is in features (Database, Cache only)
    if "services" in final_features:
        if quick:
            # Default to no external services in quick mode
            project_config["services"] = []
        else:
            service_choices = [
                questionary.Choice("Valkey", value="valkey"),
                questionary.Choice("Custom API", value="custom"),
            ]

            selected = questionary.checkbox(
                "Select external services:", choices=service_choices, style=custom_style
            ).ask()

            project_config["services"] = selected if selected else []

    # Use existing config if provided
    if config:
        project_config["base_config"] = Path(config)

    # Generate project
    click.echo(f"\n{click.style('Creating project...', fg='yellow')}")

    try:
        generator = ProjectGenerator(output_dir, project_config)
        generator.generate()

        # Initialize git repository unless --no-git flag is used
        if not no_git:
            click.echo(f"{click.style('Initializing git repository...', fg='yellow')}")
            if initialize_git_repo(output_dir):
                click.echo(f"{click.style('Git repository initialized', fg='green')}")
            else:
                click.echo(
                    f"{click.style('  Warning: Could not initialize git repository (git not found or failed)', fg='yellow')}"
                )

        click.echo(f"\n{click.style('✓ Project created successfully!', fg='green', bold=True)}")
        click.echo(f"\nLocation: {output_dir}")
        click.echo("\nNext steps:")
        click.echo(f"  1. cd {output_dir.name}")
        click.echo("  2. uv sync                    # Install dependencies")
        click.echo("  3. agentup agent serve        # Start development server")

    except Exception as e:
        click.echo(f"{click.style('✗ Error:', fg='red')} {str(e)}")
        return


def configure_features(features: list) -> dict[str, Any]:
    config = {}

    if "middleware" in features:
        middleware_choices = [
            questionary.Choice("Rate Limiting", value="rate_limit", checked=True),
            questionary.Choice("Caching", value="cache", checked=True),
            questionary.Choice("Retry Logic", value="retry"),
        ]

        selected = questionary.checkbox(
            "Select middleware to include:", choices=middleware_choices, style=custom_style
        ).ask()

        config["middleware"] = selected if selected else []

        # If cache is selected, ask for cache backend
        if "cache" in (selected or []):
            cache_backend_choice = questionary.select(
                "Select cache backend:",
                choices=[
                    questionary.Choice("Memory (development, fast)", value="memory"),
                    questionary.Choice("Valkey/Redis (production, persistent)", value="valkey"),
                ],
                style=custom_style,
            ).ask()

            config["cache_backend"] = cache_backend_choice

    if "state_management" in features:
        state_backend_choice = questionary.select(
            "Select state management backend:",
            choices=[
                questionary.Choice("Valkey/Redis (production, distributed)", value="valkey"),
                questionary.Choice("Memory (development, non-persistent)", value="memory"),
                questionary.Choice("File (local development, persistent)", value="file"),
            ],
            style=custom_style,
        ).ask()

        config["state_backend"] = state_backend_choice

    if "auth" in features:
        auth_choice = questionary.select(
            "Select authentication method:",
            choices=[
                questionary.Choice("API Key (simple, but less secure)", value="api_key"),
                questionary.Choice("JWT Bearer", value="jwt"),
                questionary.Choice("OAuth2 (with provider integration)", value="oauth2"),
            ],
            style=custom_style,
        ).ask()

        config["auth"] = auth_choice

        # If OAuth2 is selected, ask for provider
        if auth_choice == "oauth2":
            oauth2_provider = questionary.select(
                "Select OAuth2 provider:",
                choices=[
                    questionary.Choice("GitHub (introspection-based)", value="github"),
                    questionary.Choice("Google (JWT-based)", value="google"),
                    questionary.Choice("Keycloak (JWT-based)", value="keycloak"),
                    questionary.Choice("Generic (configurable)", value="generic"),
                ],
                style=custom_style,
            ).ask()

            config["oauth2_provider"] = oauth2_provider

    if "push_notifications" in features:
        push_backend_choice = questionary.select(
            "Select push notifications backend:",
            choices=[
                questionary.Choice("Memory (development, non-persistent)", value="memory"),
                questionary.Choice("Valkey/Redis (production, persistent)", value="valkey"),
            ],
            style=custom_style,
        ).ask()

        config["push_backend"] = push_backend_choice

        validate_urls = questionary.confirm(
            "Enable webhook URL validation?", default=push_backend_choice == "valkey", style=custom_style
        ).ask()

        config["push_validate_urls"] = validate_urls

    if "development" in features:
        dev_enabled = questionary.confirm(
            "Enable development features? (filesystem plugins, debug mode)", default=False, style=custom_style
        ).ask()

        config["development_enabled"] = dev_enabled

        if dev_enabled:
            filesystem_plugins = questionary.confirm(
                "Enable filesystem plugin loading? (allows loading plugins from directories)",
                default=True,
                style=custom_style,
            ).ask()

            config["filesystem_plugins_enabled"] = filesystem_plugins

            if filesystem_plugins:
                plugin_dir = questionary.text(
                    "Plugin directory path:", default="~/.agentup/plugins", style=custom_style
                ).ask()

                config["plugin_directory"] = plugin_dir

    if "mcp" in features:
        # MCP (Model Context Protocol) configuration
        # Configure filesystem server path
        # Bandit, marking as nosec, because there is unlikely to be a safer default path for a user to select
        fs_path = questionary.text("Filesystem server root path:", default="/tmp", style=custom_style).ask()  # nosec
        config["mcp_filesystem_path"] = fs_path

    if "deployment" in features:
        # Docker configuration
        docker_enabled = questionary.confirm(
            "Generate Docker files? (Dockerfile, docker-compose.yml)", default=True, style=custom_style
        ).ask()

        config["docker_enabled"] = docker_enabled

        if docker_enabled:
            docker_registry = questionary.text("Docker registry (optional):", default="", style=custom_style).ask()

            config["docker_registry"] = docker_registry if docker_registry else None

        # Helm configuration
        helm_enabled = questionary.confirm(
            "Generate Helm charts for Kubernetes deployment?", default=True, style=custom_style
        ).ask()

        config["helm_enabled"] = helm_enabled

        if helm_enabled:
            helm_namespace = questionary.text(
                "Default Kubernetes namespace:", default="default", style=custom_style
            ).ask()

            config["helm_namespace"] = helm_namespace

    return config
