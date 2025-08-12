import shutil
import subprocess  # nosec
from pathlib import Path

import click
import questionary
import structlog
from jinja2 import Environment, FileSystemLoader

from agent.utils.version import get_version

logger = structlog.get_logger(__name__)

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


@click.command()
@click.argument("plugin_name", required=False)
@click.option("--template", "-t", type=click.Choice(["direct", "ai"]), default="direct", help="Plugin template")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory for the plugin")
@click.option("--no-git", is_flag=True, help="Skip git initialization")
def create(plugin_name: str | None, template: str, output_dir: str | None, no_git: bool):
    """Create a new AgentUp plugin with scaffolding."""
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
