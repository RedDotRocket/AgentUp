import asyncio
from pathlib import Path
from typing import Any

import click
import httpx
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

    # Initial setup
    output_path: Path | None
    if config:
        project_config = {"base_config": Path(config)}
        output_path = Path(output_dir) if output_dir else Path.cwd() / "new_agent"
        if not name:
            click.echo("Warning: Agent name will be read from config file.", err=True)
    else:
        project_config, output_path = _prompt_for_basic_config(name, version, quick, output_dir)
        if output_path is None:
            return

    # Configuration
    if not config:
        _prompt_for_features(project_config, quick, no_git)

    # Generate the project
    click.echo(f"\n{click.style('Creating project...', fg='yellow')}")
    try:
        generator = ProjectGenerator(output_path, project_config)
        generator.generate()

        _handle_git_initialization(output_path, no_git)

        print_success_footer(
            "✓ Project created successfully!",
            location=str(output_path),
            docs_url="https://docs.agentup.dev/getting-started/first-agent/",
        )
        click.secho("\nNext steps:", fg="white", bold=True)
        click.echo(f"  1. cd {output_path.name}")
        click.echo("  2. uv sync                 # Install dependencies")
        click.echo("  3. uv add <plugin_name>    # Add AgentUp plugins")
        click.echo("  4. agentup plugin sync     # Sync plugins with config")
        click.echo("  5. agentup run             # Start development server")

    except Exception as e:
        print_error(str(e))
        return


# Helper functions
def _prompt_for_basic_config(
    name: str | None, version: str | None, quick: bool, output_dir: str | None
) -> tuple[dict[str, Any], Path | None]:
    """Prompts for basic project configuration and returns the config and output path."""
    project_config: dict[str, Any] = {}

    if not name:
        name = questionary.text("Agent name:", style=custom_style, validate=lambda x: len(x.strip()) > 0).ask()
        if not name:
            click.echo("Cancelled.")
            return {}, None
    project_config["name"] = name

    output_path: Path
    if not output_dir:
        # Normalize the name for directory: lowercase and replace spaces with underscores
        dir_name = name.lower().replace(" ", "_")
        output_path = Path.cwd() / dir_name
    else:
        output_path = Path(output_dir)

    if output_path.exists():
        if quick:
            # In quick mode, automatically overwrite if directory exists
            click.echo(f"Directory {output_path} already exists. Continuing in quick mode...")
        elif not questionary.confirm(
            f"Directory {output_path} already exists. Continue?", default=False, style=custom_style
        ).ask():
            click.echo("Cancelled.")
            return {}, None

    if quick:
        project_config["description"] = f"AI Agent {name} Project."
        project_config["version"] = version or "0.0.1"
    else:
        description = questionary.text("Description:", default=f"AI Agent {name} Project.", style=custom_style).ask()
        project_config["description"] = description
        if not version:
            version = questionary.text("Version:", default="0.0.1", style=custom_style).ask()
        project_config["version"] = version

    return project_config, output_path


def _prompt_for_features(project_config: dict[str, Any], quick: bool, no_git: bool):
    """Prompts for and configures advanced features."""
    if not no_git:
        project_config["author_info"] = get_git_author_info()

    # Agent type selection (always prompt, even in quick mode)
    agent_type_choices = [
        questionary.Choice("Reactive (single-shot request/response)", value="reactive"),
        questionary.Choice("Iterative (self-directed multi-turn loops)", value="iterative"),
    ]

    selected_agent_type = questionary.select(
        "Select agent execution type:", choices=agent_type_choices, default="reactive", style=custom_style
    ).ask()

    project_config["agent_type"] = selected_agent_type

    # Configure iterative-specific settings if selected
    if selected_agent_type == "iterative":
        max_iterations = questionary.text(
            "Maximum iterations per task (1-100):", default="10", style=custom_style
        ).ask()

        try:
            max_iterations = int(max_iterations)
            if not 1 <= max_iterations <= 100:
                max_iterations = 10
        except ValueError:
            max_iterations = 10

        project_config["max_iterations"] = max_iterations

        memory_enabled = questionary.confirm(
            "Enable memory for learning and context preservation?", default=True, style=custom_style
        ).ask()

        project_config["memory_enabled"] = memory_enabled

    if quick:
        default_features = [choice.value for choice in get_feature_choices() if choice.checked]
        project_config["features"] = default_features
        project_config["feature_config"] = {}
        project_config["ai_provider_config"] = {"provider": "openai"}
        project_config["services"] = []
        return

    # Standard mode
    if questionary.confirm("Would you like to customize the features?", default=False, style=custom_style).ask():
        feature_choices = get_feature_choices()
        for choice in feature_choices:
            choice.checked = False

        selected_features = questionary.checkbox(
            "Select features to include:", choices=feature_choices, style=custom_style
        ).ask()
        if selected_features is not None:
            feature_config = configure_features(selected_features)
            project_config["features"] = selected_features
            project_config["feature_config"] = feature_config

    # Configure AI provider
    ai_config = get_ai_provider_config(custom_style)
    if ai_config:
        project_config["ai_provider_config"] = ai_config

    # Configure external services
    if "services" in project_config.get("features", []):
        print_header("External Services Configuration")
        service_choices = [
            questionary.Choice("Valkey", value="valkey"),
            questionary.Choice("Custom API", value="custom"),
        ]
        selected = questionary.checkbox("Select external services:", choices=service_choices, style=custom_style).ask()
        project_config["services"] = selected if selected else []


