import re
from pathlib import Path
from typing import Any

import click
import questionary
import yaml
from jinja2 import Environment, FileSystemLoader
from questionary import Style

# Custom style for interactive prompts
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
        ("error", "fg:#cc6666 bold"),
    ]
)


@click.command()
@click.option("--name", "-n", help="Skill name")
@click.option("--id", "-i", help="Skill ID")
@click.option("--description", "-d", help="Skill description")
@click.option("--input-mode", help="Input mode (text/multimodal)")
@click.option("--output-mode", help="Output mode (text/multimodal)")
def add_skill(
    name: str | None, id: str | None, description: str | None, input_mode: str | None, output_mode: str | None
):
    """
    Create a new skill to your AgentUp Agent.
    """
    # Check if we're in an agent project
    if not Path("agent_config.yaml").exists():
        click.echo(click.style("Error: No agent_config.yaml found!", fg="red"))
        click.echo("Are you in an agent project directory?")
        return

    click.echo(click.style("AgentUp - Interactive Skill Generator", fg="bright_blue", bold=True))
    click.echo("Let's add a new skill to your agent.\n")

    # Collect skill information
    skill_data = collect_skill_info(name, id, description, input_mode, output_mode)
    if not skill_data:
        click.echo("Cancelled.")
        return

    # Add to configuration
    if not add_skill_to_config(skill_data):
        return

    # Generate handler code
    if not add_skill_handler(skill_data):
        return

    # Success message
    click.echo(f"\n{click.style('Skill added successfully!', fg='green', bold=True)}")
    click.echo(f"\nSkill ID: {skill_data['skill_id']}")
    click.echo("\nNext steps:")
    click.echo(f"1. Implement the handler in src/agent/handlers/{skill_data['skill_id']}_handler.py")


def collect_skill_info(
    name: str | None, id: str | None, description: str | None, input_mode: str | None, output_mode: str | None
) -> dict[str, Any]:
    """Collect skill information interactively."""
    skill_data = {}

    # Basic information
    if not name:
        name = questionary.text("Skill name:", validate=lambda x: len(x.strip()) > 0, style=custom_style).ask()
        if not name:
            return {}

    skill_data["name"] = name

    # Generate skill ID from name if not provided
    if not id:
        default_id = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        default_id = re.sub(r"_+", "_", default_id).strip("_")

        id = questionary.text(
            "Skill ID:",
            default=default_id,
            validate=lambda x: re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", x) is not None,
            style=custom_style,
        ).ask()
        if not id:
            return {}

    skill_data["skill_id"] = id

    # Description
    if not description:
        description = questionary.text("Description:", default=f"Handle {name} requests", style=custom_style).ask()

    skill_data["description"] = description

    # Input/Output modes
    if not input_mode:
        input_mode = questionary.select(
            "Input mode:", choices=["text", "multimodal"], default="text", style=custom_style
        ).ask()

    skill_data["input_mode"] = input_mode

    if not output_mode:
        output_mode = questionary.select(
            "Output mode:", choices=["text", "multimodal"], default="text", style=custom_style
        ).ask()

    skill_data["output_mode"] = output_mode

    # Routing mode selection - this is now a core configuration step
    routing_mode = questionary.select(
        "Routing mode:",
        choices=[
            questionary.Choice("AI (intelligent routing using LLM)", value="ai"),
            questionary.Choice("Direct (keyword/pattern matching)", value="direct"),
        ],
        default="ai",
        style=custom_style,
    ).ask()

    skill_data["routing_mode"] = routing_mode

    # Advanced options
    if questionary.confirm("Configure advanced options?", default=False, style=custom_style).ask():
        skill_data.update(collect_advanced_options())

    # Routing configuration based on routing mode
    if routing_mode == "direct":
        if questionary.confirm("Configure routing rules for this skill?", default=True, style=custom_style).ask():
            skill_data.update(collect_routing_config(skill_data))
    else:
        # AI routing mode - no keywords or patterns needed
        click.echo(f"\n{click.style('AI Routing Mode', fg='cyan', bold=True)}")
        click.echo("Using AI routing - no keywords or patterns needed.")

    return skill_data


