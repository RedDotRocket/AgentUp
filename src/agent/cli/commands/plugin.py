import json
import shutil
import subprocess  # nosec
import sys
from pathlib import Path

import click
import questionary
from jinja2 import Environment, FileSystemLoader
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...utils.version import get_version

# Standard library modules that should not be used as plugin names
_STDLIB_MODULES = {
    # Core builtins
    "builtins",
    "__builtin__",
    "__future__",
    "sys",
    "os",
    "io",
    "re",
    "json",
    "xml",
    "csv",
    "urllib",
    "http",
    "email",
    "html",
    "collections",
    "itertools",
    "functools",
    "operator",
    "pathlib",
    "glob",
    "shutil",
    "tempfile",
    "datetime",
    "time",
    "calendar",
    "hashlib",
    "hmac",
    "secrets",
    "random",
    "math",
    "cmath",
    "decimal",
    "fractions",
    "statistics",
    "array",
    "struct",
    "codecs",
    "unicodedata",
    "stringprep",
    "readline",
    "rlcompleter",
    "pickle",
    "copyreg",
    "copy",
    "pprint",
    "reprlib",
    "enum",
    "types",
    "weakref",
    "gc",
    "inspect",
    "site",
    "importlib",
    "pkgutil",
    "modulefinder",
    "runpy",
    "traceback",
    "faulthandler",
    "pdb",
    "profile",
    "pstats",
    "timeit",
    "trace",
    "contextlib",
    "abc",
    "atexit",
    "tracemalloc",
    "warnings",
    "dataclasses",
    "contextvar",
    "concurrent",
    "threading",
    "multiprocessing",
    "subprocess",
    "sched",
    "queue",
    "select",
    "selectors",
    "asyncio",
    "socket",
    "ssl",
    "signal",
    "mmap",
    "ctypes",
    "logging",
    "getopt",
    "argparse",
    "fileinput",
    "linecache",
    "shlex",
    "configparser",
    "netrc",
    "mailcap",
    "mimetypes",
    "base64",
    "binhex",
    "binascii",
    "quopri",
    "uu",
    "sqlite3",
    "zlib",
    "gzip",
    "bz2",
    "lzma",
    "zipfile",
    "tarfile",
    "getpass",
    "cmd",
    "turtle",
    "wsgiref",
    "unittest",
    "doctest",
    "test",
    "2to3",
    "lib2to3",
    "venv",
    "ensurepip",
    "zipapp",
    "platform",
    "errno",
    "msilib",
    "msvcrt",
    "winreg",
    "winsound",
    "posix",
    "pwd",
    "spwd",
    "grp",
    "crypt",
    "termios",
    "tty",
    "pty",
    "fcntl",
    "pipes",
    "resource",
    "nis",
    "syslog",
    "optparse",
    "imp",
    "zipimport",
    "ast",
    "symtable",
    "token",
    "keyword",
    "tokenize",
    "tabnanny",
    "pyclbr",
    "py_compile",
    "compileall",
    "dis",
    "pickletools",
    "formatter",
    "parser",
    "symbol",
    "compiler",
}

# Reserved names that may cause conflicts in projects
_RESERVED_NAMES = {
    "agentup",
    "test",
    "tests",
    "setup",
    "install",
    "build",
    "dist",
    "egg",
    "develop",
    "docs",
    "doc",
    "src",
    "lib",
    "bin",
    "scripts",
    "tools",
    "util",
    "utils",
    "common",
    "core",
    "main",
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "env",
    "virtual",
    "virtualenv",
    "requirements",
    "config",
    "conf",
    "settings",
    "data",
    "tmp",
    "temp",
    "cache",
    "log",
    "logs",
    "admin",
    "root",
    "user",
    "api",
}


def _render_plugin_template(template_name: str, context: dict) -> str:
    templates_dir = Path(__file__).parent.parent.parent / "templates" / "plugins"

    # For YAML files, disable block trimming to preserve proper formatting
    if template_name.endswith(".yml.j2") or template_name.endswith(".yaml.j2"):
        jinja_env = Environment(
            loader=FileSystemLoader(templates_dir), autoescape=True, trim_blocks=False, lstrip_blocks=False
        )
    else:
        jinja_env = Environment(
            loader=FileSystemLoader(templates_dir), autoescape=True, trim_blocks=True, lstrip_blocks=True
        )

    template = jinja_env.get_template(template_name)
    return template.render(context)