def get_ai_provider_config(custom_style) -> dict[str, Any] | None:
    """Configure AI provider settings interactively."""

    PROVIDER_CHOICES = [
        questionary.Choice("OpenAI", value="openai"),
        questionary.Choice("Anthropic", value="anthropic"),
        questionary.Choice("Ollama", value="ollama"),
    ]

    ai_provider = questionary.select(
        "Please select an AI Provider:",
        choices=PROVIDER_CHOICES,
        style=custom_style,
    ).ask()

    if not ai_provider:
        return None

    config = {"provider": ai_provider}

    # Handle Ollama model selection first
    if ai_provider == "ollama":
        model = _select_ollama_model(custom_style)
        if not model:
            return None
        config["model"] = model

    # Ask about streaming for all providers
    config["stream"] = questionary.confirm("Enable streaming responses?", default=True, style=custom_style).ask()

    return config


def _select_ollama_model(custom_style) -> str | None:
    """Get Ollama model selection from user."""
    models = asyncio.run(get_ollama_models())

    if not models:
        click.echo("No models found locally. Defaulting to 'llama3:latest'.", err=True)
        return "llama3"

    selected_model = questionary.select(
        "Please select an Ollama model:",
        choices=models,
        style=custom_style,
    ).ask()

    # questionary.ask() can return None if cancelled
    return selected_model if selected_model is not None else None


def _handle_git_initialization(output_dir: Path, no_git: bool):
    """Initializes a Git repository in the output directory."""
    if not no_git:
        click.echo(f"{click.style('Initializing git repository...', fg='yellow')}")
        success, error = initialize_git_repo(output_dir)
        if success:
            click.echo(f"{click.style('Git repository initialized', fg='green')}")
        else:
            click.echo(f"{click.style(f'Warning: Could not initialize git repository: {error}', fg='yellow')}")


async def get_ollama_models() -> list[str]:
    """Pings the local Ollama API and returns a list of available model names.

    This function is a standalone helper that doesn't rely on a class instance.
    """
    import os

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(base_url=base_url) as client:
            response = await client.get("/api/tags", timeout=5.0)
            response.raise_for_status()  # Raise an exception for bad status codes

            data = response.json()
            models = data.get("models", [])
            return [model["name"] for model in models]

    except httpx.HTTPError as e:
        click.echo(f"Warning: Could not connect to Ollama or retrieve models. Error: {e}", err=True)
        return []
    except KeyError:
        click.echo("Warning: Ollama API response is missing the 'models' key.", err=True)
        return []


def configure_features(features: list) -> dict[str, Any]:
    config = {}

    if "middleware" in features:
        print_header("Middleware Configuration")
        middleware_choices = [
            questionary.Choice("Rate Limiting", value="rate_limit", checked=True),
            questionary.Choice("Caching", value="cache", checked=True),
            questionary.Choice("Retry Logic", value="retry"),
        ]
        selected = questionary.checkbox(
            "Select middleware to include:", choices=middleware_choices, style=custom_style
        ).ask()
        config["middleware"] = selected if selected else []
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
        print_header("State Management Configuration")
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
        print_header("Authentication Configuration")
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
        print_header("Push Notifications Configuration")
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
        print_header("Development Features Configuration")
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
        print_header("Deployment Configuration", "Configure deployment options for your agent")
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
        helm_enabled = questionary.confirm(
            "Generate Helm charts for Kubernetes deployment?", default=True, style=custom_style
        ).ask()
        config["helm_enabled"] = helm_enabled
        if helm_enabled:
            # Helm configuration
            helm_namespace = questionary.text(
                "Default Kubernetes namespace:", default="default", style=custom_style
            ).ask()
            config["helm_namespace"] = helm_namespace
    return config
