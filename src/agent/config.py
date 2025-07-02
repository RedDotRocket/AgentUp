import os
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str = "agent_config.yaml") -> dict[str, Any]:
    """Load agent configuration from YAML file."""
    # Check for config path from environment variable first
    env_config_path = os.getenv("AGENT_CONFIG_PATH")
    if env_config_path:
        config_path = env_config_path

    path = Path(config_path)

    if not path.exists():
        # Return error
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    # Process environment variables
    config = _process_env_vars(config)

    return config


def _process_env_vars(config: Any) -> Any:
    """Recursively process environment variable substitutions."""
    if isinstance(config, dict):
        return {k: _process_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_process_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        # Extract env var name and default
        env_expr = config[2:-1]
        if ":" in env_expr:
            var_name, default = env_expr.split(":", 1)
        else:
            var_name, default = env_expr, None

        # Get value from environment or use default
        value = os.getenv(var_name, default)
        if value is None:
            raise ValueError(f"Environment variable {var_name} not set and no default provided")

        return value
    else:
        return config


def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two configurations, with override taking precedence."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result