def _render_and_write_template(template_name: str, output_path: Path, context: dict) -> None:
    """Renders a Jinja2 template and writes it to the specified path."""
    content = _render_plugin_template(template_name, context)
    output_path.write_text(content, encoding="utf-8")


def _to_snake_case(name: str) -> str:
    # Replace hyphens and spaces with underscores
    name = name.replace("-", "_").replace(" ", "_")
    # Remove any non-alphanumeric characters except underscores
    name = "".join(c for c in name if c.isalnum() or c == "_")
    return name.lower()


def _validate_plugin_name(name: str) -> tuple[bool, str]:
    """Validate plugin name to ensure it won't conflict with Python builtins or reserved names.

    Returns:
        tuple: (is_valid, error_message)
    """
    # Check basic format
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        return False, "Plugin name must contain only letters, numbers, hyphens, and underscores"

    # Check for invalid start/end characters
    if name.startswith(("-", "_")) or name.endswith(("-", "_")):
        return False, "Plugin name cannot start or end with hyphens or underscores"

    # Check if starts with a number
    if name[0].isdigit():
        return False, "Plugin name cannot start with a number"

    # Normalize to check against Python modules
    normalized_name = name.lower().replace("-", "_")

    if normalized_name in _STDLIB_MODULES:
        return False, f"'{name}' conflicts with Python standard library module '{normalized_name}'"

    # Check against commonly reserved names and project terms
    if normalized_name in _RESERVED_NAMES:
        return False, f"'{name}' is a reserved name that may cause conflicts"

    # Check if it's too short
    if len(name) < 3:
        return False, "Plugin name should be at least 3 characters long"

    return True, ""


@click.group("plugin", help="Manage plugins and their configurations.")
def plugin():
    pass


