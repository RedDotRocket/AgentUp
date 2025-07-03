import json
import shutil
import subprocess  # nosec
import sys
from pathlib import Path

import click
import questionary
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def plugin():
    """Manage AgentUp plugins - next-generation extensible skills."""
    pass


@plugin.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plugin information")
@click.option("--format", "-f", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_plugins(verbose: bool, format: str):
    """List all loaded plugins and their skills."""
    try:
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        plugins = manager.list_plugins()
        skills = manager.list_skills()

        if format == "json":
            output = {
                "plugins": [
                    {
                        "name": p.name,
                        "version": p.version,
                        "status": p.status,
                        "author": p.author,
                        "description": p.description,
                    }
                    for p in plugins
                ],
                "skills": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "version": s.version,
                        "plugin": manager.skill_to_plugin.get(s.id),
                        "capabilities": s.capabilities,
                    }
                    for s in skills
                ],
            }
            console.print_json(json.dumps(output, indent=2))
            return

        if format == "yaml":
            import yaml

            output = {
                "plugins": [
                    {
                        "name": p.name,
                        "version": p.version,
                        "status": p.status,
                        "author": p.author,
                        "description": p.description,
                    }
                    for p in plugins
                ],
                "skills": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "version": s.version,
                        "plugin": manager.skill_to_plugin.get(s.id),
                        "capabilities": s.capabilities,
                    }
                    for s in skills
                ],
            }
            console.print(yaml.dump(output, default_flow_style=False))
            return

        # Table format (default)
        if not plugins:
            console.print("[yellow]No plugins loaded.[/yellow]")
            console.print("\nTo create a plugin: [cyan]agentup plugin create[/cyan]")
            console.print("To install from registry: [cyan]agentup plugin install <name>[/cyan]")
            return

        # Plugins table
        plugin_table = Table(title="Loaded Plugins", box=box.ROUNDED, title_style="bold cyan")
        plugin_table.add_column("Plugin", style="cyan")
        plugin_table.add_column("Version", style="green", justify="center")
        plugin_table.add_column("Status", style="blue", justify="center")
        plugin_table.add_column("Skills", style="yellow", justify="center")

        if verbose:
            plugin_table.add_column("Source", style="dim")
            plugin_table.add_column("Author", style="white")

        for plugin in plugins:
            # Count skills from this plugin
            skill_count = sum(1 for sid, pid in manager.skill_to_plugin.items() if pid == plugin.name)

            row = [
                plugin.name,
                plugin.version,
                plugin.status.value,
                str(skill_count),
            ]

            if verbose:
                source = plugin.metadata.get("source", "entry_point")
                row.extend([source, plugin.author or "—"])

            plugin_table.add_row(*row)

        console.print(plugin_table)

        # Skills table
        if skills:
            console.print()  # Blank line
            skill_table = Table(title="Available Skills", box=box.ROUNDED, title_style="bold cyan")
            skill_table.add_column("Skill ID", style="cyan")
            skill_table.add_column("Name", style="white")
            skill_table.add_column("Plugin", style="dim")
            skill_table.add_column("Capabilities", style="green")

            if verbose:
                skill_table.add_column("Version", style="yellow", justify="center")
                skill_table.add_column("Priority", style="blue", justify="center")

            for skill in skills:
                plugin_name = manager.skill_to_plugin.get(skill.id, "unknown")
                # Handle both string and enum capabilities
                caps = []
                for cap in skill.capabilities:
                    if hasattr(cap, "value"):
                        caps.append(cap.value)
                    else:
                        caps.append(str(cap))
                capabilities = ", ".join(caps)

                row = [skill.id, skill.name, plugin_name, capabilities]

                if verbose:
                    row.extend([skill.version, str(skill.priority)])

                skill_table.add_row(*row)

            console.print(skill_table)

    except ImportError:
        console.print("[red]Plugin system not available. Please check your installation.[/red]")
    except Exception as e:
        console.print(f"[red]Error listing plugins: {e}[/red]")


