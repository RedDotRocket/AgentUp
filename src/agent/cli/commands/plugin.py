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
    """Manage AgentUp plugins - create, install, list, and validate plugins."""
    pass


@plugin.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plugin information and logging")
@click.option("--capabilities", "-c", is_flag=True, help="Show available capabilities/AI functions")
@click.option("--format", "-f", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--debug", is_flag=True, help="Show debug logging output")
def list_plugins(verbose: bool, capabilities: bool, format: str, debug: bool):
    """List all loaded plugins and their capabilities."""
    try:
        # Configure logging based on verbose/debug flags
        import logging
        import os
        
        if debug:
            os.environ["AGENTUP_LOG_LEVEL"] = "DEBUG"
            logging.getLogger("agent.plugins").setLevel(logging.DEBUG)
            logging.getLogger("agent.plugins.manager").setLevel(logging.DEBUG)
        elif verbose:
            # Show INFO level for verbose mode
            logging.getLogger("agent.plugins").setLevel(logging.INFO)
            logging.getLogger("agent.plugins.manager").setLevel(logging.INFO)
        else:
            # Suppress all plugin discovery logs for clean output
            logging.getLogger("agent.plugins").setLevel(logging.WARNING)
            logging.getLogger("agent.plugins.manager").setLevel(logging.WARNING)
        
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        plugins = manager.list_plugins()
        available_capabilities = manager.list_capabilities()

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
                ]
            }
            
            # Only include capabilities if -c flag is used
            if capabilities:
                output["capabilities"] = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "version": c.version,
                        "plugin": manager.capability_to_plugin.get(c.id),
                        "features": c.capabilities,
                    }
                    for c in available_capabilities
                ]
            
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
                ]
            }
            
            # Only include capabilities if -c flag is used
            if capabilities:
                output["capabilities"] = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "version": c.version,
                        "plugin": manager.capability_to_plugin.get(c.id),
                        "features": c.capabilities,
                    }
                    for c in available_capabilities
                ]
            
            console.print(yaml.dump(output, default_flow_style=False))
            return

        # Table format (default)
        if not plugins:
            console.print("[yellow]No plugins loaded.[/yellow]")
            console.print("\nTo create a plugin: [cyan]agentup plugin create[/cyan]")
            console.print("To install from registry: [cyan]agentup plugin install <name>[/cyan]")
            return

        # Plugins table - simplified
        plugin_table = Table(title="Loaded Plugins", box=box.ROUNDED, title_style="bold cyan")
        plugin_table.add_column("Plugin", style="cyan")
        plugin_table.add_column("Name", style="white")
        plugin_table.add_column("Version", style="green", justify="center")
        plugin_table.add_column("Status", style="blue", justify="center")

        if verbose:
            plugin_table.add_column("Source", style="dim")
            plugin_table.add_column("Author", style="white")

        for plugin in plugins:
            # Get the friendly name from available_capabilities or use plugin name
            plugin_display_name = plugin.name
            # Find the first capability for this plugin to get its name
            for cap_id, plugin_name in manager.capability_to_plugin.items():
                if plugin_name == plugin.name:
                    capability_info = manager.capabilities.get(cap_id)
                    if capability_info and capability_info.name:
                        plugin_display_name = capability_info.name
                        break

            row = [
                plugin.name,
                plugin_display_name,
                plugin.version,
                plugin.status.value,
            ]

            if verbose:
                source = plugin.metadata.get("source", "entry_point")
                row.extend([source, plugin.author or "—"])

            plugin_table.add_row(*row)

        console.print(plugin_table)

        # Only show capabilities table if --capabilities flag is used
        if capabilities:
            # AI Functions table - show individual functions instead of capabilities
            console.print()  # Blank line
            
            # Collect all AI functions from all capabilities
            all_ai_functions = []
            for capability in available_capabilities:
                plugin_name = manager.capability_to_plugin.get(capability.id, "unknown")
                ai_functions = manager.get_ai_functions(capability.id)
                
                if ai_functions:
                    for func in ai_functions:
                        # Extract parameter names from the function schema
                        param_names = []
                        if "properties" in func.parameters:
                            param_names = list(func.parameters["properties"].keys())
                        
                        all_ai_functions.append({
                            "name": func.name,
                            "description": func.description,
                            "parameters": param_names,
                            "plugin": plugin_name,
                            "capability_id": capability.id
                        })

            if all_ai_functions:
                ai_table = Table(title="Available Capabilities", box=box.ROUNDED, title_style="bold cyan")
                ai_table.add_column("Capability ID", style="cyan")
                ai_table.add_column("Plugin", style="dim")
                ai_table.add_column("Parameters", style="green")

                if verbose:
                    ai_table.add_column("Description", style="white")

                for func in all_ai_functions:
                    parameters_str = ", ".join(func["parameters"]) if func["parameters"] else "none"
                    
                    row = [
                        func["name"],
                        func["plugin"],
                        parameters_str,
                    ]

                    if verbose:
                        row.append(func["description"][:80] + "..." if len(func["description"]) > 80 else func["description"])

                    ai_table.add_row(*row)

                console.print(ai_table)
            elif manager.list_capabilities():
                # Fallback to showing basic capabilities if no AI functions
                capability_table = Table(title="Available Capabilities", box=box.ROUNDED, title_style="bold cyan")
                capability_table.add_column("Capability ID", style="cyan")
                capability_table.add_column("Name", style="white")
                capability_table.add_column("Plugin", style="dim")
                capability_table.add_column("Features", style="green")

                if verbose:
                    capability_table.add_column("Version", style="yellow", justify="center")
                    capability_table.add_column("Priority", style="blue", justify="center")

                for capability in manager.list_capabilities():
                    plugin_name = manager.capability_to_plugin.get(capability.id, "unknown")
                    # Handle both string and enum capability features
                    caps = []
                    for cap in capability.capabilities:
                        if hasattr(cap, "value"):
                            caps.append(cap.value)
                        else:
                            caps.append(str(cap))
                    features = ", ".join(caps)

                    row = [capability.id, capability.name, plugin_name, features]

                    if verbose:
                        row.extend([capability.version, str(capability.priority)])

                    capability_table.add_row(*row)

                console.print(capability_table)

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

    capability_id = questionary.text(
        "Primary capability ID:", default=plugin_name.replace("-", "_"), validate=lambda x: x.replace("_", "").isalnum()
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

classifiers = [
    "Framework :: AgentUp :: Plugin",
]

[project.entry-points."agentup.available_capabilities"]
{plugin_name.replace("-", "_")} = "{plugin_name.replace("-", "_")}.plugin:Plugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''
        (output_dir / "pyproject.toml").write_text(pyproject_content)

        # Create plugin.py based on template
        if template == "ai":
            plugin_code = _generate_ai_plugin_code(plugin_name, capability_id, display_name, description)
        elif template == "advanced":
            plugin_code = _generate_advanced_plugin_code(plugin_name, capability_id, display_name, description)
        else:
            plugin_code = _generate_basic_plugin_code(plugin_name, capability_id, display_name, description)

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

This plugin provides the `{capability_id}` capability to AgentUp agents.

## Development

1. Edit `src/{plugin_name.replace("-", "_")}/plugin.py` to implement your capability logic
2. Test locally with an AgentUp agent
3. Publish to PyPI when ready

## Configuration

The capability can be configured in `agent_config.yaml`:

```yaml
plugins:
  - plugin_id: {capability_id}
    config:
      # Add your configuration options here
```
"""
        (output_dir / "README.md").write_text(readme_content)

        # Create test file
        test_content = f'''"""Tests for {display_name} plugin."""

import pytest
from agent.plugins.models import CapabilityContext, CapabilityInfo
from {plugin_name.replace("-", "_")}.plugin import Plugin


def test_plugin_registration():
    """Test that the plugin registers correctly."""
    plugin = Plugin()
    capability_info = plugin.register_capability()

    assert isinstance(capability_info, CapabilityInfo)
    assert capability_info.id == "{capability_id}"
    assert capability_info.name == "{display_name}"


def test_plugin_execution():
    """Test basic plugin execution."""
    plugin = Plugin()

    # Create a mock context
    from unittest.mock import Mock
    task = Mock()
    context = CapabilityContext(task=task)

    result = plugin.execute_capability(context)

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

        # Create CLAUDE.md for plugin development guidance
        claude_md_content = f"""# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this AgentUp plugin.

## Plugin Overview

This is an AgentUp plugin that provides {display_name} functionality. It follows the A2A-specification compliant plugin architecture using the pluggy hook system.

## Plugin Structure

```
{plugin_name}/
├── src/
│   └── {plugin_name.replace("-", "_")}/
│       ├── __init__.py
│       └── plugin.py           # Main plugin implementation
├── tests/
│   └── test_{plugin_name.replace("-", "_")}.py
├── pyproject.toml              # Package configuration with AgentUp entry point
├── README.md                   # Plugin documentation
└── CLAUDE.md                   # This file
```

## A2A Specification Compliance

This plugin is designed to be fully A2A-specification compliant. Always consult the A2A specification when making architectural decisions or implementing features.

## Core Plugin Architecture

### Hook System
The plugin uses pluggy hooks to integrate with AgentUp:

- `@hookimpl def register_capability()` - **Required** - Registers the plugin's capability(s)
- `@hookimpl def can_handle_task()` - **Required** - Determines if plugin can handle a task
- `@hookimpl def execute_capability()` - **Required** - Main capability execution logic
- `@hookimpl def validate_config()` - Optional - Validates plugin configuration
- `@hookimpl def get_ai_functions()` - Optional - Provides AI-callable functions
- `@hookimpl def configure_services()` - Optional - Configures external services
- `@hookimpl def get_middleware_config()` - Optional - Requests middleware

### Entry Point
The plugin is registered via entry point in `pyproject.toml`:
```toml
[project.entry-points."agentup.available_capabilities"]
{plugin_name.replace("-", "_")} = "{plugin_name.replace("-", "_")}.plugin:Plugin"
```

## Development Guidelines

### Code Style
- Follow PEP 8 and Python best practices
- Use type hints throughout the codebase
- Use async/await for I/O operations
- Handle errors gracefully with proper A2A error responses

### Plugin Implementation Patterns

#### 1. Capability Registration
```python
@hookimpl
def register_capability(self) -> CapabilityInfo:
    return CapabilityInfo(
        id="{capability_id}",
        name="{display_name}",
        version="0.1.0",
        description="{description}",
        available_capabilities=[CapabilityType.TEXT],  # Add available_capabilities as needed
        tags=["{plugin_name}", "custom"],
        config_schema={{
            # JSON schema for configuration validation
        }}
    )
```

#### 2. Task Routing
```python
@hookimpl
def can_handle_task(self, context: CapabilityContext) -> float:
    user_input = self._extract_user_input(context).lower()

    # Return confidence score (0.0 to 1.0)
    # Higher scores = more likely to handle the task
    keywords = {{'keyword1': 1.0, 'keyword2': 0.8}}

    confidence = 0.0
    for keyword, score in keywords.items():
        if keyword in user_input:
            confidence = max(confidence, score)

    return confidence
```

#### 3. Capability Execution
```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    try:
        user_input = self._extract_user_input(context)

        # Your capability logic here
        response = self._process_request(user_input)

        return CapabilityResult(
            content=response,
            success=True,
            metadata={{"capability": "{capability_id}"}}
        )
    except Exception as e:
        return CapabilityResult(
            content=f"Error: {{str(e)}}",
            success=False,
            error=str(e)
        )
```

#### 4. AI Function Support
```python
@hookimpl
def get_ai_functions(self) -> list[AIFunction]:
    return [
        AIFunction(
            name="function_name",
            description="Function description for LLM",
            parameters={{
                "type": "object",
                "properties": {{
                    "param1": {{
                        "type": "string",
                        "description": "Parameter description"
                    }}
                }},
                "required": ["param1"]
            }},
            handler=self._handle_function
        )
    ]
```

### Error Handling
- Always return CapabilityResult objects from execute_capability
- Use success=False for errors
- Include descriptive error messages
- Log errors appropriately for debugging

### Testing
- Write comprehensive tests for all plugin functionality
- Test both success and error cases
- Mock external dependencies
- Use pytest and async test patterns

### Configuration
- Define configuration schema in register_capability()
- Validate configuration in validate_config() hook
- Use environment variables for sensitive data
- Provide sensible defaults

## Development Workflow

### Local Development
1. Install in development mode: `pip install -e .`
2. Create test agent: `agentup agent create test-agent --template minimal`
3. Configure plugin in agent's `agent_config.yaml`
4. Test with: `agentup agent serve`

### Testing
```bash
# Run tests
pytest tests/ -v

# Check plugin loading
agentup plugin list

# Validate plugin
agentup plugin validate {plugin_name.replace("-", "_")}
```

### External Dependencies
- Use AgentUp's service registry for HTTP clients, databases, etc.
- Declare all dependencies in pyproject.toml
- Use async libraries for better performance

## Plugin Capabilities

### Available Capabilities
- `CapabilityType.TEXT` - Text processing
- `CapabilityType.MULTIMODAL` - Images, documents, etc.
- `CapabilityType.AI_FUNCTION` - LLM-callable functions
- `CapabilityType.STREAMING` - Streaming responses
- `CapabilityType.STATEFUL` - State management

### Middleware Support
Request middleware for common functionality:
- Rate limiting
- Caching
- Retry logic
- Logging
- Validation

### Service Integration
Access external services via AgentUp's service registry:
- HTTP clients
- Database connections
- Cache backends
- Message queues

## Best Practices

### Performance
- Use async/await for I/O operations
- Implement caching for expensive operations
- Use connection pooling for external APIs
- Minimize blocking operations

### Security
- Validate all inputs
- Sanitize outputs
- Use secure authentication methods
- Never log sensitive data

### Maintainability
- Follow single responsibility principle
- Keep functions small and focused
- Use descriptive variable names
- Add docstrings to all public methods

## Common Patterns

### External API Integration
```python
async def _call_external_api(self, data):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.example.com/endpoint",
            json=data,
            headers={{"Authorization": f"Bearer {{self.api_key}}"}}
        )
        response.raise_for_status()
        return response.json()
```

### State Management
```python
@hookimpl
def get_state_schema(self) -> dict:
    return {{
        "type": "object",
        "properties": {{
            "user_preferences": {{"type": "object"}},
            "session_data": {{"type": "object"}}
        }}
    }}
```

### Configuration Validation
```python
@hookimpl
def validate_config(self, config: dict) -> ValidationResult:
    errors = []
    warnings = []

    if not config.get("api_key"):
        errors.append("api_key is required")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

## Debugging Tips

### Common Issues
- Plugin not loading: Check entry point in pyproject.toml
- Functions not available: Verify get_ai_functions() returns valid schemas
- Routing not working: Debug can_handle_task() logic
- Configuration errors: Implement validate_config() hook

### Logging
```python
import logging
logger = logging.getLogger(__name__)

def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    logger.info("Processing request", extra={{"capability": "{capability_id}"}})
    # ... implementation
```

## Distribution

### Package Structure
- Follow Python package conventions
- Include comprehensive README.md
- Add LICENSE file
- Include CHANGELOG.md for version history

### Publishing
1. Test thoroughly with various agents
2. Update version in pyproject.toml
3. Build package: `python -m build`
4. Upload to PyPI: `python -m twine upload dist/*`

## Important Notes

### A2A Compliance
- All responses must be A2A-compliant
- Use proper task lifecycle management
- Follow A2A error response formats
- Implement proper message handling

### Framework Integration
- Leverage AgentUp's built-in features
- Use provided utilities and helpers
- Follow established patterns from other plugins
- Maintain compatibility with different agent templates

### Community Guidelines
- Write clear documentation
- Provide usage examples
- Follow semantic versioning
- Respond to issues and pull requests

## Resources

- [AgentUp Documentation](https://docs.agentup.dev)
- [A2A Specification](https://a2a.dev)
- [Plugin Development Guide](https://docs.agentup.dev/plugins/development)
- [Testing Guide](https://docs.agentup.dev/plugins/testing)
- [AI Functions Guide](https://docs.agentup.dev/plugins/ai-functions)

---

Remember: This plugin is part of the AgentUp ecosystem. Always consider how it integrates with other plugins and follows A2A standards for maximum compatibility and usefulness.
"""
        (output_dir / "CLAUDE.md").write_text(claude_md_content)

        # Initialize git repo
        # Bandit: Add nosec to ignore command injection risk
        # This is safe as we control the output_dir input and it comes from trusted source (the code itself)
        if not no_git:
            subprocess.run(["git", "init"], cwd=output_dir, capture_output=True)  # nosec
            subprocess.run(["git", "add", "."], cwd=output_dir, capture_output=True)  # nosec
            subprocess.run(
                ["git", "commit", "-m", f"Initial commit for {plugin_name} plugin"], cwd=output_dir, capture_output=True
            )  # nosec

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


def _generate_basic_plugin_code(plugin_name: str, capability_id: str, display_name: str, description: str) -> str:
    """Generate basic plugin template code."""
    return f'''"""
{display_name} plugin for AgentUp.

{description}
"""

import pluggy
from agent.plugins import CapabilityInfo, CapabilityContext, CapabilityResult, ValidationResult, CapabilityType

hookimpl = pluggy.HookimplMarker("agentup")


class Plugin:
    """Main plugin class for {display_name}."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "{plugin_name}"

    @hookimpl
    def register_capability(self) -> CapabilityInfo:
        """Register the capability with AgentUp."""
        return CapabilityInfo(
            id="{capability_id}",
            name="{display_name}",
            version="0.1.0",
            description="{description}",
            available_capabilities=[CapabilityType.TEXT],
            tags=["{plugin_name}", "custom"],
        )

    @hookimpl
    def validate_config(self, config: dict) -> ValidationResult:
        """Validate capability configuration."""
        # Add your validation logic here
        return ValidationResult(valid=True)

    @hookimpl
    def can_handle_task(self, context: CapabilityContext) -> bool:
        """Check if this capability can handle the task."""
        # Add your routing logic here
        # For now, return True to handle all tasks
        return True

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute the capability logic."""
        # Extract user input from the task
        user_input = self._extract_user_input(context)

        # Your capability logic here
        response = f"Processed by {display_name}: {{user_input}}"

        return CapabilityResult(
            content=response,
            success=True,
            metadata={{"capability": "{capability_id}"}},
        )

    def _extract_user_input(self, context: CapabilityContext) -> str:
        """Extract user input from the task context."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""
'''


def _generate_advanced_plugin_code(plugin_name: str, capability_id: str, display_name: str, description: str) -> str:
    """Generate advanced plugin template with more features."""
    return f'''"""
{display_name} plugin for AgentUp.

{description}
"""

import pluggy
from agent.plugins import CapabilityInfo, CapabilityContext, CapabilityResult, ValidationResult, CapabilityType

hookimpl = pluggy.HookimplMarker("agentup")


class Plugin:
    """Advanced plugin class for {display_name}."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "{plugin_name}"
        self.services = {{}}
        self.config = {{}}

    @hookimpl
    def register_capability(self) -> CapabilityInfo:
        """Register the capability with AgentUp."""
        return CapabilityInfo(
            id="{capability_id}",
            name="{display_name}",
            version="0.1.0",
            description="{description}",
            available_capabilities=[CapabilityType.TEXT, CapabilityType.STATEFUL],
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
        """Validate capability configuration."""
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
    def can_handle_task(self, context: CapabilityContext) -> float:
        """Check if this capability can handle the task."""
        # Advanced routing with confidence scoring
        user_input = self._extract_user_input(context).lower()

        # Define keywords and their confidence scores
        keywords = {{
            "{capability_id}": 1.0,
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
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute the capability logic."""
        try:
            # Get configuration
            self.config = context.config

            # Extract user input
            user_input = self._extract_user_input(context)

            # Access state if needed
            state = context.state

            # Your advanced capability logic here
            # Example: Make API call, process data, etc.

            response = f"{display_name} processed: {{user_input}}"

            # Update state if needed
            state_updates = {{
                "last_processed": user_input,
                "process_count": state.get("process_count", 0) + 1,
            }}

            return CapabilityResult(
                content=response,
                success=True,
                metadata={{
                    "capability": "{capability_id}",
                    "confidence": self.can_handle_task(context),
                }},
                state_updates=state_updates,
            )

        except Exception as e:
            return CapabilityResult(
                content=f"Error processing request: {{str(e)}}",
                success=False,
                error=str(e),
            )

    @hookimpl
    def get_middleware_config(self) -> list[dict]:
        """Request middleware for this capability."""
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

    def _extract_user_input(self, context: CapabilityContext) -> str:
        """Extract user input from the task context."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""
'''


def _generate_ai_plugin_code(plugin_name: str, capability_id: str, display_name: str, description: str) -> str:
    """Generate AI-enabled plugin template."""
    return f'''"""
{display_name} plugin for AgentUp with AI available_capabilities.

{description}
"""

import pluggy
from agent.plugins import (
    CapabilityInfo, CapabilityContext, CapabilityResult, ValidationResult, CapabilityType, AIFunction
)

hookimpl = pluggy.HookimplMarker("agentup")


class Plugin:
    """AI-enabled plugin class for {display_name}."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "{plugin_name}"
        self.llm_service = None

    @hookimpl
    def register_capability(self) -> CapabilityInfo:
        """Register the capability with AgentUp."""
        return CapabilityInfo(
            id="{capability_id}",
            name="{display_name}",
            version="0.1.0",
            description="{description}",
            available_capabilities=[CapabilityType.TEXT, CapabilityType.AI_FUNCTION],
            tags=["{plugin_name}", "ai", "llm"],
        )

    @hookimpl
    def validate_config(self, config: dict) -> ValidationResult:
        """Validate capability configuration."""
        # AI available_capabilities typically don't need much config
        return ValidationResult(valid=True)

    @hookimpl
    def configure_services(self, services: dict) -> None:
        """Configure services for the plugin."""
        # Store LLM service for AI operations
        self.llm_service = services.get("llm")

    @hookimpl
    def can_handle_task(self, context: CapabilityContext) -> bool:
        """Check if this capability can handle the task."""
        # For AI functions, let the LLM decide
        return True

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute the capability logic."""
        # This is called when the capability is invoked directly
        user_input = self._extract_user_input(context)

        return CapabilityResult(
            content=f"{display_name} is ready to help with: {{user_input}}",
            success=True,
        )

    @hookimpl
    def get_ai_functions(self) -> list[AIFunction]:
        """Provide AI functions for LLM function calling."""
        return [
            AIFunction(
                name="process_with_{capability_id}",
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
                name="analyze_with_{capability_id}",
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

    async def _process_function(self, task, context: CapabilityContext) -> CapabilityResult:
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

        return CapabilityResult(content=result, success=True)

    async def _analyze_function(self, task, context: CapabilityContext) -> CapabilityResult:
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

        return CapabilityResult(
            content=result,
            success=True,
            metadata={{"analysis_type": analysis_type}},
        )

    def _extract_user_input(self, context: CapabilityContext) -> str:
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
        result = subprocess.run(cmd, capture_output=True, text=True)  # nosec

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
        result = subprocess.run(cmd, capture_output=True, text=True)  # nosec

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
@click.argument("capability_id")
def info(capability_id: str):
    """Show detailed information about a plugin capability."""
    try:
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        capability = manager.get_capability(capability_id)

        if not capability:
            console.print(f"[yellow]Capability '{capability_id}' not found[/yellow]")
            return

        # Get plugin info
        plugin_name = manager.capability_to_plugin.get(capability_id, "unknown")
        plugin = manager.plugins.get(plugin_name)

        # Build info panel
        info_lines = [
            f"[bold]Capability ID:[/bold] {capability.id}",
            f"[bold]Name:[/bold] {capability.name}",
            f"[bold]Version:[/bold] {capability.version}",
            f"[bold]Description:[/bold] {capability.description or 'No description'}",
            f"[bold]Plugin:[/bold] {plugin_name}",
            f"[bold]Features:[/bold] {', '.join([cap.value if hasattr(cap, 'value') else str(cap) for cap in capability.capabilities])}",
            f"[bold]Tags:[/bold] {', '.join(capability.tags) if capability.tags else 'None'}",
            f"[bold]Priority:[/bold] {capability.priority}",
            f"[bold]Input Mode:[/bold] {capability.input_mode}",
            f"[bold]Output Mode:[/bold] {capability.output_mode}",
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
        if capability.config_schema:
            info_lines.extend(["", "[bold cyan]Configuration Schema:[/bold cyan]"])
            import json

            schema_str = json.dumps(capability.config_schema, indent=2)
            info_lines.append(f"[dim]{schema_str}[/dim]")

        # AI functions
        ai_functions = manager.get_ai_functions(capability_id)
        if ai_functions:
            info_lines.extend(["", "[bold cyan]AI Functions:[/bold cyan]"])
            for func in ai_functions:
                info_lines.append(f"  • [green]{func.name}[/green]: {func.description}")

        # Health status
        if hasattr(manager.capability_hooks.get(capability_id), "get_health_status"):
            try:
                health = manager.capability_hooks[capability_id].get_health_status()
                info_lines.extend(["", "[bold cyan]Health Status:[/bold cyan]"])
                for key, value in health.items():
                    info_lines.append(f"  • {key}: {value}")
            except Exception:
                click.secho("[red]Error getting health status[/red]", err=True)
                pass

        # Create panel
        panel = Panel(
            "\n".join(info_lines),
            title=f"[bold cyan]{capability.name}[/bold cyan]",
            border_style="blue",
            padding=(1, 2),
        )

        console.print(panel)

    except ImportError:
        console.print("[red]Plugin system not available.[/red]")
    except Exception as e:
        console.print(f"[red]Error getting capability info: {e}[/red]")


@plugin.command()
def validate():
    """Validate all loaded plugins and their configurations."""
    try:
        from agent.config import load_config
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        config = load_config()

        console.print("[cyan]Validating plugins...[/cyan]\n")

        # Get capability configurations
        capability_configs = {plugin.get("plugin_id"): plugin.get("config", {}) for plugin in config.get("plugins", [])}

        all_valid = True
        results = []

        for capability_id, capability_info in manager.capabilities.items():
            capability_config = capability_configs.get(capability_id, {})
            validation = manager.validate_config(capability_id, capability_config)

            results.append(
                {
                    "capability_id": capability_id,
                    "capability_name": capability_info.name,
                    "plugin": manager.capability_to_plugin.get(capability_id),
                    "validation": validation,
                    "has_config": capability_id in capability_configs,
                }
            )

            if not validation.valid:
                all_valid = False

        # Display results
        table = Table(title="Plugin Validation Results", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Capability", style="cyan")
        table.add_column("Plugin", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Issues", style="yellow")

        for result in results:
            capability_id = result["capability_id"]
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

            table.add_row(capability_id, plugin, status, issues)

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