@plugin.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plugin information and logging")
@click.option("--capabilities", "-c", is_flag=True, help="Show available capabilities/AI functions")
@click.option(
    "--format", "-f", type=click.Choice(["table", "json", "yaml", "agentup-cfg"]), default="table", help="Output format"
)
@click.option("--agentup-cfg", is_flag=True, help="Output in agentup.yml format (same as --format agentup-cfg)")
@click.option("--debug", is_flag=True, help="Show debug logging output")
def list_plugins(verbose: bool, capabilities: bool, format: str, agentup_cfg: bool, debug: bool):
    # Handle --agentup-cfg flag (shortcut for --format agentup-cfg)
    if agentup_cfg:
        format = "agentup-cfg"

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

        from agent.plugins.manager import PluginRegistry

        # Create a registry without auto-discovery to avoid allowlist warnings during listing
        try:
            from agent.config import Config

            config = Config.model_dump()
        except ImportError:
            config = None

        manager = PluginRegistry(config)

        # Use the discovery method that bypasses allowlist for listing purposes
        all_available_plugins = manager.discover_all_available_plugins()

        if format == "json":
            output = {
                "plugins": [
                    {
                        "name": plugin_info["name"],
                        "version": plugin_info["version"],
                        "package": plugin_info["package"],
                        "status": plugin_info["status"],
                        "loaded": plugin_info["loaded"],
                        "configured": plugin_info["configured"],
                    }
                    for plugin_info in all_available_plugins
                ]
            }

            # Only include capabilities if -c flag is used
            if capabilities:
                # Discover capabilities for JSON output (same as table output)
                capabilities_for_json = []
                for plugin_info in all_available_plugins:
                    plugin_name = plugin_info["name"]
                    try:
                        import importlib.metadata

                        entry_points = importlib.metadata.entry_points()

                        if hasattr(entry_points, "select"):
                            plugin_entries = entry_points.select(group="agentup.plugins", name=plugin_name)
                        else:
                            plugin_entries = [
                                ep for ep in entry_points.get("agentup.plugins", []) if ep.name == plugin_name
                            ]

                        for entry_point in plugin_entries:
                            try:
                                plugin_class = entry_point.load()
                                plugin_instance = plugin_class()
                                cap_definitions = plugin_instance.get_capability_definitions()

                                for cap_def in cap_definitions:
                                    capabilities_for_json.append(
                                        {
                                            "id": cap_def.id,
                                            "name": cap_def.name,
                                            "description": cap_def.description,
                                            "plugin": plugin_name,
                                            "required_scopes": cap_def.required_scopes,
                                            "ai_function": cap_def.is_ai_capability,
                                        }
                                    )
                            except Exception as e:
                                if debug or verbose:
                                    click.secho(
                                        f"Warning: Could not load plugin {plugin_name}: {e}",
                                        fg="yellow",
                                    )
                                continue
                    except Exception as e:
                        if debug or verbose:
                            click.secho(f"Warning: Could not load plugin {plugin_name}: {e}", fg="red")
                        continue

                output["capabilities"] = capabilities_for_json

            click.secho(json.dumps(output, indent=2))
            return

        if format == "yaml":
            import yaml

            output = {
                "plugins": [
                    {
                        "plugin_id": plugin_info["name"],
                        "version": plugin_info["version"],
                        "package": plugin_info["package"],
                        "status": plugin_info["status"],
                        "loaded": plugin_info["loaded"],
                        "configured": plugin_info["configured"],
                    }
                    for plugin_info in all_available_plugins
                ]
            }

            # Only include capabilities if -c flag is used (same logic as JSON)
            if capabilities:
                capabilities_for_yaml = []
                for plugin_info in all_available_plugins:
                    plugin_name = plugin_info["name"]
                    try:
                        import importlib.metadata

                        entry_points = importlib.metadata.entry_points()

                        if hasattr(entry_points, "select"):
                            plugin_entries = entry_points.select(group="agentup.plugins", name=plugin_name)
                        else:
                            plugin_entries = [
                                ep for ep in entry_points.get("agentup.plugins", []) if ep.name == plugin_name
                            ]

                        for entry_point in plugin_entries:
                            try:
                                plugin_class = entry_point.load()
                                plugin_instance = plugin_class()
                                cap_definitions = plugin_instance.get_capability_definitions()

                                for cap_def in cap_definitions:
                                    capabilities_for_yaml.append(
                                        {
                                            "id": cap_def.id,
                                            "name": cap_def.name,
                                            "description": cap_def.description,
                                            "plugin": plugin_name,
                                            "required_scopes": cap_def.required_scopes,
                                            "ai_function": cap_def.is_ai_capability,
                                        }
                                    )
                            except Exception as e:
                                if debug or verbose:
                                    click.secho(f"Warning: Could not load plugin {plugin_name}: {e}", fg="red")
                                continue
                    except Exception as e:
                        if debug or verbose:
                            click.secho(f"Warning: Could not load plugin {plugin_name}: {e}", fg="red")
                        continue

                output["capabilities"] = capabilities_for_yaml

            click.secho(yaml.dump(output, default_flow_style=False))
            return

        if format == "agentup-cfg":
            from collections import OrderedDict

            import yaml

            console = Console()

            # Custom representer to maintain field order
            def represent_ordereddict(dumper, data):
                return dumper.represent_dict(data.items())

            yaml.add_representer(OrderedDict, represent_ordereddict)

            # For agentup-cfg format, always include capabilities (no -c flag needed)
            plugins_config = []

            for plugin_info in all_available_plugins:
                plugin_name = plugin_info["name"]
                package_name = plugin_info["package"]

                # Generate better name and description
                base_name = plugin_name.replace("_", " ").replace("-", " ").title()
                if base_name.lower().endswith("plugin"):
                    display_name = base_name
                else:
                    display_name = base_name + " Plugin"

                # Use OrderedDict to maintain field order
                plugin_config = OrderedDict(
                    [
                        ("plugin_id", plugin_name),
                        ("package", package_name),
                        ("name", display_name),
                        (
                            "description",
                            f"A plugin for {plugin_name.replace('_', ' ').replace('-', ' ')} functionality",
                        ),
                        ("tags", [plugin_name.replace("_", "-").replace(" ", "-").lower()]),
                        ("input_mode", "text"),
                        ("output_mode", "text"),
                        ("priority", 50),
                        ("capabilities", []),
                    ]
                )

                # Load capabilities for this plugin
                try:
                    import importlib.metadata

                    entry_points = importlib.metadata.entry_points()

                    if hasattr(entry_points, "select"):
                        plugin_entries = entry_points.select(group="agentup.plugins", name=plugin_name)
                    else:
                        plugin_entries = [
                            ep for ep in entry_points.get("agentup.plugins", []) if ep.name == plugin_name
                        ]

                    for entry_point in plugin_entries:
                        try:
                            plugin_class = entry_point.load()
                            plugin_instance = plugin_class()
                            cap_definitions = plugin_instance.get_capability_definitions()

                            for cap_def in cap_definitions:
                                capability_config = OrderedDict(
                                    [
                                        ("capability_id", cap_def.id),
                                        ("required_scopes", cap_def.required_scopes),
                                        ("enabled", True),
                                    ]
                                )
                                plugin_config["capabilities"].append(capability_config)

                        except Exception as e:
                            if debug or verbose:
                                console.print(f"[dim red]Warning: Could not load plugin {plugin_name}: {e}[/dim red]")
                            continue
                except Exception as e:
                    if debug or verbose:
                        console.print(f"[dim red]Warning: Could not find entry point for {plugin_name}: {e}[/dim red]")
                    continue

                # Only add plugins that have capabilities
                if plugin_config["capabilities"]:
                    plugins_config.append(plugin_config)

            if plugins_config:
                output = {"plugins": plugins_config}
                # Use sort_keys=False to preserve order, default_flow_style=False for block style
                yaml_output = yaml.dump(
                    output, default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000, indent=2
                )
                console.print(yaml_output)
            else:
                console.print("plugins: []")
            return

        # Table format (default)
        if not all_available_plugins:
            click.secho("[yellow]No plugins found.[/yellow]")
            click.secho("\nTo create a plugin: [cyan]agentup plugin create[/cyan]")
            click.secho("To install from registry: [cyan]agentup plugin install <name>[/cyan]")
            return

        # Plugins table - show all available plugins
        plugin_table = Table(title="Available Plugins", box=box.ROUNDED, title_style="bold cyan")
        plugin_table.add_column("Plugin", style="cyan")
        plugin_table.add_column("Package", style="white")
        plugin_table.add_column("Version", style="green", justify="center")
        plugin_table.add_column("Status", style="blue", justify="center")

        if verbose:
            plugin_table.add_column("Configured", style="dim", justify="center")
            plugin_table.add_column("Module", style="dim")

        for plugin_info in all_available_plugins:
            # Determine status display
            status = plugin_info["status"]
            if plugin_info["loaded"]:
                status = "loaded"
            elif plugin_info["configured"]:
                status = "configured"
            else:
                status = "available"

            row = [
                plugin_info["name"],
                plugin_info["package"],
                plugin_info["version"],
                status,
            ]

            if verbose:
                configured = "✓" if plugin_info["configured"] else "✗"
                row.extend([configured, plugin_info.get("module", "unknown")])

            plugin_table.add_row(*row)

        console = Console()
        console.print(plugin_table)

        # Only show capabilities table if --capabilities flag is used
        if capabilities:
            click.secho()  # Blank line

            # For capabilities display, we need to temporarily load plugins to get their capabilities
            # This is only done when explicitly requested with -c flag
            all_capabilities_info = []

            for plugin_info in all_available_plugins:
                plugin_name = plugin_info["name"]

                try:
                    # Try to load the plugin class to get its capabilities
                    import importlib.metadata

                    entry_points = importlib.metadata.entry_points()

                    # Handle different Python versions
                    if hasattr(entry_points, "select"):
                        plugin_entries = entry_points.select(group="agentup.plugins", name=plugin_name)
                    else:
                        plugin_entries = [
                            ep for ep in entry_points.get("agentup.plugins", []) if ep.name == plugin_name
                        ]

                    for entry_point in plugin_entries:
                        try:
                            plugin_class = entry_point.load()
                            plugin_instance = plugin_class()

                            # Get capability definitions
                            cap_definitions = plugin_instance.get_capability_definitions()

                            for cap_def in cap_definitions:
                                all_capabilities_info.append(
                                    {
                                        "id": cap_def.id,
                                        "name": cap_def.name,
                                        "description": cap_def.description,
                                        "plugin": plugin_name,
                                        "scopes": cap_def.required_scopes,
                                        "ai_function": cap_def.is_ai_capability,
                                        "tags": getattr(cap_def, "tags", []),
                                    }
                                )

                        except Exception as e:
                            # Skip failed plugin loads but don't show errors in list command
                            if debug or verbose:
                                click.secho(f"Warning: Could not load plugin {plugin_name}: {e}", fg="red)")
                            continue

                except Exception as e:
                    if debug or verbose:
                        click.secho(f"Warning: Could not find entry point for {plugin_name}: {e}", fg="red")
                    continue

            if all_capabilities_info:
                capabilities_table = Table(title="Available Capabilities", box=box.ROUNDED, title_style="bold cyan")
                capabilities_table.add_column("Capability", style="cyan")
                capabilities_table.add_column("Plugin", style="dim")
                capabilities_table.add_column("AI Function", style="green", justify="center")
                capabilities_table.add_column("Required Scopes", style="yellow")

                if verbose:
                    capabilities_table.add_column("Description", style="white")

                for cap_info in all_capabilities_info:
                    ai_indicator = "✓" if cap_info["ai_function"] else "✗"
                    scopes_str = ", ".join(cap_info["scopes"]) if cap_info["scopes"] else "none"

                    row = [
                        cap_info["id"],  # Show ID instead of name - this is what goes in config
                        cap_info["plugin"],
                        ai_indicator,
                        scopes_str,
                    ]

                    if verbose:
                        description = cap_info["description"] or "No description"
                        row.append(description[:80] + "..." if len(description) > 80 else description)

                    capabilities_table.add_row(*row)

                console.print(capabilities_table)
            else:
                click.secho("No capabilities found. This may indicate:", fg="yellow")
                click.secho("  • No plugins are installed", fg="yellow")
                click.secho("  • Plugins have issues loading", fg="yellow")
                click.secho("  • Use --verbose to see loading details", fg="yellow")

    except ImportError:
        click.secho("[red]Plugin system not available. Please check your installation.[/red]")
    except Exception as e:
        click.secho(f"[red]Error listing plugins: {e}[/red]")