@plugin.command()
@click.argument("plugin_name", required=False)
@click.option(
    "--template", "-t", type=click.Choice(["basic", "advanced", "ai"]), default="basic", help="Plugin template"
)
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory for the plugin")
@click.option("--no-git", is_flag=True, help="Skip git initialization")
def create(plugin_name: str | None, template: str, output_dir: str | None, no_git: bool):
    """Create a new plugin for development."""
    console.print("[bold cyan]AgentUp Plugin Creator[/bold cyan]")
    console.print("Let's create a new plugin!\n")

    # Interactive prompts if not provided
    if not plugin_name:
        plugin_name = questionary.text(
            "Plugin name:",
            validate=lambda x: len(x.strip()) > 0 and x.replace("-", "").replace("_", "").isalnum(),
        ).ask()

        if not plugin_name:
            console.print("Cancelled.")
            return

    # Normalize plugin name
    plugin_name = plugin_name.lower().replace(" ", "-")

    # Get plugin details
    display_name = questionary.text("Display name:", default=plugin_name.replace("-", " ").title()).ask()

    description = questionary.text("Description:", default=f"A plugin that provides {display_name} functionality").ask()

    author = questionary.text("Author name:").ask()

    skill_id = questionary.text(
        "Primary skill ID:", default=plugin_name.replace("-", "_"), validate=lambda x: x.replace("_", "").isalnum()
    ).ask()

    # Determine output directory
    if not output_dir:
        output_dir = Path.cwd() / plugin_name
    else:
        output_dir = Path(output_dir) / plugin_name

    if output_dir.exists():
        if not questionary.confirm(f"Directory {output_dir} exists. Overwrite?", default=False).ask():
            console.print("Cancelled.")
            return
        shutil.rmtree(output_dir)

    # Create plugin structure
    console.print(f"\n[cyan]Creating plugin in {output_dir}...[/cyan]")

    try:
        # Create directories
        output_dir.mkdir(parents=True, exist_ok=True)
        src_dir = output_dir / "src" / plugin_name.replace("-", "_")
        src_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = output_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Create pyproject.toml
        pyproject_content = f'''[project]
name = "{plugin_name}"
version = "0.1.0"
description = "{description}"
authors = [
    {{ name = "{author or "Your Name"}", email = "your.email@example.com" }}
]
dependencies = [
    "agentup>=0.1.0",
    "pluggy>=1.5.0",
]

[project.entry-points."agentup.skills"]
{plugin_name.replace("-", "_")} = "{plugin_name.replace("-", "_")}.plugin:Plugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''
        (output_dir / "pyproject.toml").write_text(pyproject_content)

        # Create plugin.py based on template
        if template == "ai":
            plugin_code = _generate_ai_plugin_code(plugin_name, skill_id, display_name, description)
        elif template == "advanced":
            plugin_code = _generate_advanced_plugin_code(plugin_name, skill_id, display_name, description)
        else:
            plugin_code = _generate_basic_plugin_code(plugin_name, skill_id, display_name, description)

        (src_dir / "plugin.py").write_text(plugin_code)

        # Create __init__.py
        (src_dir / "__init__.py").write_text(
            f'"""Plugin: {display_name}"""\n\nfrom .plugin import Plugin\n\n__all__ = ["Plugin"]\n'
        )

        # Create README.md
        readme_content = f"""# {display_name}

{description}

## Installation

### For development:
```bash
cd {plugin_name}
pip install -e .
```

### From PyPI (when published):
```bash
pip install {plugin_name}
```

## Usage

This plugin provides the `{skill_id}` skill to AgentUp agents.

## Development

1. Edit `src/{plugin_name.replace("-", "_")}/plugin.py` to implement your skill logic
2. Test locally with an AgentUp agent
3. Publish to PyPI when ready

## Configuration

The skill can be configured in `agent_config.yaml`:

```yaml
skills:
  - skill_id: {skill_id}
    config:
      # Add your configuration options here
```
"""
        (output_dir / "README.md").write_text(readme_content)

        # Create test file
        test_content = f'''"""Tests for {display_name} plugin."""

import pytest
from agent.plugins.models import SkillContext, SkillInfo
from {plugin_name.replace("-", "_")}.plugin import Plugin


def test_plugin_registration():
    """Test that the plugin registers correctly."""
    plugin = Plugin()
    skill_info = plugin.register_skill()

    assert isinstance(skill_info, SkillInfo)
    assert skill_info.id == "{skill_id}"
    assert skill_info.name == "{display_name}"


def test_plugin_execution():
    """Test basic plugin execution."""
    plugin = Plugin()

    # Create a mock context
    from unittest.mock import Mock
    task = Mock()
    context = SkillContext(task=task)

    result = plugin.execute_skill(context)

    assert result.success
    assert result.content
