import os
import re
from pathlib import Path
from typing import Any

import click
import yaml


@click.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), default="agent_config.yaml", help="Path to agent configuration file"
)
@click.option("--check-env", "-e", is_flag=True, help="Check environment variables")
@click.option("--check-handlers", "-h", is_flag=True, help="Check handler implementations")
@click.option("--strict", "-s", is_flag=True, help="Strict validation (fail on warnings)")
def validate(config: str, check_env: bool, check_handlers: bool, strict: bool):
    """Validate your agent configuration.

    Checks for:
    - Valid YAML syntax
    - Required fields
    - Plugin definitions
    - Service configurations
    - System prompt configuration
    - Plugin system prompts
    - Environment variables (with --check-env)
    - Handler implementations (with --check-handlers)
    """
    click.echo(click.style(f"Validating {config}...\n", fg="bright_blue", bold=True))

    errors = []
    warnings = []

    # Load and parse YAML
    config_data = load_yaml_config(config, errors)
    if not config_data:
        display_results(errors, warnings)
        return

    # Validate structure
    validate_required_fields(config_data, errors, warnings)
    validate_agent_section(config_data.get("agent", {}), errors, warnings)
    validate_plugins_section(config_data.get("plugins", []), errors, warnings)

    # Validate routing configuration
    if "routing" in config_data:
        validate_routing_section(config_data["routing"], errors, warnings)

    # Validate AI configuration against plugins requirements
    validate_ai_requirements(config_data, errors, warnings)

    # Optional validations
    if "services" in config_data:
        validate_services_section(config_data["services"], errors, warnings)

    if "security" in config_data:
        validate_security_section(config_data["security"], errors, warnings)

    if "middleware" in config_data:
        validate_middleware_section(config_data["middleware"], errors, warnings)

    # Validate AI system prompt configuration
    if "ai" in config_data:
        validate_system_prompt_section(config_data["ai"], errors, warnings)

    # Validate plugin system prompts in plugins
    validate_plugin_system_prompts(config_data.get("plugins", []), errors, warnings)

    # Check environment variables
    if check_env:
        check_environment_variables(config_data, errors, warnings)

    # Check handler implementations
    if check_handlers:
        check_handler_implementations(config_data.get("plugins", []), errors, warnings)

    # Display results
    display_results(errors, warnings, strict)


def load_yaml_config(config_path: str, errors: list[str]) -> dict[str, Any] | None:
    """Load and parse YAML configuration."""
    try:
        with open(config_path) as f:
            content = f.read()

        # Check for common YAML issues
        if "\t" in content:
            errors.append("YAML files should not contain tabs. Use spaces for indentation.")

        config = yaml.safe_load(content)

        if not isinstance(config, dict):
            errors.append("Configuration must be a YAML dictionary/object")
            return None

        click.echo(f"{click.style('✓', fg='green')} Valid YAML syntax")
        return config

    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML syntax: {str(e)}")
        return None
    except Exception as e:
        errors.append(f"Error reading configuration: {str(e)}")
        return None