@plugin.command()
@click.argument("plugin_name", required=False)
@click.option("--template", "-t", type=click.Choice(["direct", "ai"]), default="direct", help="Plugin template")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory for the plugin")
@click.option("--no-git", is_flag=True, help="Skip git initialization")
def create(plugin_name: str | None, template: str, output_dir: str | None, no_git: bool):
    click.secho("[bold cyan]AgentUp Plugin Creator[/bold cyan]")
    click.secho("Let's create a new plugin!\n")

    # Interactive prompts if not provided
    if not plugin_name:

        def validate_name(name: str) -> bool | str:
            """Validator for questionary that returns True or error message."""
            is_valid, error_msg = _validate_plugin_name(name)
            return True if is_valid else error_msg

        plugin_name = questionary.text(
            "Plugin name:",
            validate=validate_name,
        ).ask()

        if not plugin_name:
            click.secho("Cancelled.", fg="yellow")
            return

    # Normalize plugin name
    plugin_name = plugin_name.lower().replace(" ", "-")

    # Validate the name even if provided via CLI
    is_valid, error_msg = _validate_plugin_name(plugin_name)
    if not is_valid:
        click.secho(f"Error: {error_msg}", fg="red")
        return

    # Get plugin details
    display_name = questionary.text("Display name:", default=plugin_name.replace("-", " ").title()).ask()

    description = questionary.text("Description:", default=f"A plugin that provides {display_name} functionality").ask()

    author = questionary.text("Author name:").ask()

    def validate_email(email: str) -> bool | str:
        """Validator for questionary that returns True or error message."""
        if not email.strip():
            return True  # Allow empty email

        # Basic email validation
        if " " in email:
            return "Email cannot contain spaces"
        if "@" not in email:
            return "Email must contain @"
        if email.count("@") != 1:
            return "Email must contain exactly one @"

        parts = email.split("@")
        if not parts[0] or not parts[1]:
            return "Email must have text before and after @"
        if "." not in parts[1]:
            return "Email domain must contain a dot"

        return True

    email = questionary.text(
        "Author email (optional - press enter to skip):",
        validate=validate_email,
    ).ask()

    capability_id = questionary.text(
        "Primary capability ID:", default=plugin_name.replace("-", "_"), validate=lambda x: x.replace("_", "").isalnum()
    ).ask()

    # Ask about coding agent memory
    coding_agent = questionary.select("Coding Agent Memory:", choices=["Claude Code", "Cursor"]).ask()

    # Ask about GitHub Actions
    include_github_actions = questionary.confirm("Include GitHub Actions? (CI/CD workflows)", default=True).ask()

    # Determine output directory
    if not output_dir:
        output_dir = Path.cwd() / plugin_name
    else:
        output_dir = Path(output_dir) / plugin_name

    if output_dir.exists():
        if not questionary.confirm(f"Directory {output_dir} exists. Overwrite?", default=False).ask():
            click.secho("Cancelled.", fg="yellow")
            return
        shutil.rmtree(output_dir)

    # Create plugin structure
    click.secho(f"\nCreating plugin in {output_dir}...", fg="green")

    try:
        # Create directories
        output_dir.mkdir(parents=True, exist_ok=True)
        src_dir = output_dir / "src" / _to_snake_case(plugin_name)
        src_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = output_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Prepare template context
        plugin_name_snake = _to_snake_case(plugin_name)
        # Generate class name, avoiding double "Plugin" suffix
        base_class_name = "".join(word.capitalize() for word in plugin_name.replace("-", "_").split("_"))
        if base_class_name.endswith("Plugin"):
            class_name = base_class_name
        else:
            class_name = base_class_name + "Plugin"
        capability_method_name = _to_snake_case(capability_id)
        context = {
            "plugin_name": plugin_name,
            "plugin_name_snake": plugin_name_snake,
            "class_name": class_name,
            "display_name": display_name,
            "description": description,
            "author": author,
            "email": email.strip() if email and email.strip() else None,
            "capability_id": capability_id,
            "capability_method_name": capability_method_name,
            "template": template,
            "coding_agent": coding_agent,
            "include_github_actions": include_github_actions,
            "agentup_version": get_version(),  # Current AgentUp version for templates
        }

        # Create pyproject.toml
        _render_and_write_template("pyproject.toml.j2", output_dir / "pyproject.toml", context)

        # Create plugin.py
        _render_and_write_template("plugin.py.j2", src_dir / "plugin.py", context)

        # Create __init__.py
        _render_and_write_template("__init__.py.j2", src_dir / "__init__.py", context)

        # Create README.md
        _render_and_write_template("README.md.j2", output_dir / "README.md", context)

        # Create basic test file
        _render_and_write_template("test_plugin.py.j2", tests_dir / f"test_{plugin_name_snake}.py", context)

        # Create .gitignore
        _render_and_write_template(".gitignore.j2", output_dir / ".gitignore", context)

        # Copy static folder to plugin root
        templates_dir = Path(__file__).parent.parent.parent / "templates" / "plugins"
        static_source = templates_dir / "static"
        static_dest = output_dir / "static"

        if static_source.exists():
            shutil.copytree(static_source, static_dest)

        # Create coding agent memory files based on selection
        if coding_agent == "Claude Code":
            _render_and_write_template("CLAUDE.md.j2", output_dir / "CLAUDE.md", context)
        elif coding_agent == "Cursor":
            cursor_rules_dir = output_dir / ".cursor" / "rules"
            cursor_rules_dir.mkdir(parents=True, exist_ok=True)
            cursor_content = f"""# AgentUp Plugin Development Rules

This is an AgentUp plugin for {display_name}.

## Plugin Architecture

- Uses decorator-based architecture with `@capability` decorator
- Entry point: `{plugin_name_snake}.plugin:{class_name}`
- Capability ID: `{capability_id}`

## Key Development Guidelines

- Always use async/await for capability methods
- Extract input using `self._extract_task_content(context)`
- Return dict with success/error status and content
- Follow modern Python typing conventions
- Use Pydantic v2 patterns

## Available Context

```python
from agent.plugins.models import CapabilityContext

context.request_id: str
context.user_id: str
context.agent_id: str
context.conversation_id: str
context.message: str
context.metadata: dict[str, Any]
```

## Testing

- Use pytest with async support
- Mock CapabilityContext for tests
- Test both success and error cases
"""
            (cursor_rules_dir / "agentup_plugin.mdc").write_text(cursor_content, encoding="utf-8")

        # Create GitHub Actions files if requested
        if include_github_actions:
            github_workflows_dir = output_dir / ".github" / "workflows"
            github_workflows_dir.mkdir(parents=True, exist_ok=True)

            # Create CI workflow
            ci_content = f"""name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{{{ matrix.python-version }}}}
      uses: actions/setup-python@v4
      with:
        python-version: ${{{{ matrix.python-version }}}}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
        pip install pytest pytest-asyncio pytest-cov

    - name: Run tests
      run: |
        pytest tests/ --cov={plugin_name_snake} --cov-report=xml --cov-report=term-missing

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      if: matrix.python-version == '3.11'
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install ruff mypy bandit
        pip install -e .

    - name: Lint with ruff
      run: |
        ruff check src/ tests/
        ruff format --check src/ tests/

    - name: Type check with mypy
      run: |
        mypy src/{plugin_name_snake}/

    - name: Security check with bandit
      run: |
        bandit -r src/{plugin_name_snake}/ -ll
"""
            (github_workflows_dir / "ci.yml").write_text(ci_content, encoding="utf-8")

            # Create security workflow
            security_content = f"""name: Security

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  security:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install bandit safety semgrep
        pip install -e .

    - name: Run bandit security linter
      run: |
        bandit -r src/{plugin_name_snake}/ -f json -o bandit-report.json
        bandit -r src/{plugin_name_snake}/ -ll

    - name: Run safety check
      run: |
        safety check

    - name: Run semgrep
      run: |
        semgrep --config=auto src/{plugin_name_snake}/

    - name: Upload security results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: security-reports
        path: |
          bandit-report.json
"""
            (github_workflows_dir / "security.yml").write_text(security_content, encoding="utf-8")

            # Create dependabot.yml
            github_dir = output_dir / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            dependabot_content = """version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "deps"
      include: "scope"
    reviewers:
      - "{author}"
    assignees:
      - "{author}"
    open-pull-requests-limit: 10
    allow:
      - dependency-type: "direct"
      - dependency-type: "indirect"
""".format(author=author.lower().replace(" ", "-") if author else "author")
            (github_dir / "dependabot.yml").write_text(dependabot_content, encoding="utf-8")

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
        click.secho("\n✓ Plugin created successfully!", fg="green")
        click.secho(f"\nLocation: {output_dir}", fg="cyan")
        click.secho("\nNext steps:", fg="yellow")
        click.secho(f"1. cd {output_dir}")
        click.secho("2. pip install -e .")
        click.secho(f"3. Edit src/{plugin_name_snake}/plugin.py")
        click.secho("4. Test with your AgentUp agent")

    except Exception as e:
        click.secho(f"[red]Error creating plugin: {e}[/red]")
        if output_dir.exists():
            shutil.rmtree(output_dir)


