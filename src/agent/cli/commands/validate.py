import os
import re
from pathlib import Path
from typing import Any

import click
import yaml


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default="agentup.yml",
    help="Path to agent configuration file",
)
@click.option("--check-env", "-e", is_flag=True, help="Check environment variables")
@click.option("--check-handlers", "-h", is_flag=True, help="Check handler implementations")
@click.option("--strict", "-s", is_flag=True, help="Strict validation (fail on warnings)")
def validate(config: str, check_env: bool, check_handlers: bool, strict: bool):
    """Validate your agent configuration and setup.

    Checks for:
    - Valid YAML syntax
    - Required fields
    - API version compatibility
    - Plugin configurations and overrides
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

    # Validate API version compatibility
    validate_api_version(config_data, errors, warnings)

    # Validate structure
    validate_required_fields(config_data, errors, warnings)
    validate_agent_section(config_data, errors, warnings)

    # Validate new unified plugin configuration
    validate_unified_plugins_section(config_data, errors, warnings)

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

    # Check environment variables
    if check_env:
        check_environment_variables(config_data, errors, warnings)

    # Check handler implementations
    if check_handlers:
        check_handler_implementations(config_data.get("plugins", []), errors, warnings)

    # Display results
    display_results(errors, warnings, strict)


def load_yaml_config(config_path: str, errors: list[str]) -> dict[str, Any] | None:
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
    # Check for new flat format (name, description at top level) or old nested format (agent section)
    has_old_format = "agent" in config
    has_new_format = "name" in config and "description" in config

    if not has_old_format and not has_new_format:
        errors.append("Missing required fields: either 'agent' section or top-level 'name' and 'description'")

    # Plugins are always required
    if "plugins" not in config:
        errors.append("Missing required field: 'plugins'")
    elif not config["plugins"]:
        errors.append("Required field 'plugins' is empty")

    # Check for unknown top-level fields
    known_fields = {
        # Old nested format
        "agent",
        # New flat format - top-level agent info
        "name",
        "description",
        "version",
        # Common sections
        "plugins",
        "services",
        "security",
        "ai",
        "ai_provider",
        "mcp",
        "middleware",
        "monitoring",
        "observability",
        "development",
        "push_notifications",
        "state_management",
        "cache",
        "logging",
    }
    unknown_fields = set(config.keys()) - known_fields

    if unknown_fields:
        warnings.append(f"Unknown configuration fields: {', '.join(unknown_fields)}")


def validate_agent_section(config: dict[str, Any], errors: list[str], warnings: list[str]):
    # Check if using old nested format
    if "agent" in config:
        agent = config["agent"]
        if not agent:
            return
        required_agent_fields = ["name", "description"]
        for field in required_agent_fields:
            if field not in agent:
                errors.append(f"Missing required agent field: '{field}'")
            elif not agent[field] or not str(agent[field]).strip():
                errors.append(f"Agent field '{field}' is empty")
    else:
        # New flat format - check top-level fields
        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: '{field}'")
            elif not config[field] or not str(config[field]).strip():
                errors.append(f"Field '{field}' is empty")

    # Validate version format if present (check both old and new formats)
    version = None
    if "agent" in config and "version" in config["agent"]:
        version = config["agent"]["version"]
    elif "version" in config:
        version = config["version"]

    if version and not re.match(r"^\d+\.\d+\.\d+", str(version)):
        warnings.append(f"Version '{version}' doesn't follow semantic versioning (x.y.z)")


def validate_plugins_section(plugins: list[dict[str, Any]], errors: list[str], warnings: list[str]):
    if not plugins:
        errors.append("No plugins defined. At least one plugin is required.")
        return

    if not isinstance(plugins, list):
        errors.append("Plugins must be a list")
        return

    for i, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            errors.append(f"Plugin {i} must be a dictionary")
            continue

        # Required plugin fields (legacy format)
        required_plugin_fields = ["name", "description", "package"]

        for field in required_plugin_fields:
            if field not in plugin:
                if field == "package":
                    errors.append(f"Plugin {i} missing required field: '{field}' (needed for plugin system security)")
                else:
                    errors.append(f"Plugin {i} missing required field: '{field}'")
            elif not plugin[field]:
                errors.append(f"Plugin {i} field '{field}' is empty")

        # Validate package name format (PyPI naming conventions)
        package_name = plugin.get("package")
        if package_name:
            if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$", package_name):
                errors.append(
                    f"Invalid package name '{package_name}' for plugin {i}. Must follow PyPI naming conventions (letters, numbers, dots, hyphens, underscores)."
                )
            # Warn about common naming issues
            if package_name.startswith("-") or package_name.endswith("-"):
                errors.append(f"Package name '{package_name}' cannot start or end with hyphen")
            if package_name.startswith(".") or package_name.endswith("."):
                errors.append(f"Package name '{package_name}' cannot start or end with dot")
            if "__" in package_name:
                warnings.append(f"Package name '{package_name}' contains double underscores, which may cause issues")

        # Validate regex patterns (if provided for capability detection)
        patterns = plugin.get("patterns", [])
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
        plugin_name = plugin.get("name", f"plugin_{i}")
        if "middleware" in plugin:
            warnings.append(
                f"Plugin '{plugin_name}' uses deprecated 'middleware' field. Use 'middleware_override' instead."
            )
            validate_middleware_config(plugin["middleware"], plugin_name, errors, warnings)

        # Validate plugin_override if present
        if "plugin_override" in plugin:
            validate_middleware_config(plugin["plugin_override"], plugin_name, errors, warnings)

    click.echo(f"{click.style('✓', fg='green')} Found {len(plugins)} plugin(s)")


def validate_api_version(config_data: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate API version compatibility."""
    api_version = config_data.get("apiVersion")

    if not api_version:
        warnings.append("Missing 'apiVersion' field. Recommend adding 'apiVersion: v1' for future compatibility.")
        return

    supported_versions = ["v1"]
    if api_version not in supported_versions:
        errors.append(f"Unsupported apiVersion '{api_version}'. Supported versions: {', '.join(supported_versions)}")
    else:
        click.echo(f"{click.style('✓', fg='green')} API version {api_version} is supported")


