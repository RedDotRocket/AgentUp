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

console = Console()

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


@click.group()
def plugin():
    pass


@plugin.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plugin information and logging")
@click.option("--capabilities", "-c", is_flag=True, help="Show available capabilities/AI functions")
@click.option("--format", "-f", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--debug", is_flag=True, help="Show debug logging output")
def list_plugins(verbose: bool, capabilities: bool, format: str, debug: bool):
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

                        all_ai_functions.append(
                            {
                                "name": func.name,
                                "description": func.description,
                                "parameters": param_names,
                                "plugin": plugin_name,
                                "capability_id": capability.id,
                            }
                        )

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
                        row.append(
                            func["description"][:80] + "..." if len(func["description"]) > 80 else func["description"]
                        )

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
    console.print("[bold cyan]AgentUp Plugin Creator[/bold cyan]")
    console.print("Let's create a new plugin!\n")

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
            console.print("Cancelled.")
            return

    # Normalize plugin name
    plugin_name = plugin_name.lower().replace(" ", "-")

    # Validate the name even if provided via CLI
    is_valid, error_msg = _validate_plugin_name(plugin_name)
    if not is_valid:
        console.print(f"[red]Error: {error_msg}[/red]")
        return

    # Get plugin details
    display_name = questionary.text("Display name:", default=plugin_name.replace("-", " ").title()).ask()

    description = questionary.text("Description:", default=f"A plugin that provides {display_name} functionality").ask()

    author = questionary.text("Author name:").ask()

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
            console.print("Cancelled.")
            return
        shutil.rmtree(output_dir)

    # Create plugin structure
    console.print(f"\n[cyan]Creating plugin in {output_dir}...[/cyan]")

    try:
        # Create directories
        output_dir.mkdir(parents=True, exist_ok=True)
        src_dir = output_dir / "src" / _to_snake_case(plugin_name)
        src_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = output_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Prepare template context
        plugin_name_snake = _to_snake_case(plugin_name)
        context = {
            "plugin_name": plugin_name,
            "plugin_name_snake": plugin_name_snake,
            "display_name": display_name,
            "description": description,
            "author": author,
            "capability_id": capability_id,
            "template": template,
            "coding_agent": coding_agent,
            "include_github_actions": include_github_actions,
        }

        # Create pyproject.toml
        pyproject_content = _render_plugin_template("pyproject.toml.j2", context)
        (output_dir / "pyproject.toml").write_text(pyproject_content)

        # Create plugin.py
        plugin_code = _render_plugin_template("plugin.py.j2", context)
        (src_dir / "plugin.py").write_text(plugin_code)

        # Create __init__.py
        init_content = _render_plugin_template("__init__.py.j2", context)
        (src_dir / "__init__.py").write_text(init_content)

        # Create README.md
        readme_content = _render_plugin_template("README.md.j2", context)
        (output_dir / "README.md").write_text(readme_content)

        # Create test file
        test_content = _render_plugin_template("test_plugin.py.j2", context)
        (tests_dir / f"test_{plugin_name_snake}.py").write_text(test_content)

        # Create .gitignore
        gitignore_content = _render_plugin_template(".gitignore.j2", context)
        (output_dir / ".gitignore").write_text(gitignore_content)

        # Copy static folder to plugin root
        templates_dir = Path(__file__).parent.parent.parent / "templates" / "plugins"
        static_source = templates_dir / "static"
        static_dest = output_dir / "static"

        if static_source.exists():
            shutil.copytree(static_source, static_dest)

        # Create coding agent memory files based on selection
        if coding_agent == "Claude Code":
            claude_md_content = _render_plugin_template("CLAUDE.md.j2", context)
            (output_dir / "CLAUDE.md").write_text(claude_md_content)
        elif coding_agent == "Cursor":
            cursor_rules_dir = output_dir / ".cursor" / "rules"
            cursor_rules_dir.mkdir(parents=True, exist_ok=True)
            cursor_content = _render_plugin_template(".cursor/rules/agentup_plugin.mdc.j2", context)
            (cursor_rules_dir / "agentup_plugin.mdc").write_text(cursor_content)

        # Create GitHub Actions files if requested
        if include_github_actions:
            github_workflows_dir = output_dir / ".github" / "workflows"
            github_workflows_dir.mkdir(parents=True, exist_ok=True)

            # Create CI workflow
            ci_content = _render_plugin_template(".github/workflows/ci.yml.j2", context)
            (github_workflows_dir / "ci.yml").write_text(ci_content)

            # Create security workflow
            security_content = _render_plugin_template(".github/workflows/security.yml.j2", context)
            (github_workflows_dir / "security.yml").write_text(security_content)

            # Create dependabot.yml
            github_dir = output_dir / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            dependabot_content = _render_plugin_template(".github/dependabot.yml.j2", context)
            (github_dir / "dependabot.yml").write_text(dependabot_content)

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
        console.print("\n[green]✓ Plugin created successfully![/green]")
        console.print(f"\nLocation: [cyan]{output_dir}[/cyan]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"1. cd {output_dir}")
        console.print("2. pip install -e .")
        console.print(f"3. Edit src/{plugin_name_snake}/plugin.py")
        console.print("4. Test with your AgentUp agent")

    except Exception as e:
        console.print(f"[red]Error creating plugin: {e}[/red]")
        if output_dir.exists():
            shutil.rmtree(output_dir)


@plugin.command()
@click.argument("plugin_name")
@click.option("--source", "-s", type=click.Choice(["pypi", "git", "local"]), default="pypi", help="Installation source")
@click.option("--url", "-u", help="Git URL or local path (for git/local sources)")
@click.option("--force", "-f", is_flag=True, help="Force reinstall if already installed")
def install(plugin_name: str, source: str, url: str | None, force: bool):
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
            console.print(f"[green]✓ Successfully installed {plugin_name}[/green]")
            console.print("\n[bold]Next steps:[/bold]")
            console.print("1. Restart your agent to load the new plugin")
            console.print("2. Run [cyan]agentup plugin list[/cyan] to verify installation")
        else:
            console.print(f"[red]✗ Failed to install {plugin_name}[/red]")
            console.print(f"[red]{result.stderr}[/red]")

    except Exception as e:
        console.print(f"[red]Error installing plugin: {e}[/red]")


@plugin.command()
@click.argument("plugin_name")
def uninstall(plugin_name: str):
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
            console.print(f"[green]✓ Successfully uninstalled {plugin_name}[/green]")
        else:
            console.print(f"[red]✗ Failed to uninstall {plugin_name}[/red]")
            console.print(f"[red]{result.stderr}[/red]")

    except Exception as e:
        console.print(f"[red]Error uninstalling plugin: {e}[/red]")


@plugin.command()
@click.argument("plugin_name")
def reload(plugin_name: str):
    try:
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()

        if plugin_name not in manager.plugins:
            console.print(f"[yellow]Plugin '{plugin_name}' not found[/yellow]")
            return

        console.print(f"[cyan]Reloading plugin '{plugin_name}'...[/cyan]")

        if manager.reload_plugin(plugin_name):
            console.print(f"[green]✓ Successfully reloaded {plugin_name}[/green]")
        else:
            console.print(f"[red]✗ Failed to reload {plugin_name}[/red]")
            console.print("[dim]Note: Entry point plugins cannot be reloaded[/dim]")

    except ImportError:
        console.print("[red]Plugin system not available.[/red]")
    except Exception as e:
        console.print(f"[red]Error reloading plugin: {e}[/red]")


@plugin.command()
@click.argument("capability_id")
def info(capability_id: str):
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
    try:
        from agent.config import Config
        from agent.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()

        console.print("[cyan]Validating plugins...[/cyan]\n")

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
            console.print("\n[green]✓ All plugins validated successfully![/green]")
        else:
            console.print("\n[red]✗ Some plugins have validation errors.[/red]")
            console.print("Please check your agentup.yml and fix the issues.")

    except ImportError:
        console.print("[red]Plugin system not available.[/red]")
    except Exception as e:
        console.print(f"[red]Error validating plugins: {e}[/red]")