@plugin.command()
@click.argument("plugin_name")
@click.option("--source", "-s", type=click.Choice(["pypi", "git", "local"]), default="pypi", help="Installation source")
@click.option("--url", "-u", help="Git URL or local path (for git/local sources)")
@click.option("--force", "-f", is_flag=True, help="Force reinstall if already installed")
def install(plugin_name: str, source: str, url: str | None, force: bool):
    if source in ["git", "local"] and not url:
        click.secho(f"Error: --url is required for {source} source", fg="red")
        return

    click.secho(f"Installing plugin '{plugin_name}' from {source}...", fg="cyan")

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
            click.secho(f"[green]✓ Successfully installed {plugin_name}[/green]")
            click.secho("\nNext steps:", fg="yellow")
            click.secho("1. Restart your agent to load the new plugin")
            click.secho("2. Run agentup plugin list to verify installation", fg="cyan")
        else:
            click.secho(f"✗ Failed to install {plugin_name}", fg="red")
            click.secho(f"{result.stderr}", fg="red")

    except Exception as e:
        click.secho(f"[red]Error installing plugin: {e}[/red]")


@plugin.command()
@click.argument("plugin_name")
def uninstall(plugin_name: str):
    if not questionary.confirm(f"Uninstall plugin '{plugin_name}'?", default=False).ask():
        click.secho("Cancelled.")
        return

    click.secho(f"Uninstalling plugin '{plugin_name}'...", fg="cyan")

    try:
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y", plugin_name]
        # Bandit: Add nosec to ignore command injection risk
        # This is safe as we control the plugin_name input and it comes from trusted sources
        result = subprocess.run(cmd, capture_output=True, text=True)  # nosec

        if result.returncode == 0:
            click.secho(f"✓ Successfully uninstalled {plugin_name}", fg="green")
        else:
            click.secho(f"✗ Failed to uninstall {plugin_name}", fg="red")
            click.secho(f"{result.stderr}", fg="red")

    except Exception as e:
        click.secho(f"[red]Error uninstalling plugin: {e}[/red]")