'''
        (tests_dir / f"test_{plugin_name.replace('-', '_')}.py").write_text(test_content)

        # Create .gitignore
        gitignore_content = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.coverage
.env
.venv
env/
venv/
"""
        (output_dir / ".gitignore").write_text(gitignore_content)

        # Initialize git repo
        # Bandit: Add nosec to ignore command injection risk
        # This is safe as we control the output_dir input and it comes from trusted source (the code itself)
        if not no_git:
            subprocess.run(["git", "init"], cwd=output_dir, capture_output=True) # nosec
            subprocess.run(["git", "add", "."], cwd=output_dir, capture_output=True) # nosec
            subprocess.run(
                ["git", "commit", "-m", f"Initial commit for {plugin_name} plugin"], cwd=output_dir, capture_output=True
            ) # nosec

        # Success message
        console.print("\n[green]✅ Plugin created successfully![/green]")
        console.print(f"\nLocation: [cyan]{output_dir}[/cyan]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"1. cd {output_dir}")
        console.print("2. pip install -e .")
        console.print(f"3. Edit src/{plugin_name.replace('-', '_')}/plugin.py")
        console.print("4. Test with your AgentUp agent")

    except Exception as e:
        console.print(f"[red]Error creating plugin: {e}[/red]")
        if output_dir.exists():
            shutil.rmtree(output_dir)


def _generate_basic_plugin_code(plugin_name: str, skill_id: str, display_name: str, description: str) -> str:
    """Generate basic plugin template code."""
    return f'''"""
{display_name} plugin for AgentUp.

{description}
"""

import pluggy
from agent.plugins import SkillInfo, SkillContext, SkillResult, ValidationResult, SkillCapability

hookimpl = pluggy.HookimplMarker("agentup")


class Plugin:
    """Main plugin class for {display_name}."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "{plugin_name}"

    @hookimpl
    def register_skill(self) -> SkillInfo:
        """Register the skill with AgentUp."""
        return SkillInfo(
            id="{skill_id}",
            name="{display_name}",
            version="0.1.0",
            description="{description}",
            capabilities=[SkillCapability.TEXT],
            tags=["{plugin_name}", "custom"],
        )

    @hookimpl
    def validate_config(self, config: dict) -> ValidationResult:
        """Validate skill configuration."""
        # Add your validation logic here
        return ValidationResult(valid=True)

    @hookimpl
    def can_handle_task(self, context: SkillContext) -> bool:
        """Check if this skill can handle the task."""
        # Add your routing logic here
        # For now, return True to handle all tasks
        return True

    @hookimpl
    def execute_skill(self, context: SkillContext) -> SkillResult:
        """Execute the skill logic."""
        # Extract user input from the task
        user_input = self._extract_user_input(context)

        # Your skill logic here
        response = f"Processed by {display_name}: {{user_input}}"

        return SkillResult(
            content=response,
            success=True,
            metadata={{"skill": "{skill_id}"}},
        )

    def _extract_user_input(self, context: SkillContext) -> str:
        """Extract user input from the task context."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""
'''


def _generate_advanced_plugin_code(plugin_name: str, skill_id: str, display_name: str, description: str) -> str:
    """Generate advanced plugin template with more features."""
    return f'''"""
{display_name} plugin for AgentUp.

{description}
"""

import pluggy
from agent.plugins import SkillInfo, SkillContext, SkillResult, ValidationResult, SkillCapability

hookimpl = pluggy.HookimplMarker("agentup")