def collect_advanced_options() -> dict[str, Any]:
    """Collect advanced skill options."""
    advanced = {}

    # External API configuration
    if questionary.confirm("Does this skill use external APIs?", default=False, style=custom_style).ask():
        api_config = {}
        api_config["service"] = questionary.text("Service name (e.g., openai, weather_api):", style=custom_style).ask()

        api_config["requires_key"] = questionary.confirm("Requires API key?", default=True, style=custom_style).ask()

        if api_config["requires_key"]:
            api_config["env_var"] = questionary.text(
                "Environment variable name:", default=f"{api_config['service'].upper()}_API_KEY", style=custom_style
            ).ask()

        advanced["api_config"] = api_config

    # Middleware configuration
    if questionary.confirm("Configure middleware?", default=False, style=custom_style).ask():
        middleware = []

        middleware_options = [
            questionary.Choice("Rate limiting", value="rate_limit"),
            questionary.Choice("Caching", value="cache"),
            questionary.Choice("Input validation", value="validation"),
            questionary.Choice("Retry logic", value="retry"),
            questionary.Choice("Logging", value="logging"),
        ]

        selected = questionary.checkbox("Select middleware:", choices=middleware_options, style=custom_style).ask()

        for mw_type in selected:
            mw_config = {"type": mw_type}

            if mw_type == "rate_limit":
                mw_config["requests_per_minute"] = questionary.text(
                    "Requests per minute:", default="60", validate=lambda x: x.isdigit(), style=custom_style
                ).ask()
            elif mw_type == "cache":
                mw_config["ttl"] = questionary.text(
                    "Cache TTL (seconds):", default="300", validate=lambda x: x.isdigit(), style=custom_style
                ).ask()
            elif mw_type == "retry":
                mw_config["max_retries"] = questionary.text(
                    "Max retries:", default="3", validate=lambda x: x.isdigit(), style=custom_style
                ).ask()

            middleware.append(mw_config)

        advanced["middleware"] = middleware

    # State management
    if questionary.confirm("Enable state management?", default=False, style=custom_style).ask():
        advanced["stateful"] = True
        advanced["storage"] = questionary.select(
            "Storage backend:", choices=["file", "memory", "valkey"], default="file", style=custom_style
        ).ask()

    return advanced


def collect_routing_config(skill_data: dict[str, Any]) -> dict[str, Any]:
    """Collect routing configuration for the skill."""
    routing_config = {}

    # Keywords for routing
    default_keywords = [skill_data["skill_id"].replace("_", " "), skill_data["skill_id"], skill_data["name"].lower()]

    # Remove duplicates while preserving order
    seen = set()
    default_keywords = [x for x in default_keywords if not (x in seen or seen.add(x))]

    click.echo(f"\n{click.style('Routing Configuration', fg='cyan', bold=True)}")
    click.echo("Configure how users will trigger this skill.")

    # Keywords
    keywords_input = questionary.text(
        "Keywords (comma-separated):",
        default=", ".join(default_keywords),
        instruction="Words that will trigger this skill",
        style=custom_style,
    ).ask()

    if keywords_input:
        keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
        routing_config["keywords"] = keywords

    # Advanced routing patterns
    if questionary.confirm("Add regex patterns for advanced routing?", default=False, style=custom_style).ask():
        patterns = []

        while True:
            pattern = questionary.text(
                "Regex pattern (or press Enter to finish):",
                instruction="e.g., '^(process|analyze).*' to match text starting with 'process' or 'analyze'",
                style=custom_style,
            ).ask()

            if not pattern:
                break

            patterns.append(pattern)

            if not questionary.confirm("Add another pattern?", default=False, style=custom_style).ask():
                break

        if patterns:
            routing_config["patterns"] = patterns

    # Priority
    priority = questionary.select(
        "Routing priority:",
        choices=[
            questionary.Choice("High (checked first)", value="high"),
            questionary.Choice("Normal (default order)", value="normal"),
            questionary.Choice("Low (checked last)", value="low"),
        ],
        default="normal",
        style=custom_style,
    ).ask()

    routing_config["priority"] = priority

    # Set as default skill
    if questionary.confirm(
        "Make this the default skill (fallback when no other rules match)?", default=False, style=custom_style
    ).ask():
        routing_config["is_default"] = True

    return {"routing": routing_config}