@plugin.command()
@click.argument("plugin_name")
def reload(plugin_name: str):
    try:
        from agent.plugins.manager import get_plugin_registry

        manager = get_plugin_registry()

        if plugin_name not in manager.plugins:
            click.secho(f"Plugin '{plugin_name}' not found", fg="yellow")
            return

        click.secho(f"Reloading plugin '{plugin_name}'...", fg="cyan")

        if manager.reload_plugin(plugin_name):
            click.secho(f"✓ Successfully reloaded {plugin_name}", fg="green")
        else:
            click.secho(f"✗ Failed to reload {plugin_name}", fg="red")
            click.secho("[dim]Note: Entry point plugins cannot be reloaded[/dim]")

    except ImportError:
        click.secho("Plugin system not available.", fg="red")
    except Exception as e:
        click.secho(f"Error reloading plugin: {e}", fg="red")


@plugin.command()
@click.argument("capability_id")
def info(capability_id: str):
    try:
        from agent.plugins.manager import get_plugin_registry

        manager = get_plugin_registry()
        capability = manager.get_capability(capability_id)

        if not capability:
            click.secho(f"Capability '{capability_id}' not found", fg="yellow")
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

        console = Console()
        console.print(panel)

    except ImportError:
        click.secho("Plugin system not available.", fg="red")
    except Exception as e:
        click.secho(f"Error getting capability info: {e}", fg="red")


@plugin.command()
def validate():
    try:
        from agent.config import Config
        from agent.plugins.manager import get_plugin_registry

        manager = get_plugin_registry()

        click.secho("Validating plugins...", fg="cyan")

        # Get capability configurations
        capability_configs = {plugin.plugin_id: plugin.config or {} for plugin in Config.plugins}

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
        console = Console()
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
                issues += "Warnings: " + "; ".join(validation.warnings)

            table.add_row(capability_id, plugin, status, issues)

        console.print(table)

        if all_valid:
            click.secho("\n✓ All plugins validated successfully!", fg="green")
        else:
            click.secho("\n[red]✗ Some plugins have validation errors.[/red]")
            click.secho("Please check your agentup.yml and fix the issues.")

    except ImportError:
        click.secho("[red]Plugin system not available.[/red]")
    except Exception as e:
        click.secho(f"[red]Error validating plugins: {e}[/red]")
