import os
from pathlib import Path
from typing import Any

import structlog
import yaml
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)


def load_config(config_path: str = "agentup.yml", configure_logging: bool = True) -> dict[str, Any]:
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

    # Handle empty files - yaml.safe_load returns None for empty files
    if config is None:
        config = {}

    # Process environment variables
    config = _process_env_vars(config)

    # Configure logging early if requested
    if configure_logging:
        _configure_logging_from_config(config)

    return config


def _process_env_vars(config: Any) -> Any:
    """Recursively process environment variable substitutions."""
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Check parent directory (for development)
        parent_env = Path.cwd().parent / ".env"
        if parent_env.exists():
            load_dotenv(parent_env)
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
            logger.warning(f"Environment variable {var_name} not set and no default provided, using empty value")
            return ""

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


def _configure_logging_from_config(config: dict[str, Any]) -> None:
    """Configure logging from agent configuration."""
    try:
        from .logging import configure_logging_from_config

        configure_logging_from_config(config)
    except ImportError:
        # Fallback to basic logging if structlog is not available
        import logging

        logging_config = config.get("logging", {})
        level = logging_config.get("level", "INFO")

        try:
            log_level = getattr(logging, level.upper())
        except AttributeError:
            log_level = logging.INFO

        logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