def ensure_services_import_available() -> bool:
    """Ensure handlers.py has services import when external APIs are used."""
    handlers_path = Path("src/agent/handlers/handlers.py")

    if not handlers_path.exists():
        click.echo(f"{click.style('❌ Error:', fg='red')} handlers.py not found!")
        return False

    try:
        handlers_content = handlers_path.read_text()

        # Check if services import already exists
        if "from .services import get_services" not in handlers_content:
            click.echo(f"{click.style('📝 Adding services import to handlers.py...', fg='blue')}")

            # Find where to insert the import (after existing imports)
            lines = handlers_content.split("\n")
            insert_line = 0

            # Find the best place to insert (after existing imports)
            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    insert_line = i + 1
                elif line.strip() == "" and insert_line > 0:
                    # Found empty line after imports
                    break

            # Insert services import
            services_import = "\n# Import services for external API integration\nfrom .services import get_services"

            if insert_line > 0:
                lines.insert(insert_line, services_import)
            else:
                # Fallback: add after docstring
                for i, line in enumerate(lines):
                    if line.strip().endswith('"""') and i > 0:
                        lines.insert(i + 1, services_import)
                        break

            # Write back the updated content
            handlers_path.write_text("\n".join(lines))

            click.echo(f"{click.style('✓', fg='green')} Added services import to handlers.py")

        return True

    except Exception as e:
        click.echo(f"{click.style('❌ Error updating handlers.py:', fg='red')} {str(e)}")
        return False


def ensure_function_dispatcher_import_available() -> bool:
    """Ensure handlers.py has function_dispatcher import when LLM features are used."""
    handlers_path = Path("src/agent/handlers/handlers.py")

    if not handlers_path.exists():
        click.echo(f"{click.style('❌ Error:', fg='red')} handlers.py not found!")
        return False

    try:
        handlers_content = handlers_path.read_text()

        # Check if function_dispatcher import already exists
        if "from .function_dispatcher import ai_function" not in handlers_content:
            click.echo(f"{click.style('📝 Adding Agent Exectutor import to handlers.py...', fg='blue')}")

            # Find where to insert the import (after existing imports)
            lines = handlers_content.split("\n")
            insert_line = 0

            # Find the best place to insert (after existing imports)
            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    insert_line = i + 1
                elif line.strip() == "" and insert_line > 0:
                    # Found empty line after imports
                    break

            # Insert function_dispatcher import
            ai_import = (
                "\n# Import AI function decorator for LLM-powered agents\nfrom .function_dispatcher import ai_function"
            )

            if insert_line > 0:
                lines.insert(insert_line, ai_import)
            else:
                # Fallback: add after docstring
                for i, line in enumerate(lines):
                    if line.strip().endswith('"""') and i > 0:
                        lines.insert(i + 1, ai_import)
                        break

            # Write back the updated content
            handlers_path.write_text("\n".join(lines))

            click.echo(f"{click.style('✓', fg='green')} Added Agent Executor import to handlers.py")

        return True

    except Exception as e:
        click.echo(f"{click.style('❌ Error updating handlers.py:', fg='red')} {str(e)}")
        return False