def _validate_dictionary_plugins(plugins: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate plugins in new dictionary format."""
    package_names = set()

    for package_name, plugin_config in plugins.items():
        # Validate package name (dictionary key)
        if not package_name:
            errors.append("Empty package name in plugins dictionary")
            continue

        # Check for duplicate packages (shouldn't happen in dict, but check anyway)
        if package_name in package_names:
            errors.append(f"Duplicate package: '{package_name}'")
        else:
            package_names.add(package_name)

        # Validate package name format (PyPI naming conventions)
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$", package_name):
            errors.append(f"Invalid package name '{package_name}'. Must follow PyPI naming conventions.")

        # Plugin config should be a dictionary or Pydantic model
        if not isinstance(plugin_config, dict | object):
            errors.append(f"Plugin '{package_name}' configuration must be a dictionary")
            continue

        # Package name serves as the identifier (no separate plugin_id needed)

        # Validate enabled field
        enabled = True  # default
        if hasattr(plugin_config, "enabled"):
            enabled = plugin_config.enabled
        elif isinstance(plugin_config, dict):
            enabled = plugin_config.get("enabled", True)

        if not isinstance(enabled, bool):
            errors.append(f"Plugin '{package_name}' 'enabled' field must be boolean")

        # Validate capabilities if present
        capabilities = None
        if hasattr(plugin_config, "capabilities"):
            capabilities = plugin_config.capabilities
        elif isinstance(plugin_config, dict):
            capabilities = plugin_config.get("capabilities")

        if capabilities:
            validate_capability_overrides(capabilities, f"plugin '{package_name}'", errors, warnings)

        # Validate plugin-level config
        config_value = None
        if hasattr(plugin_config, "config"):
            config_value = plugin_config.config
        elif isinstance(plugin_config, dict):
            config_value = plugin_config.get("config")

        if config_value and not isinstance(config_value, dict):
            errors.append(f"Plugin '{package_name}' 'config' field must be a dictionary")

    click.echo(f"{click.style('✓', fg='green')} Found {len(plugins)} plugin(s) in dictionary format")


def validate_unified_plugins_section(config_data: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate the new unified plugin configuration structure."""
    plugins = config_data.get("plugins", [])
    plugin_defaults = config_data.get("plugin_defaults", {})
    global_defaults = config_data.get("global_defaults", {})

    # Validate plugin defaults
    if plugin_defaults:
        validate_plugin_defaults(plugin_defaults, errors, warnings)

    # Validate global defaults
    if global_defaults:
        validate_global_defaults(global_defaults, errors, warnings)

    # Handle both old list format and new dictionary format
    if isinstance(plugins, list):
        # Old list format - validate using legacy method
        if plugins and len(plugins) > 0:
            first_plugin = plugins[0]
            if isinstance(first_plugin, dict) and "name" in first_plugin:
                warnings.append(
                    "Detected old plugin configuration format. Consider migrating to unified plugin format."
                )
                validate_plugins_section(plugins, errors, warnings)
                return

        # Empty list
        if not plugins:
            warnings.append("No plugins configured. Consider adding plugins to extend functionality.")
            return

    elif isinstance(plugins, dict):
        # New dictionary format - validate keys and values
        if not plugins:
            warnings.append("No plugins configured. Consider adding plugins to extend functionality.")
            return

        # Validate each plugin in dictionary format
        _validate_dictionary_plugins(plugins, errors, warnings)
        return

    else:
        errors.append("Plugins must be a list (legacy format) or dictionary (new format)")
        return

    # This function should not be reached for new dictionary format
    # It's handled by _validate_dictionary_plugins now
    click.echo(f"{click.style('✓', fg='green')} Found {len(plugins)} plugin(s) in legacy format")


def validate_plugin_defaults(plugin_defaults: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate plugin defaults configuration."""
    middleware = plugin_defaults.get("middleware", {})

    if middleware and not isinstance(middleware, dict):
        errors.append("plugin_defaults.middleware must be a dictionary")
        return

    # Validate middleware configurations
    for middleware_name, middleware_config in middleware.items():
        if not isinstance(middleware_config, dict):
            errors.append(f"plugin_defaults.middleware.{middleware_name} must be a dictionary")
            continue

        # Validate common middleware types
        if middleware_name == "rate_limited":
            validate_rate_limit_config(
                middleware_config, f"plugin_defaults.middleware.{middleware_name}", errors, warnings
            )
        elif middleware_name == "cached":
            validate_cache_config(middleware_config, f"plugin_defaults.middleware.{middleware_name}", errors, warnings)
        elif middleware_name == "retryable":
            validate_retry_config(middleware_config, f"plugin_defaults.middleware.{middleware_name}", errors, warnings)


def validate_global_defaults(global_defaults: dict[str, Any], errors: list[str], warnings: list[str]):
    """Validate global system-wide defaults configuration."""
    middleware = global_defaults.get("middleware", {})

    if middleware and not isinstance(middleware, dict):
        errors.append("global_defaults.middleware must be a dictionary")
        return

    # Validate middleware configurations
    for middleware_name, middleware_config in middleware.items():
        if not isinstance(middleware_config, dict):
            errors.append(f"global_defaults.middleware.{middleware_name} must be a dictionary")
            continue

        # Validate common middleware types
        if middleware_name == "rate_limited":
            validate_rate_limit_config(
                middleware_config, f"global_defaults.middleware.{middleware_name}", errors, warnings
            )
        elif middleware_name == "cached":
            validate_cache_config(middleware_config, f"global_defaults.middleware.{middleware_name}", errors, warnings)
        elif middleware_name == "retryable":
            validate_retry_config(middleware_config, f"global_defaults.middleware.{middleware_name}", errors, warnings)


def validate_plugin_middleware_overrides(
    middleware_list: list[dict], context: str, errors: list[str], warnings: list[str]
):
    """Validate plugin-level middleware override list."""
    if not isinstance(middleware_list, list):
        errors.append(f"{context} middleware must be a list")
        return

    for i, middleware in enumerate(middleware_list):
        if not isinstance(middleware, dict):
            errors.append(f"{context} middleware[{i}] must be a dictionary")
            continue

        if "name" not in middleware:
            errors.append(f"{context} middleware[{i}] missing required field 'name'")
            continue

        if "config" not in middleware and "params" not in middleware:
            errors.append(f"{context} middleware[{i}] missing required field 'config' or 'params'")
            continue

        # Check for both new 'config' field and legacy 'params' field
        params_field = middleware.get("config") or middleware.get("params")
        if params_field and not isinstance(params_field, dict):
            errors.append(f"{context} middleware[{i}] 'config'/'params' must be a dictionary")


def validate_capability_overrides(capabilities: dict[str, Any], context: str, errors: list[str], warnings: list[str]):
    """Validate capability override configurations."""
    if not isinstance(capabilities, dict):
        errors.append(f"{context} capabilities must be a dictionary")
        return

    for cap_id, cap_config in capabilities.items():
        if not isinstance(cap_config, dict):
            errors.append(f"{context} capability '{cap_id}' must be a dictionary")
            continue

        # Validate enabled field
        if "enabled" in cap_config:
            if not isinstance(cap_config["enabled"], bool):
                errors.append(f"{context} capability '{cap_id}' 'enabled' field must be boolean")

        # Validate required_scopes
        if "required_scopes" in cap_config:
            scopes = cap_config["required_scopes"]
            if not isinstance(scopes, list):
                errors.append(f"{context} capability '{cap_id}' 'required_scopes' must be a list")
            else:
                for scope in scopes:
                    if not isinstance(scope, str):
                        errors.append(f"{context} capability '{cap_id}' scope must be string")

        # Validate capability-level middleware
        if "middleware" in cap_config:
            validate_plugin_middleware_overrides(
                cap_config["middleware"], f"{context} capability '{cap_id}'", errors, warnings
            )

        # Validate capability config
        if "config" in cap_config:
            if not isinstance(cap_config["config"], dict):
                errors.append(f"{context} capability '{cap_id}' 'config' must be a dictionary")


def validate_rate_limit_config(config: dict[str, Any], context: str, errors: list[str], warnings: list[str]):
    """Validate rate limiting configuration."""
    if "requests_per_minute" in config:
        rpm = config["requests_per_minute"]
        if not isinstance(rpm, int | float) or rpm <= 0:
            errors.append(f"{context} 'requests_per_minute' must be a positive number")

    if "burst_size" in config:
        burst = config["burst_size"]
        if not isinstance(burst, int) or burst <= 0:
            errors.append(f"{context} 'burst_size' must be a positive integer")


def validate_cache_config(config: dict[str, Any], context: str, errors: list[str], warnings: list[str]):
    """Validate caching configuration."""
    if "backend_type" in config:
        backend = config["backend_type"]
        valid_backends = ["memory", "redis", "valkey"]
        if backend not in valid_backends:
            errors.append(f"{context} 'backend_type' must be one of: {', '.join(valid_backends)}")

    if "default_ttl" in config:
        ttl = config["default_ttl"]
        if not isinstance(ttl, int | float) or ttl <= 0:
            errors.append(f"{context} 'default_ttl' must be a positive number")

    if "max_size" in config:
        max_size = config["max_size"]
        if not isinstance(max_size, int) or max_size <= 0:
            errors.append(f"{context} 'max_size' must be a positive integer")


def validate_retry_config(config: dict[str, Any], context: str, errors: list[str], warnings: list[str]):
    """Validate retry configuration."""
    if "max_attempts" in config:
        attempts = config["max_attempts"]
        if not isinstance(attempts, int) or attempts <= 0:
            errors.append(f"{context} 'max_attempts' must be a positive integer")

    if "initial_delay" in config:
        delay = config["initial_delay"]
        if not isinstance(delay, int | float) or delay < 0:
            errors.append(f"{context} 'initial_delay' must be a non-negative number")

    if "max_delay" in config:
        max_delay = config["max_delay"]
        if not isinstance(max_delay, int | float) or max_delay < 0:
            errors.append(f"{context} 'max_delay' must be a non-negative number")


def validate_middleware_config(
    middleware: list[dict[str, Any]], plugin_name: str, errors: list[str], warnings: list[str]
):
    if not isinstance(middleware, list):
        errors.append(f"Plugin '{plugin_name}' middleware must be a list")
        return

    valid_middleware_types = {"rate_limit", "cache", "retry", "logging", "timing", "transform"}

    for mw in middleware:
        if not isinstance(mw, dict):
            errors.append(f"Plugin '{plugin_name}' middleware entry must be a dictionary")
            continue

        if "type" not in mw:
            errors.append(f"Plugin '{plugin_name}' middleware missing 'type' field")
            continue

        mw_type = mw["type"]
        if mw_type not in valid_middleware_types:
            warnings.append(f"Plugin '{plugin_name}' has unknown middleware type: '{mw_type}'")

        # Validate specific middleware configurations
        if mw_type == "rate_limit" and "requests_per_minute" in mw:
            try:
                rpm = int(mw["requests_per_minute"])
                if rpm <= 0:
                    errors.append(f"Plugin '{plugin_name}' rate limit must be positive")
            except (ValueError, TypeError):
                errors.append(f"Plugin '{plugin_name}' rate limit must be a number")

        if mw_type == "cache" and "ttl" in mw:
            try:
                ttl = int(mw["ttl"])
                if ttl <= 0:
                    errors.append(f"Plugin '{plugin_name}' cache TTL must be positive")
            except (ValueError, TypeError):
                errors.append(f"Plugin '{plugin_name}' cache TTL must be a number")


def validate_services_section(services: dict[str, Any], errors: list[str], warnings: list[str]):
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
    if not isinstance(security, dict):
        errors.append("Security must be a dictionary")
        return

    # Check if security is enabled
    if not security.get("enabled", False):
        click.echo(f"{click.style('✓', fg='green')} Security disabled")
        return

    # Validate auth configuration
    if "auth" not in security:
        errors.append("Security configuration missing 'auth' field when enabled")
        return

    auth = security["auth"]
    if not isinstance(auth, dict):
        errors.append("Security auth must be a dictionary")
        return

    # Check which auth types are configured
    auth_types = []
    if "api_key" in auth:
        auth_types.append("api_key")
        validate_api_key_auth(auth["api_key"], errors, warnings)
    if "jwt" in auth:
        auth_types.append("jwt")
        validate_jwt_auth(auth["jwt"], errors, warnings)
    if "oauth2" in auth:
        auth_types.append("oauth2")
        validate_oauth2_auth(auth["oauth2"], errors, warnings)

    if not auth_types:
        errors.append("No authentication method configured in security.auth")
    elif len(auth_types) > 1:
        warnings.append(f"Multiple auth methods configured: {', '.join(auth_types)}. Only one will be active.")

    # Validate scope hierarchy if present
    if "scope_hierarchy" in security:
        validate_scope_hierarchy(security["scope_hierarchy"], errors, warnings)

    click.echo(f"{click.style('✓', fg='green')} Security configuration valid")


def validate_api_key_auth(api_key_config: dict[str, Any], errors: list[str], warnings: list[str]):
    if "keys" not in api_key_config:
        errors.append("API key auth missing 'keys' field")
        return

    keys = api_key_config.get("keys", [])
    if not isinstance(keys, list) or not keys:
        errors.append("API key auth 'keys' must be a non-empty list")
        return

    for i, key_config in enumerate(keys):
        if not isinstance(key_config, dict):
            errors.append(f"API key {i} must be a dictionary")
            continue
        if "key" not in key_config:
            errors.append(f"API key {i} missing 'key' field")
        if "scopes" in key_config and not isinstance(key_config["scopes"], list):
            errors.append(f"API key {i} 'scopes' must be a list")


def validate_jwt_auth(jwt_config: dict[str, Any], errors: list[str], warnings: list[str]):
    if "secret_key" not in jwt_config:
        errors.append("JWT auth missing 'secret_key' field")

    if "algorithm" in jwt_config:
        valid_algorithms = {
            "HS256",
            "HS384",
            "HS512",
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
            "ES512",
        }
        if jwt_config["algorithm"] not in valid_algorithms:
            warnings.append(f"Unknown JWT algorithm: {jwt_config['algorithm']}")


def validate_oauth2_auth(oauth2_config: dict[str, Any], errors: list[str], warnings: list[str]):
    if "validation_strategy" not in oauth2_config:
        errors.append("OAuth2 auth missing 'validation_strategy' field")

    if oauth2_config.get("validation_strategy") == "jwt":
        required_fields = ["jwks_url", "jwt_algorithm", "jwt_issuer"]
        for field in required_fields:
            if field not in oauth2_config:
                errors.append(f"OAuth2 JWT validation missing '{field}' field")


def validate_scope_hierarchy(scope_hierarchy: dict[str, Any], errors: list[str], warnings: list[str]):
    if not isinstance(scope_hierarchy, dict):
        errors.append("Scope hierarchy must be a dictionary")
        return

    for scope, children in scope_hierarchy.items():
        if not isinstance(children, list):
            errors.append(f"Scope '{scope}' children must be a list")


def check_environment_variables(config: dict[str, Any], errors: list[str], warnings: list[str]):
    env_var_pattern = re.compile(r"\$\{([^:}]+)(?::([^}]+))?\}")
    missing_vars = []

    def check_value(value: Any, path: str = ""):
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
        click.echo(f"\n{click.style('Environment Variables:', fg='yellow')}")
        for var_name, path in missing_vars:
            warnings.append(f"Missing environment variable '{var_name}' referenced in {path}")
    else:
        click.echo(f"{click.style('✓', fg='green')} All environment variables present or have defaults")


def check_handler_implementations(plugins: list[dict[str, Any]], errors: list[str], warnings: list[str]):
    handlers_path = Path("src/agent/handlers.py")

    if not handlers_path.exists():
        errors.append("handlers.py not found at src/agent/handlers.py")
        return

    try:
        with open(handlers_path) as f:
            handlers_content = f.read()

        click.echo(f"\n{click.style('Handler Implementations:', fg='yellow')}")

        for plugin in plugins:
            plugin_name = plugin.get("name")
            if not plugin_name:
                continue

            # Check for handler registration
            if f'@register_handler("{plugin_name}")' in handlers_content:
                click.echo(f"{click.style('✓', fg='green')} Handler found for '{plugin_name}'")
            else:
                warnings.append(f"No handler implementation found for plugin '{plugin_name}'")

            # Check for handler function
            if f"def handle_{plugin_name}" not in handlers_content:
                warnings.append(f"Handler function 'handle_{plugin_name}' not found")

    except Exception as e:
        errors.append(f"Error checking handlers: {str(e)}")


def validate_ai_requirements(config: dict[str, Any], errors: list[str], warnings: list[str]):
    ai_provider = config.get("ai_provider", {})

    # If AI is configured, validate the configuration
    if ai_provider:
        # Validate AI provider configuration
        if "provider" not in ai_provider:
            errors.append("AI provider configuration missing 'provider' field")
        else:
            provider = ai_provider["provider"]

            # Validate provider-specific requirements
            if provider == "openai":
                if "api_key" not in ai_provider:
                    errors.append("OpenAI provider requires 'api_key' field")
            elif provider == "anthropic":
                if "api_key" not in ai_provider:
                    errors.append("Anthropic provider requires 'api_key' field")
            elif provider == "ollama":
                # Ollama doesn't require API key but might need base_url
                pass
            else:
                warnings.append(f"Unknown AI provider: '{provider}'")

            # Validate common AI provider fields
            if "model" not in ai_provider:
                warnings.append("AI provider configuration missing 'model' field - will use provider default")

    click.echo(f"{click.style('✓', fg='green')} AI requirements validated")


def validate_system_prompt_section(ai_config: dict[str, Any], errors: list[str], warnings: list[str]):
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
    if not any(word in prompt_lower for word in ["you are", "your role", "agent", "help"]):
        warnings.append("System prompt may lack clear role definition")

    click.echo(f"{click.style('✓', fg='green')} System prompt validated")


def validate_middleware_section(
    middleware: dict[str, Any] | list[dict[str, Any]], errors: list[str], warnings: list[str]
):
    # Handle new object-based format
    if isinstance(middleware, dict):
        valid_middleware_sections = {
            "enabled",
            "rate_limiting",
            "caching",
            "cache",
            "retry",
            "logging",
            "timeout_seconds",
            "enable_metrics",
            "debug_mode",
            "custom_middleware",
        }

        for section_name, section_config in middleware.items():
            if section_name not in valid_middleware_sections:
                warnings.append(f"Unknown middleware section: '{section_name}'")

            # Special validation for enabled field
            if section_name == "enabled":
                if not isinstance(section_config, bool):
                    errors.append("Middleware 'enabled' field must be a boolean")
                continue

            # Other fields that are not objects
            if section_name in {"timeout_seconds", "enable_metrics", "debug_mode"}:
                continue

            # Validate nested objects
            if section_name in {
                "rate_limiting",
                "caching",
                "cache",
                "retry",
                "logging",
            } and not isinstance(section_config, dict):
                errors.append(f"Middleware section '{section_name}' must be an object")
        return

    # Handle old list-based format
    if not isinstance(middleware, list):
        errors.append("Middleware section must be a list or object")
        return

    valid_middleware_names = {"timed", "cached", "rate_limited", "retryable"}

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
    click.echo(f"\n{click.style('Validation Results:', fg='bright_blue', bold=True)}")

    if errors:
        click.echo(f"\n{click.style('✗ Errors:', fg='red', bold=True)}")
        for error in errors:
            click.echo(f"  • {error}")

    if warnings:
        click.echo(f"\n{click.style('  Warnings:', fg='yellow', bold=True)}")
        for warning in warnings:
            click.echo(f"  • {warning}")

    if not errors and not warnings:
        click.echo(f"\n{click.style('✓ Configuration is valid!', fg='green', bold=True)}")
        click.echo("Your agent configuration passed all validation checks.")
    elif not errors:
        click.echo(f"\n{click.style('✓ Configuration is valid with warnings', fg='green')}")
        if strict:
            click.echo(f"{click.style('✗ Failed strict validation due to warnings', fg='red')}")
            exit(1)
    else:
        click.echo(f"\n{click.style('✗ Configuration is invalid', fg='red', bold=True)}")
        click.echo(f"Found {len(errors)} error(s) and {len(warnings)} warning(s)")
        exit(1)
