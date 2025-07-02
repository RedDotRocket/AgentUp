import subprocess  # nosec
from pathlib import Path
from typing import Any

import click
import questionary
from questionary import Style

from ...generator import ProjectGenerator
from ...templates import (
    get_feature_choices,
    get_template_choices,
    get_template_features,
)


def initialize_git_repo(project_path: Path) -> bool:
    """Initialize a git repository in the project directory.

    Returns:
        bool: True if git initialization was successful, False otherwise.

    Bandit:
        This function uses subprocess to run git commands, which is generally safe
        as long as the entry point is the CLI command and the project_path is controlled.
    """
    try:
        # Check if git is available
        subprocess.run(["git", "--version"], check=True, capture_output=True)  # nosec

        # Initialize git repository
        subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)  # nosec

        # Add all files to git
        subprocess.run(["git", "add", "."], cwd=project_path, check=True, capture_output=True)  # nosec

        # Create initial commit
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
@click.option("--template", "-t", help="Project template to use")
@click.option(
    "--quick", "-q", is_flag=True, help="Quick setup with standard features (middleware, services, auth, testing)"
)
@click.option("--minimal", is_flag=True, help="Create with minimal features (basic handlers only)")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Use existing agent_config.yaml as template")
@click.option("--no-git", is_flag=True, help="Skip git repository initialization")
def create_agent(
    name: str | None,
    template: str | None,
    quick: bool,
    minimal: bool,
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
        agentup agent create --quick my-agent   # Quick setup with standard features
        agentup agent create --minimal my-agent # Minimal setup (basic handlers only)
        agentup agent create --no-git my-agent  # Skip git initialization
        agentup agent create --template chatbot my-chatbot
    """
    click.echo(click.style("-" * 40, fg="white", dim=True))
    click.echo(click.style("Create your AI agent:", fg="white", dim=True))
    click.echo(click.style("-" * 40, fg="white", dim=True))

    # Get project configuration
    project_config = {}

    # Project name
    if not name:
        name = questionary.text("Agent name:", style=custom_style, validate=lambda x: len(x.strip()) > 0).ask()
        if not name:
            click.echo("Cancelled.")
            return

    project_config["name"] = name

    # Output directory
    if not output_dir:
        # Normalize the name for directory: lowercase and replace spaces with underscores
        dir_name = name.lower().replace(" ", "_")
        output_dir = Path.cwd() / dir_name
    else:
        output_dir = Path(output_dir)

    # Check if directory exists
    if output_dir.exists():
        if not questionary.confirm(
            f"Directory {output_dir} already exists. Continue?", default=False, style=custom_style
        ).ask():
            click.echo("Cancelled.")
            return

    # Quick mode - use specified template or default to standard
    if quick:
        selected_template = template or "standard"
        project_config["template"] = selected_template
        project_config["description"] = f"AI Agent {name} Project."
        # Use template's features
        template_features = get_template_features()
        project_config["features"] = template_features.get(selected_template, {}).get("features", [])
    # Minimal mode - use minimal template with no features
    elif minimal:
        project_config["template"] = "minimal"
        project_config["description"] = f"AI Agent {name} Project."
        project_config["features"] = []
    else:
        # Project description
        description = questionary.text("Description:", default=f"AI Agent {name} Project.", style=custom_style).ask()
        project_config["description"] = description

        # Template selection (interactive mode when no template is specified)
        if not template:
            template_choices = get_template_choices()
            template = questionary.select("Select template:", choices=template_choices, style=custom_style).ask()
            if not template:
                click.echo("Cancelled.")
                return

        project_config["template"] = template

        # Use template's default features
        template_features = get_template_features()
        project_config["features"] = template_features.get(template, {}).get("features", [])

        # Ask if user wants to customize features
        if questionary.confirm("Would you like to customize the features?", default=False, style=custom_style).ask():
            # Get all available feature choices
            feature_choices = get_feature_choices()

            # Mark current template features as checked
            for choice in feature_choices:
                if choice.value in project_config["features"]:
                    choice.checked = True
                else:
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
        service_choices = [
            questionary.Choice("PostgreSQL", value="postgres"),
            questionary.Choice("Valkey", value="valkey"),
            questionary.Choice("Custom API", value="custom"),
        ]

        selected = questionary.checkbox("Select external services:", choices=service_choices, style=custom_style).ask()

        project_config["services"] = selected if selected else []

    # Use existing config if provided
    if config:
        project_config["base_config"] = Path(config)

    # Generate project
    click.echo(f"\n{click.style('📁 Creating project...', fg='yellow')}")

    try:
        generator = ProjectGenerator(output_dir, project_config)
        generator.generate()

        # Initialize git repository unless --no-git flag is used
        if not no_git:
            click.echo(f"{click.style('📝 Initializing git repository...', fg='yellow')}")
            if initialize_git_repo(output_dir):
                click.echo(f"{click.style('✅ Git repository initialized', fg='green')}")
            else:
                click.echo(
                    f"{click.style('⚠️  Warning: Could not initialize git repository (git not found or failed)', fg='yellow')}"
                )

        click.echo(f"\n{click.style('✅ Project created successfully!', fg='green', bold=True)}")
        click.echo(f"\nLocation: {output_dir}")
        click.echo("\nNext steps:")
        click.echo(f"  1. cd {output_dir.name}")
        click.echo("  2. uv sync                    # Install dependencies")
        click.echo("  3. agentup dev                # Start development server")

    except Exception as e:
        click.echo(f"{click.style('❌ Error:', fg='red')} {str(e)}")
        return


def configure_features(features: list) -> dict[str, Any]:
    """Configure selected features with additional options."""
    config = {}

    if "middleware" in features:
        middleware_choices = [
            questionary.Choice("Rate Limiting", value="rate_limit", checked=True),
            questionary.Choice("Caching", value="cache", checked=True),
            questionary.Choice("Input Validation", value="validation"),
            questionary.Choice("Retry Logic", value="retry"),
            questionary.Choice("Logging", value="logging", checked=True),
        ]

        selected = questionary.checkbox(
            "Select middleware to include:", choices=middleware_choices, style=custom_style
        ).ask()

        config["middleware"] = selected if selected else []

    if "auth" in features:
        auth_choice = questionary.select(
            "Select authentication method:",
            choices=[
                questionary.Choice("API Key", value="api_key"),
                questionary.Choice("JWT", value="jwt"),
                questionary.Choice("OAuth2", value="oauth2"),
            ],
            style=custom_style,
        ).ask()

        config["auth"] = auth_choice

    return config