def ensure_api_imports_available(skill_data: dict[str, Any]) -> bool:
    """Ensure required imports for API integration are available at the top of handlers.py."""
    handlers_path = Path("src/agent/handlers/handlers.py")

    if not handlers_path.exists():
        click.echo(f"{click.style('❌ Error:', fg='red')} handlers.py not found!")
        return False

    try:
        handlers_content = handlers_path.read_text()

        # Check if API imports already exist
        needs_imports = []
        if skill_data.get("api_config"):
            if "import os" not in handlers_content:
                needs_imports.extend(["import os"])
            if "import logging" not in handlers_content:
                needs_imports.extend(["import logging"])
            if "import httpx" not in handlers_content:
                needs_imports.extend(["import httpx"])
            if "logger = logging.getLogger(__name__)" not in handlers_content:
                needs_imports.extend(["", "logger = logging.getLogger(__name__)"])

        if needs_imports:
            click.echo(f"{click.style('📝 Adding API imports to handlers.py...', fg='blue')}")

            # Find where to insert the imports (after existing imports)
            lines = handlers_content.split("\n")
            insert_line = 0

            # Find the best place to insert (after existing imports)
            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    insert_line = i + 1
                elif line.strip() == "" and insert_line > 0:
                    # Found empty line after imports
                    break

            # Insert API imports
            api_imports = "\n# Required imports for API integration\n" + "\n".join(needs_imports)

            if insert_line > 0:
                lines.insert(insert_line, api_imports)
            else:
                # Fallback: add after docstring
                for i, line in enumerate(lines):
                    if line.strip().endswith('"""') and i > 0:
                        lines.insert(i + 1, api_imports)
                        break

            # Write back the updated content
            handlers_path.write_text("\n".join(lines))

            click.echo(f"{click.style('✓', fg='green')} Added API imports to handlers.py")

        return True

    except Exception as e:
        click.echo(f"{click.style('❌ Error updating handlers.py:', fg='red')} {str(e)}")
        return False


def ensure_api_dependencies() -> bool:
    """Ensure required dependencies for API integration are available."""
    try:
        # Check if pyproject.toml exists and has httpx
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            if "httpx" in content:
                return True

        # Check if httpx is importable
        try:
            import httpx  # noqa: F401

            return True
        except ImportError:
            return False

    except Exception:
        return False


def ensure_middleware_available() -> bool:
    """Ensure middleware.py exists and handlers.py has middleware imports."""
    middleware_path = Path("src/agent/middleware.py")
    handlers_path = Path("src/agent/handlers/handlers.py")

    # Check if middleware.py exists
    if not middleware_path.exists():
        click.echo(f"{click.style('📁 Creating middleware.py...', fg='blue')}")

        # Get template directory (absolute path to handle working directory issues)
        template_dir = Path(__file__).parent.parent.parent / "templates"
        if not template_dir.exists():
            click.echo(f"{click.style('❌ Error:', fg='red')} Template directory not found!")
            return False

        # Load and render middleware template
        try:
            env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
            template = env.get_template("middleware.py.j2")

            # Render with basic context (no specific project variables needed)
            content = template.render(project_name="Current Project", project_name_snake="current_project")

            # Create middleware.py
            middleware_path.parent.mkdir(parents=True, exist_ok=True)
            middleware_path.write_text(content)

            click.echo(f"{click.style('✓', fg='green')} Created src/agent/middleware.py")

        except Exception as e:
            click.echo(f"{click.style('❌ Error creating middleware.py:', fg='red')} {str(e)}")
            return False

    # Check if handlers.py has middleware imports
    try:
        handlers_content = handlers_path.read_text()

        # Check if middleware import already exists
        if "from .middleware import" not in handlers_content:
            click.echo(f"{click.style('📝 Adding middleware imports to handlers.py...', fg='blue')}")

            # Find the imports section (after the docstring and existing imports)
            lines = handlers_content.split("\n")
            insert_line = 0

            # Find where to insert the import (after existing imports)
            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    insert_line = i + 1
                elif line.strip() == "" and insert_line > 0:
                    # Found empty line after imports
                    break

            # Insert middleware import
            middleware_import = "\n# Import middleware decorators\nfrom .middleware import cached, rate_limited, timed, logged, retryable"

            if insert_line > 0:
                lines.insert(insert_line, middleware_import)
            else:
                # Fallback: add after docstring
                for i, line in enumerate(lines):
                    if line.strip().endswith('"""') and i > 0:
                        lines.insert(i + 1, middleware_import)
                        break

            # Write back to file
            updated_content = "\n".join(lines)
            handlers_path.write_text(updated_content)

            click.echo(f"{click.style('✓', fg='green')} Added middleware imports to handlers.py")

    except Exception as e:
        click.echo(f"{click.style('❌ Error updating handlers.py:', fg='red')} {str(e)}")
        return False

    return True