class Plugin:
    """Advanced plugin class for {display_name}."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "{plugin_name}"
        self.services = {{}}
        self.config = {{}}

    @hookimpl
    def register_skill(self) -> SkillInfo:
        """Register the skill with AgentUp."""
        return SkillInfo(
            id="{skill_id}",
            name="{display_name}",
            version="0.1.0",
            description="{description}",
            capabilities=[SkillCapability.TEXT, SkillCapability.STATEFUL],
            tags=["{plugin_name}", "advanced", "custom"],
            config_schema={{
                "type": "object",
                "properties": {{
                    "api_key": {{
                        "type": "string",
                        "description": "API key for external service",
                    }},
                    "timeout": {{
                        "type": "integer",
                        "default": 30,
                        "description": "Request timeout in seconds",
                    }},
                    "debug": {{
                        "type": "boolean",
                        "default": False,
                        "description": "Enable debug logging",
                    }},
                }},
                "required": ["api_key"],
            }},
        )

    @hookimpl
    def validate_config(self, config: dict) -> ValidationResult:
        """Validate skill configuration."""
        errors = []
        warnings = []

        # Check required fields
        if not config.get("api_key"):
            errors.append("api_key is required")

        # Validate timeout
        timeout = config.get("timeout", 30)
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append("timeout must be a positive integer")
        elif timeout > 300:
            warnings.append("timeout is very high (> 5 minutes)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @hookimpl
    def configure_services(self, services: dict) -> None:
        """Configure services for the plugin."""
        self.services = services
        # Access services like: services.get("llm"), services.get("database"), etc.

    @hookimpl
    def can_handle_task(self, context: SkillContext) -> float:
        """Check if this skill can handle the task."""
        # Advanced routing with confidence scoring
        user_input = self._extract_user_input(context).lower()

        # Define keywords and their confidence scores
        keywords = {{
            "{skill_id}": 1.0,
            "{plugin_name}": 0.9,
            # Add more keywords here
        }}

        # Calculate confidence based on keyword matches
        confidence = 0.0
        for keyword, score in keywords.items():
            if keyword in user_input:
                confidence = max(confidence, score)

        return confidence

    @hookimpl
    def execute_skill(self, context: SkillContext) -> SkillResult:
        """Execute the skill logic."""
        try:
            # Get configuration
            self.config = context.config

            # Extract user input
            user_input = self._extract_user_input(context)

            # Access state if needed
            state = context.state

            # Your advanced skill logic here
            # Example: Make API call, process data, etc.

            response = f"{display_name} processed: {{user_input}}"

            # Update state if needed
            state_updates = {{
                "last_processed": user_input,
                "process_count": state.get("process_count", 0) + 1,
            }}

            return SkillResult(
                content=response,
                success=True,
                metadata={{
                    "skill": "{skill_id}",
                    "confidence": self.can_handle_task(context),
                }},
                state_updates=state_updates,
            )

        except Exception as e:
            return SkillResult(
                content=f"Error processing request: {{str(e)}}",
                success=False,
                error=str(e),
            )

    @hookimpl
    def get_middleware_config(self) -> list[dict]:
        """Request middleware for this skill."""
        return [
            {{"type": "rate_limit", "requests_per_minute": 60}},
            {{"type": "cache", "ttl": 300}},
            {{"type": "logging", "level": "INFO"}},
        ]

    @hookimpl
    def get_state_schema(self) -> dict:
        """Define state schema for stateful operations."""
        return {{
            "type": "object",
            "properties": {{
                "last_processed": {{"type": "string"}},
                "process_count": {{"type": "integer"}},
                "user_preferences": {{"type": "object"}},
            }},
        }}

    @hookimpl
    def get_health_status(self) -> dict:
        """Report health status of the plugin."""
        return {{
            "status": "healthy",
            "version": "0.1.0",
            "services_available": list(self.services.keys()),
            "config_loaded": bool(self.config),
        }}

    def _extract_user_input(self, context: SkillContext) -> str:
        """Extract user input from the task context."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""
'''


def _generate_ai_plugin_code(plugin_name: str, skill_id: str, display_name: str, description: str) -> str:
    """Generate AI-enabled plugin template."""
    return f'''"""
{display_name} plugin for AgentUp with AI capabilities.

{description}
"""

import pluggy
from agent.plugins import (
    SkillInfo, SkillContext, SkillResult, ValidationResult, SkillCapability, AIFunction
)

hookimpl = pluggy.HookimplMarker("agentup")


