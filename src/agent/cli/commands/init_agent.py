from pathlib import Path
from typing import Any

import click
import questionary

from agent.cli.style import custom_style, print_error, print_header, print_success_footer
from agent.generator import ProjectGenerator
from agent.templates import get_feature_choices
from agent.utils.git_utils import get_git_author_info, initialize_git_repo


@click.command()
@click.argument("name", required=False)
@click.argument("version", required=False)
@click.option("--quick", "-q", is_flag=True, help="Quick setup with minimal features (basic handlers only)")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Use existing agentup.yml as template")
@click.option("--no-git", is_flag=True, help="Skip git repository initialization")
def init_agent(
    name: str | None,
    version: str | None,
    quick: bool,
    output_dir: str | None,
    config: str | None,
    no_git: bool,
):
    """Initializes a new Agent project.

    By default, this will initialize a git repository in the project directory
    with an initial commit. Use --no-git to skip git initialization.
    """
    print_header("AgentUp Agent Creator", "Create your AI agent")

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
                f"Directory {output_dir} already exists. Continue?",
                default=False,
                style=custom_style,
            ).ask():
                click.echo("Cancelled.")
                return

    if quick:
        project_config["description"] = f"AI Agent {name} Project."
        project_config["version"] = version or "0.0.1"
        # Include default checked features in quick mode
        default_features = [choice.value for choice in get_feature_choices() if choice.checked]
        project_config["features"] = default_features
        project_config["feature_config"] = {}
    else:
        description = questionary.text("Description:", default=f"AI Agent {name} Project.", style=custom_style).ask()
        project_config["description"] = description

        project_config["features"] = []

        if not version:
            version = questionary.text("Version:", default="0.0.1", style=custom_style).ask()

        project_config["version"] = version

        if not no_git:
            project_config["author_info"] = get_git_author_info()

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
            success, error = initialize_git_repo(output_dir)
            if success:
                click.echo(f"{click.style('Git repository initialized', fg='green')}")
            else:
                click.echo(f"{click.style(f'  Warning: Could not initialize git repository: {error}', fg='yellow')}")

        print_success_footer(
            "✓ Project created successfully!",
            location=str(output_dir),
            docs_url="https://docs.agentup.dev/getting-started/first-agent/",
        )

        click.secho("\nNext steps:", fg="white", bold=True)
        click.echo(f"  1. cd {output_dir.name}")
        click.echo("  2. uv sync                # Install dependencies")
        click.echo("  3. uv add <plugin_name>   # Add AgentUp plugins")
        click.echo("  4. agentup plugin sync    # Sync plugins with config")
        click.echo("  5. agentup run            # Start development server")

    except Exception as e:
        print_error(str(e))
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
            "Enable webhook URL validation?",
            default=push_backend_choice == "valkey",
            style=custom_style,
        ).ask()

        config["push_validate_urls"] = validate_urls

    if "development" in features:
        dev_enabled = questionary.confirm(
            "Enable development features? (filesystem plugins, debug mode)",
            default=False,
            style=custom_style,
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
        fs_path = "/tmp"  # nosec
        config["mcp_filesystem_path"] = fs_path

    if "deployment" in features:
        # Docker configuration
        docker_enabled = questionary.confirm(
            "Generate Docker files? (Dockerfile, docker-compose.yml)",
            default=True,
            style=custom_style,
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