def add_skill_to_config(skill_data: dict[str, Any]) -> bool:
    """Add skill to agent_config.yaml."""
    try:
        # Load existing config
        with open("agent_config.yaml") as f:
            config = yaml.safe_load(f)

        # Migrate config if needed
        migrate_config_if_needed(config)

        # Create skill entry
        skill_entry = {
            "skill_id": skill_data["skill_id"],
            "name": skill_data["name"],
            "description": skill_data["description"],
            "input_mode": skill_data["input_mode"],
            "output_mode": skill_data["output_mode"],
        }

        # Add tags if available (used in @ai_function decorator)
        routing_data = skill_data.get("routing", {})
        if skill_data.get("routing_mode") == "direct":
            # Add default tags for direct routing skills
            skill_entry["tags"] = [skill_data["skill_id"], "direct", "keyword"]
        else:
            # Add default tags for AI routing skills
            skill_entry["tags"] = [skill_data["skill_id"], "ai", "assistant"]

        # Add routing configuration for direct routing skills only
        if skill_data.get("routing_mode") == "direct":
            if routing_data.get("keywords"):
                skill_entry["keywords"] = routing_data["keywords"]
            if routing_data.get("patterns"):
                skill_entry["patterns"] = routing_data["patterns"]

        # Add priority based on routing configuration
        priority_map = {"high": 10, "normal": 50, "low": 90}
        skill_entry["priority"] = priority_map.get(routing_data.get("priority", "normal"), 50)

        # Add middleware if configured
        if skill_data.get("middleware"):
            skill_entry["middleware"] = skill_data["middleware"]

        # Add to skills list
        if "skills" not in config:
            config["skills"] = []

        # Check if skill already exists
        for existing in config["skills"]:
            if existing.get("skill_id") == skill_data["skill_id"]:
                click.echo(
                    f"{click.style('⚠️  Warning:', fg='yellow')} Skill '{skill_data['skill_id']}' already exists!"
                )
                if not questionary.confirm("Overwrite?", default=False, style=custom_style).ask():
                    return False
                config["skills"].remove(existing)
                break

        config["skills"].append(skill_entry)

        # Clean up old routing configuration if it exists (migration to implicit routing)
        if "routing" in config:
            # Remove the old routing section as we now use implicit routing
            del config["routing"]

        # Write back to file
        with open("agent_config.yaml", "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        click.echo(f"{click.style('✓', fg='green')} Updated agent_config.yaml")
        if skill_data.get("routing_mode") == "direct":
            click.echo(f"{click.style('✓', fg='green')} Updated routing configuration")
        else:
            click.echo(f"{click.style('✓', fg='green')} Updated routing configuration")
        return True

    except Exception as e:
        click.echo(f"{click.style('❌ Error updating config:', fg='red')} {str(e)}")
        return False


def migrate_config_if_needed(config: dict[str, Any]):
    """Clean up old routing configuration for implicit routing migration."""
    if "routing" in config:
        click.echo(f"{click.style('🔄 Migrating to implicit routing configuration...', fg='blue')}")
        # Remove old routing section - we now use implicit routing based on keywords/patterns
        del config["routing"]
        click.echo(f"{click.style('✓', fg='green')} Migrated to implicit routing configuration")


def add_skill_handler(skill_data: dict[str, Any]) -> bool:
    """Create individual handler file for the skill."""
    handler_filename = f"{skill_data['skill_id']}_handler.py"
    handler_path = Path(f"src/agent/handlers/{handler_filename}")

    # Check if handler file already exists
    if handler_path.exists():
        click.echo(f"{click.style('Warning:', fg='yellow')} Handler file {handler_filename} already exists!")
        if not questionary.confirm("Overwrite?", default=False, style=custom_style).ask():
            return False

    # Check if middleware is needed and create if missing
    if skill_data.get("middleware"):
        if not ensure_middleware_available():
            return False

    # Ensure required dependencies for external API integration
    if skill_data.get("api_config") or skill_data.get("external_apis"):
        if not ensure_api_dependencies():
            click.echo(f"{click.style('Warning:', fg='yellow')} Could not verify httpx dependency")
            click.echo("Please run: uv add httpx")

    # Generate handler file code with selective imports
    handler_code = generate_handler_file_code(skill_data)

    try:
        # Write the new handler file
        handler_path.write_text(handler_code)
        click.echo(f"{click.style('✓', fg='green')} Created handler file: {handler_path}")
        return True

    except Exception as e:
        click.echo(f"{click.style('Error creating handler file:', fg='red')} {str(e)}")
        return False


def extract_middleware_imports(middleware_list: list[dict[str, Any]]) -> list[str]:
    """Extract middleware import names from middleware configuration."""
    imports = []
    for mw in middleware_list:
        mw_type = mw.get("type")
        if mw_type == "cache":
            imports.append("cached")
        elif mw_type == "rate_limit":
            imports.append("rate_limited")
        elif mw_type == "logging":
            imports.append("logged")
        elif mw_type == "timing":
            imports.append("timed")
        elif mw_type == "retry":
            imports.append("retryable")
    return list(set(imports))  # Remove duplicates


def generate_middleware_decorators(middleware_list: list[dict[str, Any]]) -> list[str]:
    """Generate middleware decorator strings from middleware configuration."""
    decorators = []
    for mw in middleware_list:
        mw_type = mw.get("type")
        if mw_type == "cache":
            ttl = mw.get("ttl", 300)
            decorators.append(f"@cached(ttl={ttl})")
        elif mw_type == "rate_limit":
            rpm = mw.get("requests_per_minute", 60)
            decorators.append(f"@rate_limited(requests_per_minute={rpm})")
        elif mw_type == "logging":
            decorators.append("@logged()")
        elif mw_type == "timing":
            decorators.append("@timed()")
        elif mw_type == "retry":
            max_retries = mw.get("max_retries", 3)
            delay = mw.get("delay", 1)
            decorators.append(f"@retryable(max_retries={max_retries}, delay={delay})")
    return decorators


def prepare_template_context(skill_data: dict[str, Any]) -> dict[str, Any]:
    """Prepare context variables for Jinja2 template."""
    context = {
        "skill_id": skill_data["skill_id"],
        "name": skill_data["name"],
        "description": skill_data["description"],
        "input_mode": skill_data["input_mode"],
        "output_mode": skill_data["output_mode"],
        "api_config": skill_data.get("api_config"),
        "external_apis": skill_data.get("external_apis"),
        "stateful": skill_data.get("stateful", False),
        "middleware": skill_data.get("middleware", []),
    }

    # Process middleware for template
    if context["middleware"]:
        context["middleware_imports"] = extract_middleware_imports(context["middleware"])
        context["middleware_decorators"] = generate_middleware_decorators(context["middleware"])
    else:
        context["middleware_imports"] = []
        context["middleware_decorators"] = []

    return context


def generate_handler_file_code(skill_data: dict[str, Any]) -> str:
    """Generate handler file using Jinja2 template."""
    from jinja2 import Environment, FileSystemLoader

    # Setup Jinja2 environment
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    jinja_env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True, trim_blocks=True, lstrip_blocks=True)

    # Load the template
    template = jinja_env.get_template("skill_handler.py.j2")

    # Prepare context for template
    context = prepare_template_context(skill_data)

    # Render the template
    return template.render(**context)