class Plugin:
    """AI-enabled plugin class for {display_name}."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "{plugin_name}"
        self.llm_service = None

    @hookimpl
    def register_skill(self) -> SkillInfo:
        """Register the skill with AgentUp."""
        return SkillInfo(
            id="{skill_id}",
            name="{display_name}",
            version="0.1.0",
            description="{description}",
            capabilities=[SkillCapability.TEXT, SkillCapability.AI_FUNCTION],
            tags=["{plugin_name}", "ai", "llm"],
        )

    @hookimpl
    def validate_config(self, config: dict) -> ValidationResult:
        """Validate skill configuration."""
        # AI skills typically don't need much config
        return ValidationResult(valid=True)

    @hookimpl
    def configure_services(self, services: dict) -> None:
        """Configure services for the plugin."""
        # Store LLM service for AI operations
        self.llm_service = services.get("llm")

    @hookimpl
    def can_handle_task(self, context: SkillContext) -> bool:
        """Check if this skill can handle the task."""
        # For AI functions, let the LLM decide
        return True

    @hookimpl
    def execute_skill(self, context: SkillContext) -> SkillResult:
        """Execute the skill logic."""
        # This is called when the skill is invoked directly
        user_input = self._extract_user_input(context)

        return SkillResult(
            content=f"{display_name} is ready to help with: {{user_input}}",
            success=True,
        )

    @hookimpl
    def get_ai_functions(self) -> list[AIFunction]:
        """Provide AI functions for LLM function calling."""
        return [
            AIFunction(
                name="process_with_{skill_id}",
                description="Process user input with {display_name}",
                parameters={{
                    "type": "object",
                    "properties": {{
                        "input": {{
                            "type": "string",
                            "description": "The input to process",
                        }},
                        "options": {{
                            "type": "object",
                            "description": "Processing options",
                            "properties": {{
                                "mode": {{
                                    "type": "string",
                                    "enum": ["fast", "accurate", "balanced"],
                                    "default": "balanced",
                                }},
                                "format": {{
                                    "type": "string",
                                    "enum": ["text", "json", "markdown"],
                                    "default": "text",
                                }},
                            }},
                        }},
                    }},
                    "required": ["input"],
                }},
                handler=self._process_function,
            ),
            AIFunction(
                name="analyze_with_{skill_id}",
                description="Analyze data with {display_name}",
                parameters={{
                    "type": "object",
                    "properties": {{
                        "data": {{
                            "type": "string",
                            "description": "The data to analyze",
                        }},
                        "analysis_type": {{
                            "type": "string",
                            "enum": ["summary", "detailed", "comparison"],
                            "description": "Type of analysis to perform",
                        }},
                    }},
                    "required": ["data", "analysis_type"],
                }},
                handler=self._analyze_function,
            ),
        ]

    async def _process_function(self, task, context: SkillContext) -> SkillResult:
        """Handle the process AI function."""
        params = context.metadata.get("parameters", {{}})
        input_text = params.get("input", "")
        options = params.get("options", {{}})

        mode = options.get("mode", "balanced")
        format_type = options.get("format", "text")

        # Process based on mode
        if mode == "fast":
            result = f"Quick processing of: {{input_text[:50]}}..."
        elif mode == "accurate":
            result = f"Detailed processing of: {{input_text}}"
        else:
            result = f"Balanced processing of: {{input_text}}"

        # Format output
        if format_type == "json":
            import json
            result = json.dumps({{"result": result, "mode": mode}})
        elif format_type == "markdown":
            result = f"## Processing Result\\n\\n{{result}}"

        return SkillResult(content=result, success=True)

    async def _analyze_function(self, task, context: SkillContext) -> SkillResult:
        """Handle the analyze AI function."""
        params = context.metadata.get("parameters", {{}})
        data = params.get("data", "")
        analysis_type = params.get("analysis_type", "summary")

        # Perform analysis based on type
        if analysis_type == "summary":
            result = f"Summary of data ({{len(data)}} characters): {{data[:100]}}..."
        elif analysis_type == "detailed":
            result = f"Detailed analysis:\\n- Length: {{len(data)}} chars\\n- Content: {{data}}"
        else:  # comparison
            result = f"Comparison analysis not yet implemented for: {{data[:50]}}..."

        return SkillResult(
            content=result,
            success=True,
            metadata={{"analysis_type": analysis_type}},
        )

    def _extract_user_input(self, context: SkillContext) -> str:
        """Extract user input from the task context."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""
