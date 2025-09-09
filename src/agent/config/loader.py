"""
Configuration loader and saver for AgentUp.

This module provides functions to load and save AgentConfig instances
from/to YAML configuration files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .model import AgentConfig


def load_config(file_path: str) -> AgentConfig:
    """Load agent configuration from a YAML file."""
    path = Path(file_path)

    if not path.exists():
        # Return default config if file doesn't exist
        return AgentConfig()

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Handle environment variable expansion
    data = _expand_env_vars(data)

    return AgentConfig(**data)


def save_config(config: AgentConfig, file_path: str) -> None:
    """Save agent configuration to a YAML file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert config to dict for YAML serialization
    # Manually exclude computed fields that shouldn't be saved
    data = config.model_dump(exclude_defaults=True, exclude_none=True, by_alias=True)

    # Remove computed fields that cause validation issues when reloading
    computed_fields_to_exclude = {
        "is_production",
        "is_development",
        "enabled_services",
        "total_service_count",
        "security_enabled",
        "full_name",
    }
    for field in computed_fields_to_exclude:
        data.pop(field, None)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2, allow_unicode=True)


def _expand_env_vars(value: Any) -> Any:
    """Expand environment variables in configuration values."""
    import os
    import re

    if isinstance(value, str):
        # Handle ${VAR} and ${VAR:default} patterns
        def replace_env_var(match):
            var_spec = match.group(1)
            if ":" in var_spec:
                var_name, default = var_spec.split(":", 1)
            else:
                var_name, default = var_spec, None

            return os.getenv(var_name, default or match.group(0))

        return re.sub(r"\$\{([^}]+)\}", replace_env_var, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]

    return value