def validate_required_fields(config: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate required top-level fields."""
    required_fields = ["agent", "plugins"]

    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: '{field}'")
        elif not config[field]:
            errors.append(f"Required field '{field}' is empty")

    # Check for unknown top-level fields
    known_fields = {
        "agent",
        "plugins",
        "routing",
        "services",
        "security",
        "ai",
        "ai_provider",
        "mcp",
        "middleware",
        "monitoring",
        "observability",
        "development",
        "registry_plugins",
        "push_notifications",
        "state",
        "cache",
    }
    unknown_fields = set(config.keys()) - known_fields

    if unknown_fields:
        warnings.append(f"Unknown configuration fields: {', '.join(unknown_fields)}")


def validate_agent_section(agent: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate agent section."""
    if not agent:
        return

    required_agent_fields = ["name", "description"]

    for field in required_agent_fields:
        if field not in agent:
            errors.append(f"Missing required agent field: 'agent.{field}'")
        elif not agent[field]:
            errors.append(f"Agent field 'agent.{field}' is empty")

    # Validate version format if present
    if "version" in agent:
        version = agent["version"]
        if not re.match(r"^\d+\.\d+\.\d+", str(version)):
            warnings.append(f"Agent version '{version}' doesn't follow semantic versioning (x.y.z)")

    click.echo(f"{click.style('✓', fg='green')} Agent configuration valid")


def validate_plugins_section(plugins: list[dict[str, Any]], errors: list[str], warnings: list[str]):
    """Validate plugins section."""
    if not plugins:
        errors.append("No plugins defined. At least one plugin is required.")
        return

    if not isinstance(plugins, list):
        errors.append("Plugins must be a list")
        return

    plugin_ids = set()

    for i, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            errors.append(f"Plugin {i} must be a dictionary")
            continue

        # Required plugin fields
        required_plugin_fields = ["plugin_id", "name", "description"]

        for field in required_plugin_fields:
            if field not in plugin:
                errors.append(f"Plugin {i} missing required field: '{field}'")
            elif not plugin[field]:
                errors.append(f"Plugin {i} field '{field}' is empty")

        # Check for duplicate plugin IDs
        plugin_id = plugin.get("plugin_id")
        if plugin_id:
            if plugin_id in plugin_ids:
                errors.append(f"Duplicate plugin ID: '{plugin_id}'")
            else:
                plugin_ids.add(plugin_id)

            # Validate plugin ID format
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", plugin_id):
                errors.append(
                    f"Invalid plugin ID '{plugin_id}'. Must start with letter and contain only letters, numbers, and underscores."
                )

        # Validate routing configuration
        routing_mode = plugin.get("routing_mode")
        if routing_mode and routing_mode not in ["ai", "direct"]:
            errors.append(f"Plugin {i} has invalid routing_mode '{routing_mode}'. Must be 'ai' or 'direct'")

        # For direct routing, check that keywords or patterns are provided
        if routing_mode == "direct":
            keywords = plugin.get("keywords", [])
            patterns = plugin.get("patterns", [])
            if not keywords and not patterns:
                warnings.append(f"Plugin {i} uses direct routing but has no keywords or patterns defined")

            # Validate regex patterns
            for pattern in patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    errors.append(f"Plugin {i} has invalid regex pattern '{pattern}': {e}")

        # Validate input/output modes
        input_mode = plugin.get("input_mode", "text")
        output_mode = plugin.get("output_mode", "text")
        valid_modes = ["text", "multimodal"]

        if input_mode not in valid_modes:
            errors.append(f"Plugin {i} has invalid input_mode '{input_mode}'. Must be one of: {valid_modes}")
        if output_mode not in valid_modes:
            errors.append(f"Plugin {i} has invalid output_mode '{output_mode}'. Must be one of: {valid_modes}")

        # Validate middleware if present (deprecated in favor of middleware_override)
        if "middleware" in plugin:
            warnings.append(
                f"Plugin '{plugin_id}' uses deprecated 'middleware' field. Use 'middleware_override' instead."
            )
            validate_middleware_config(plugin["middleware"], plugin_id, errors, warnings)

        # Validate middleware_override if present
        if "middleware_override" in plugin:
            validate_middleware_config(plugin["middleware_override"], plugin_id, errors, warnings)

    click.echo(f"{click.style('✓', fg='green')} Found {len(plugins)} plugin(s)")


def validate_middleware_config(
    middleware: list[dict[str, Any]], plugin_id: str, errors: list[str], warnings: list[str]
):
    """Validate middleware configuration."""
    if not isinstance(middleware, list):
        errors.append(f"Plugin '{plugin_id}' middleware must be a list")
        return

    valid_middleware_types = {"rate_limit", "cache", "validation", "retry", "logging", "timing", "transform"}

    for mw in middleware:
        if not isinstance(mw, dict):
            errors.append(f"Plugin '{plugin_id}' middleware entry must be a dictionary")
            continue

        if "type" not in mw:
            errors.append(f"Plugin '{plugin_id}' middleware missing 'type' field")
            continue

        mw_type = mw["type"]
        if mw_type not in valid_middleware_types:
            warnings.append(f"Plugin '{plugin_id}' has unknown middleware type: '{mw_type}'")

        # Validate specific middleware configurations
        if mw_type == "rate_limit" and "requests_per_minute" in mw:
            try:
                rpm = int(mw["requests_per_minute"])
                if rpm <= 0:
                    errors.append(f"Plugin '{plugin_id}' rate limit must be positive")
            except (ValueError, TypeError):
                errors.append(f"Plugin '{plugin_id}' rate limit must be a number")

        if mw_type == "cache" and "ttl" in mw:
            try:
                ttl = int(mw["ttl"])
                if ttl <= 0:
                    errors.append(f"Plugin '{plugin_id}' cache TTL must be positive")
            except (ValueError, TypeError):
                errors.append(f"Plugin '{plugin_id}' cache TTL must be a number")


def validate_services_section(services: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate services configuration."""
    if not isinstance(services, dict):
        errors.append("Services must be a dictionary")
        return

    for service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            errors.append(f"Service '{service_name}' configuration must be a dictionary")
            continue

        if "type" not in service_config:
            errors.append(f"Service '{service_name}' missing 'type' field")

        if "config" not in service_config:
            warnings.append(f"Service '{service_name}' has no configuration")

        # Validate specific service types
        service_type = service_config.get("type")

        if service_type == "database":
            if "config" in service_config:
                db_config = service_config["config"]
                if "url" not in db_config and "connection_string" not in db_config:
                    warnings.append(f"Database service '{service_name}' missing connection configuration")

    click.echo(f"{click.style('✓', fg='green')} Services configuration valid")


def validate_security_section(security: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate security configuration."""
    if not isinstance(security, dict):
        errors.append("Security must be a dictionary")
        return

    if "type" not in security:
        errors.append("Security configuration missing 'type' field")
        return

    security_type = security["type"]
    valid_types = {"api_key", "jwt", "oauth2", "basic", "custom"}

    if security_type not in valid_types:
        warnings.append(f"Unknown security type: '{security_type}'")

    # Validate specific security configurations
    if security_type == "jwt" and "config" in security:
        jwt_config = security["config"]
        if "secret" not in jwt_config and "secret_key" not in jwt_config:
            errors.append("JWT security missing secret key configuration")

    click.echo(f"{click.style('✓', fg='green')} Security configuration valid")


def check_environment_variables(config: dict[str, Any], errors: list[str], warnings: list[str]):
    """Check for environment variables referenced in the configuration."""
    env_var_pattern = re.compile(r"\$\{([^:}]+)(?::([^}]+))?\}")
    missing_vars = []

    def check_value(value: Any, path: str = ""):
        """Recursively check for environment variables."""
        if isinstance(value, str):
            matches = env_var_pattern.findall(value)
            for var_name, default in matches:
                if not os.getenv(var_name) and not default:
                    missing_vars.append((var_name, path))
        elif isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{path}.{k}" if path else k)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(item, f"{path}[{i}]")

    check_value(config)

    if missing_vars:
        click.echo(f"\n{click.style('🔍 Environment Variables:', fg='yellow')}")
        for var_name, path in missing_vars:
            warnings.append(f"Missing environment variable '{var_name}' referenced in {path}")
    else:
        click.echo(f"{click.style('✓', fg='green')} All environment variables present or have defaults")


def check_handler_implementations(plugins: list[dict[str, Any]], errors: list[str], warnings: list[str]):
    """Check if handler implementations exist."""
    handlers_path = Path("src/agent/handlers.py")

    if not handlers_path.exists():
        errors.append("handlers.py not found at src/agent/handlers.py")
        return

    try:
        with open(handlers_path) as f:
            handlers_content = f.read()

        click.echo(f"\n{click.style('🔍 Handler Implementations:', fg='yellow')}")

        for plugin in plugins:
            plugin_id = plugin.get("plugin_id")
            if not plugin_id:
                continue

            # Check for handler registration
            if f'@register_handler("{plugin_id}")' in handlers_content:
                click.echo(f"{click.style('✓', fg='green')} Handler found for '{plugin_id}'")
            else:
                warnings.append(f"No handler implementation found for plugin '{plugin_id}'")

            # Check for handler function
            if f"def handle_{plugin_id}" not in handlers_content:
                warnings.append(f"Handler function 'handle_{plugin_id}' not found")

    except Exception as e:
        errors.append(f"Error checking handlers: {str(e)}")


def validate_routing_section(routing: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate routing configuration section."""
    if not isinstance(routing, dict):
        errors.append("Routing configuration must be a dictionary")
        return

    # Validate default_mode
    default_mode = routing.get("default_mode", "ai")
    if default_mode not in ["ai", "direct"]:
        errors.append(f"Invalid routing default_mode '{default_mode}'. Must be 'ai' or 'direct'")

    click.echo(f"{click.style('✓', fg='green')} Routing configuration valid")


def validate_ai_requirements(config: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate AI configuration requirements based on plugins."""
    plugins = config.get("plugins", [])
    routing = config.get("routing", {})
    ai_config = config.get("ai", {})
    services = config.get("services", {})

    # Check if any plugin requires AI routing
    default_mode = routing.get("default_mode", "ai")

    needs_ai = False

    for plugin in plugins:
        plugin_routing_mode = plugin.get("routing_mode", default_mode)
        if plugin_routing_mode == "ai":
            needs_ai = True
            break

    if needs_ai:
        # AI is required, validate AI configuration
        if not ai_config.get("enabled", True):
            errors.append("AI routing is required by plugins but ai.enabled is false")

        # Check that at least one LLM service is configured
        llm_services = []
        for service_name, service_config in services.items():
            if service_config.get("type") == "llm":
                llm_services.append(service_name)

        if not llm_services:
            errors.append("AI routing is required but no LLM services are configured in services section")

        # Check that ai.llm_service points to a valid service
        llm_service = ai_config.get("llm_service")
        if llm_service and llm_service not in llm_services:
            errors.append(f"AI configuration references llm_service '{llm_service}' but it's not defined in services")

    elif ai_config.get("enabled", False):
        warnings.append(
            "AI is enabled but no plugins use AI routing. Consider disabling AI or adding AI-routed plugins"
        )

    click.echo(f"{click.style('✓', fg='green')} AI requirements validated")


def validate_system_prompt_section(ai_config: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate system prompt configuration."""
    if not isinstance(ai_config, dict):
        return

    system_prompt = ai_config.get("system_prompt")
    if not system_prompt:
        return  # System prompt is optional

    if not isinstance(system_prompt, str):
        errors.append("AI system_prompt must be a string")
        return

    # Validate prompt length
    if len(system_prompt) < 10:
        warnings.append("System prompt is very short (< 10 characters)")
    elif len(system_prompt) > 8000:
        warnings.append("System prompt is very long (> 8000 characters) - may impact performance")

    # Check for common prompt injection patterns
    dangerous_patterns = [
        "ignore previous instructions",
        "disregard",
        "forget everything",
        "jailbreak",
        "developer mode",
    ]

    prompt_lower = system_prompt.lower()
    for pattern in dangerous_patterns:
        if pattern in prompt_lower:
            warnings.append(f"System prompt contains potentially risky pattern: '{pattern}'")

    # Validate prompt structure
    if not any(word in prompt_lower for word in ["you are", "your role", "assistant", "help"]):
        warnings.append("System prompt may lack clear role definition")

    click.echo(f"{click.style('✓', fg='green')} System prompt validated")


def validate_plugin_system_prompts(plugins: list[dict[str, Any]], errors: list[str], warnings: list[str]):
    """Validate plugin system prompts."""
    plugin_prompt_count = 0

    for i, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            continue

        plugin_id = plugin.get("plugin_id", f"plugin_{i}")

        # Check if plugin has plugin-specific system prompt
        if "system_prompt" in plugin:
            plugin_prompt_count += 1
            system_prompt = plugin["system_prompt"]

            if not isinstance(system_prompt, str):
                errors.append(f"Plugin '{plugin_id}' system_prompt must be a string")
                continue

            # Validate length
            if len(system_prompt) < 10:
                warnings.append(f"Plugin '{plugin_id}' system prompt is very short")
            elif len(system_prompt) > 4000:
                warnings.append(f"Plugin '{plugin_id}' system prompt is very long - may impact performance")

            # Check for plugin-specific guidance
            prompt_lower = system_prompt.lower()
            plugin_name_lower = plugin.get("name", plugin_id).lower()
            if plugin_name_lower not in prompt_lower and plugin_id.lower() not in prompt_lower:
                warnings.append(f"Plugin '{plugin_id}' system prompt may lack plugin-specific guidance")

    if plugin_prompt_count > 0:
        click.echo(f"{click.style('✓', fg='green')} Plugin system prompts validated ({plugin_prompt_count} found)")
    else:
        click.echo(f"{click.style('✓', fg='green')} No plugin system prompts found")


def validate_middleware_section(middleware: list[dict[str, Any]], errors: list[str], warnings: list[str]):
    """Validate global middleware configuration."""
    if not isinstance(middleware, list):
        errors.append("Middleware section must be a list")
        return

    valid_middleware_names = {"timed", "cached", "rate_limited", "retryable", "validated"}

    for i, middleware_config in enumerate(middleware):
        if not isinstance(middleware_config, dict):
            errors.append(f"Middleware item {i} must be an object")
            continue

        if "name" not in middleware_config:
            errors.append(f"Middleware item {i} missing required 'name' field")
            continue

        middleware_name = middleware_config["name"]
        if middleware_name not in valid_middleware_names:
            warnings.append(
                f"Unknown middleware '{middleware_name}' in global config. Valid options: {', '.join(valid_middleware_names)}"
            )

        # Validate specific middleware parameters
        params = middleware_config.get("params", {})
        if middleware_name == "cached" and "ttl" in params:
            if not isinstance(params["ttl"], int) or params["ttl"] <= 0:
                errors.append("Cached middleware 'ttl' parameter must be a positive integer")

        elif middleware_name == "rate_limited" and "requests_per_minute" in params:
            if not isinstance(params["requests_per_minute"], int) or params["requests_per_minute"] <= 0:
                errors.append("Rate limited middleware 'requests_per_minute' parameter must be a positive integer")

    click.echo(
        f"{click.style('✓', fg='green')} Middleware configuration validated ({len(middleware)} middleware items)"
    )


def display_results(errors: list[str], warnings: list[str], strict: bool = False):
    """Display validation results."""
    click.echo(f"\n{click.style('Validation Results:', fg='bright_blue', bold=True)}")

    if errors:
        click.echo(f"\n{click.style('❌ Errors:', fg='red', bold=True)}")
        for error in errors:
            click.echo(f"  • {error}")

    if warnings:
        click.echo(f"\n{click.style('⚠️  Warnings:', fg='yellow', bold=True)}")
        for warning in warnings:
            click.echo(f"  • {warning}")

    if not errors and not warnings:
        click.echo(f"\n{click.style('✅ Configuration is valid!', fg='green', bold=True)}")
        click.echo("Your agent configuration passed all validation checks.")
    elif not errors:
        click.echo(f"\n{click.style('✅ Configuration is valid with warnings', fg='green')}")
        if strict:
            click.echo(f"{click.style('❌ Failed strict validation due to warnings', fg='red')}")
            exit(1)
    else:
        click.echo(f"\n{click.style('❌ Configuration is invalid', fg='red', bold=True)}")
        click.echo(f"Found {len(errors)} error(s) and {len(warnings)} warning(s)")
        exit(1)