'''


@plugin.command()
@click.argument("plugin_name")
@click.option("--source", "-s", type=click.Choice(["pypi", "git", "local"]), default="pypi", help="Installation source")
@click.option("--url", "-u", help="Git URL or local path (for git/local sources)")
@click.option("--force", "-f", is_flag=True, help="Force reinstall if already installed")
def install(plugin_name: str, source: str, url: str | None, force: bool):
    """Install a plugin from PyPI, Git, or local directory."""
    if source in ["git", "local"] and not url:
        console.print(f"[red]Error: --url is required for {source} source[/red]")
        return

    console.print(f"[cyan]Installing plugin '{plugin_name}' from {source}...[/cyan]")

    try:
        # Prepare pip command
        if source == "pypi":
            cmd = [sys.executable, "-m", "pip", "install"]
            if force:
                cmd.append("--force-reinstall")
            cmd.append(plugin_name)
        elif source == "git":
            cmd = [sys.executable, "-m", "pip", "install"]
            if force:
                cmd.append("--force-reinstall")
            cmd.append(f"git+{url}")
        else:  # local
            cmd = [sys.executable, "-m", "pip", "install"]
            if force:
                cmd.append("--force-reinstall")
            cmd.extend(["-e", url])

        # Run pip install
        # Bandit: Add nosec to ignore command injection risk
        # This is safe as we control the plugin_name and url inputs and they come from trusted
        # sources (the code itself)
        result = subprocess.run(cmd, capture_output=True, text=True) # nosec

        if result.returncode == 0:
            console.print(f"[green]✅ Successfully installed {plugin_name}[/green]")
            console.print("\n[bold]Next steps:[/bold]")
            console.print("1. Restart your agent to load the new plugin")
            console.print("2. Run [cyan]agentup plugin list[/cyan] to verify installation")
        else:
            console.print(f"[red]❌ Failed to install {plugin_name}[/red]")
            console.print(f"[red]{result.stderr}[/red]")

    except Exception as e:
        console.print(f"[red]Error installing plugin: {e}[/red]")


@plugin.command()
@click.argument("plugin_name")
def uninstall(plugin_name: str):
    """Uninstall a plugin."""
    if not questionary.confirm(f"Uninstall plugin '{plugin_name}'?", default=False).ask():
        console.print("Cancelled.")
        return

    console.print(f"[cyan]Uninstalling plugin '{plugin_name}'...[/cyan]")

    try:
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y", plugin_name]
        # Bandit: Add nosec to ignore command injection risk
        # This is safe as we control the plugin_name input and it comes from trusted sources
        result = subprocess.run(cmd, capture_output=True, text=True) # nosec

        if result.returncode == 0:
            console.print(f"[green]✅ Successfully uninstalled {plugin_name}[/green]")
        else:
            console.print(f"[red]❌ Failed to uninstall {plugin_name}[/red]")
            console.print(f"[red]{result.stderr}[/red]")

    except Exception as e:
        console.print(f"[red]Error uninstalling plugin: {e}[/red]")


@plugin.command()
@click.argument("plugin_name")
def reload(plugin_name: str):
    """Reload a plugin (useful during development)."""
    try:
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()

        if plugin_name not in manager.plugins:
            console.print(f"[yellow]Plugin '{plugin_name}' not found[/yellow]")
            return

        console.print(f"[cyan]Reloading plugin '{plugin_name}'...[/cyan]")

        if manager.reload_plugin(plugin_name):
            console.print(f"[green]✅ Successfully reloaded {plugin_name}[/green]")
        else:
            console.print(f"[red]❌ Failed to reload {plugin_name}[/red]")
            console.print("[dim]Note: Entry point plugins cannot be reloaded[/dim]")

    except ImportError:
        console.print("[red]Plugin system not available.[/red]")
    except Exception as e:
        console.print(f"[red]Error reloading plugin: {e}[/red]")


@plugin.command()
@click.argument("skill_id")
def info(skill_id: str):
    """Show detailed information about a plugin skill."""
    try:
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        skill = manager.get_skill(skill_id)

        if not skill:
            console.print(f"[yellow]Skill '{skill_id}' not found[/yellow]")
            return

        # Get plugin info
        plugin_name = manager.skill_to_plugin.get(skill_id, "unknown")
        plugin = manager.plugins.get(plugin_name)

        # Build info panel
        info_lines = [
            f"[bold]Skill ID:[/bold] {skill.id}",
            f"[bold]Name:[/bold] {skill.name}",
            f"[bold]Version:[/bold] {skill.version}",
            f"[bold]Description:[/bold] {skill.description or 'No description'}",
            f"[bold]Plugin:[/bold] {plugin_name}",
            f"[bold]Capabilities:[/bold] {', '.join([cap.value if hasattr(cap, 'value') else str(cap) for cap in skill.capabilities])}",
            f"[bold]Tags:[/bold] {', '.join(skill.tags) if skill.tags else 'None'}",
            f"[bold]Priority:[/bold] {skill.priority}",
            f"[bold]Input Mode:[/bold] {skill.input_mode}",
            f"[bold]Output Mode:[/bold] {skill.output_mode}",
        ]

        if plugin:
            info_lines.extend(
                [
                    "",
                    "[bold cyan]Plugin Information:[/bold cyan]",
                    f"[bold]Status:[/bold] {plugin.status.value}",
                    f"[bold]Author:[/bold] {plugin.author or 'Unknown'}",
                    f"[bold]Source:[/bold] {plugin.metadata.get('source', 'entry_point')}",
                ]
            )

            if plugin.error:
                info_lines.append(f"[bold red]Error:[/bold red] {plugin.error}")

        # Configuration schema
        if skill.config_schema:
            info_lines.extend(["", "[bold cyan]Configuration Schema:[/bold cyan]"])
            import json

            schema_str = json.dumps(skill.config_schema, indent=2)
            info_lines.append(f"[dim]{schema_str}[/dim]")

        # AI functions
        ai_functions = manager.get_ai_functions(skill_id)
        if ai_functions:
            info_lines.extend(["", "[bold cyan]AI Functions:[/bold cyan]"])
            for func in ai_functions:
                info_lines.append(f"  • [green]{func.name}[/green]: {func.description}")

        # Health status
        if hasattr(manager.skill_hooks.get(skill_id), "get_health_status"):
            try:
                health = manager.skill_hooks[skill_id].get_health_status()
                info_lines.extend(["", "[bold cyan]Health Status:[/bold cyan]"])
                for key, value in health.items():
                    info_lines.append(f"  • {key}: {value}")
            except Exception:
                click.secho("[red]Error getting health status[/red]", err=True)
                pass

        # Create panel
        panel = Panel(
            "\n".join(info_lines),
            title=f"[bold cyan]{skill.name}[/bold cyan]",
            border_style="blue",
            padding=(1, 2),
        )

        console.print(panel)

    except ImportError:
        console.print("[red]Plugin system not available.[/red]")
    except Exception as e:
        console.print(f"[red]Error getting skill info: {e}[/red]")


@plugin.command()
def validate():
    """Validate all loaded plugins and their configurations."""
    try:
        from agent.config import load_config
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        config = load_config()

        console.print("[cyan]Validating plugins...[/cyan]\n")

        # Get skill configurations
        skill_configs = {skill.get("skill_id"): skill.get("config", {}) for skill in config.get("skills", [])}

        all_valid = True
        results = []

        for skill_id, skill_info in manager.skills.items():
            skill_config = skill_configs.get(skill_id, {})
            validation = manager.validate_config(skill_id, skill_config)

            results.append(
                {
                    "skill_id": skill_id,
                    "skill_name": skill_info.name,
                    "plugin": manager.skill_to_plugin.get(skill_id),
                    "validation": validation,
                    "has_config": skill_id in skill_configs,
                }
            )

            if not validation.valid:
                all_valid = False

        # Display results
        table = Table(title="Plugin Validation Results", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Skill", style="cyan")
        table.add_column("Plugin", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Issues", style="yellow")

        for result in results:
            skill_id = result["skill_id"]
            plugin = result["plugin"]
            validation = result["validation"]

            if validation.valid:
                status = "[green]✓ Valid[/green]"
                issues = ""
            else:
                status = "[red]✗ Invalid[/red]"
                issues = "; ".join(validation.errors)

            # Add warnings if any
            if validation.warnings:
                if issues:
                    issues += " | "
                issues += "[yellow]Warnings: " + "; ".join(validation.warnings) + "[/yellow]"

            table.add_row(skill_id, plugin, status, issues)

        console.print(table)

        if all_valid:
            console.print("\n[green]✅ All plugins validated successfully![/green]")
        else:
            console.print("\n[red]❌ Some plugins have validation errors.[/red]")
            console.print("Please check your agent_config.yaml and fix the issues.")

    except ImportError:
        console.print("[red]Plugin system not available.[/red]")
    except Exception as e:
        console.print(f"[red]Error validating plugins: {e}[/red]")
