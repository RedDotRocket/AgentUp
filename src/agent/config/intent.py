from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from agent.types import ConfigDict as ConfigDictType


class MiddlewareOverride(BaseModel):
    """Model for middleware override configuration."""

    name: str = Field(..., description="Middleware name")
    params: ConfigDictType = Field(default_factory=dict, description="Middleware parameters")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate middleware name."""
        if not v or not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Middleware name must be alphanumeric with hyphens and underscores")
        return v


class CapabilityOverride(BaseModel):
    """Model for capability-specific overrides."""

    enabled: bool = Field(True, description="Whether capability is enabled")
    required_scopes: list[str] = Field(default_factory=list, description="Override required scopes")
    middleware: list[MiddlewareOverride] = Field(default_factory=list, description="Capability-specific middleware")
    config: ConfigDictType = Field(default_factory=dict, description="Capability-specific configuration")

    @field_validator("required_scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Validate scope format."""
        for scope in v:
            if not isinstance(scope, str) or ":" not in scope:
                raise ValueError(f"Invalid scope format: {scope}. Must be domain:action")
        return v


class PluginOverride(BaseModel):
    """Model for plugin-level overrides."""

    enabled: bool = Field(True, description="Whether plugin is enabled")
    plugin_id: str | None = Field(None, description="Plugin ID (entry point name)")
    package: str | None = Field(None, description="Package name for security validation")
    capabilities: dict[str, CapabilityOverride] = Field(
        default_factory=dict, description="Capability-specific overrides"
    )
    middleware: list[MiddlewareOverride] = Field(default_factory=list, description="Plugin-level middleware")
    config: ConfigDictType = Field(default_factory=dict, description="Plugin-specific configuration")

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: dict) -> dict:
        """Ensure capability overrides are valid."""
        validated = {}
        for cap_id, config in v.items():
            if isinstance(config, dict):
                validated[cap_id] = CapabilityOverride(**config)
            elif isinstance(config, CapabilityOverride):
                validated[cap_id] = config
            else:
                raise ValueError(f"Invalid capability override for {cap_id}")
        return validated


# Union type for plugin configuration - supports both simple package names and complex overrides
PluginConfig = str | PluginOverride


class GlobalDefaults(BaseModel):
    """Model for global default configurations."""

    middleware: dict[str, ConfigDictType] = Field(default_factory=dict, description="Global middleware defaults")
    security: ConfigDictType = Field(default_factory=dict, description="Global security defaults")

    @field_validator("middleware")
    @classmethod
    def validate_middleware(cls, v: dict) -> dict:
        """Validate middleware configuration."""
        # Basic validation - middleware names should be alphanumeric
        for name, config in v.items():
            if not name.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"Invalid middleware name: {name}")
            if not isinstance(config, dict):
                raise ValueError(f"Middleware config for {name} must be a dictionary")
        return v


class IntentConfig(BaseModel):
    """
    Unified plugin configuration for agentup.yml.

    Supports both simple plugin lists and complex plugin overrides.
    """

    # API versioning for future compatibility
    apiVersion: str = Field("v1", description="Configuration API version")

    # Basic agent information
    name: str = Field(..., description="Agent name")
    description: str = Field("", description="Agent description")
    version: str | None = Field(None, description="Agent version")

    # Plugin configuration - supports both simple strings and complex objects
    plugins: dict[str, PluginConfig] = Field(default_factory=dict, description="Plugin configurations")

    @field_validator("plugins", mode="before")
    @classmethod
    def validate_plugins(cls, v):
        """Handle None values and convert list format to dict format."""
        if v is None:
            return {}
        if isinstance(v, list):
            # Convert old list format to new dict format
            result = {}
            for item in v:
                if isinstance(item, str):
                    # Simple package name
                    result[item] = item
                elif isinstance(item, dict) and "package" in item:
                    # Complex plugin config
                    package = item["package"]
                    result[package] = item
            return result
        return v

    # Global defaults applied to all plugins
    global_defaults: GlobalDefaults = Field(default_factory=GlobalDefaults, description="Global default configurations")

    # All other existing configuration sections remain unchanged
    # These are passed through as-is to maintain compatibility
    environment: str | None = Field(None, description="Environment setting")
    logging: dict[str, Any] | None = Field(None, description="Logging configuration")
    api: dict[str, Any] | None = Field(None, description="API configuration")
    security: dict[str, Any] | None = Field(None, description="Security configuration")
    middleware: dict[str, Any] | None = Field(None, description="Middleware configuration")
    mcp: dict[str, Any] | None = Field(None, description="MCP configuration")
    ai: dict[str, Any] | None = Field(None, description="AI configuration")
    ai_provider: dict[str, Any] | None = Field(None, description="AI provider configuration")
    services: dict[str, Any] | None = Field(None, description="Services configuration")
    push_notifications: dict[str, Any] | None = Field(None, description="Push notifications configuration")
    state_management: dict[str, Any] | None = Field(None, description="State management configuration")
    custom: dict[str, Any] | None = Field(None, description="Custom configuration")

    @field_validator("apiVersion")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        """Validate API version format."""
        if not v.startswith("v") or not v[1:].replace(".", "").isdigit():
            raise ValueError("API version must be in format v1, v1.0, v2, etc.")
        return v

    @field_validator("plugins")
    @classmethod
    def validate_plugins_detailed(cls, v: dict) -> dict:
        """Validate plugin configuration after conversion to dict format."""
        if not isinstance(v, dict):
            raise ValueError("Plugins must be a dictionary at this stage")

        validated = {}
        for package_name, config in v.items():
            # Validate package name
            if not package_name.replace("-", "").replace("_", "").replace(".", "").replace(":", "").isalnum():
                raise ValueError(f"Invalid plugin package name: {package_name}")

            # Validate and normalize configuration
            if isinstance(config, str):
                # Handle string values from the before validator
                validated[package_name] = PluginOverride()
            elif isinstance(config, dict):
                validated[package_name] = PluginOverride(**config)
            elif isinstance(config, PluginOverride):
                validated[package_name] = config
            else:
                raise ValueError(f"Invalid plugin configuration for {package_name}")

        return validated

    @model_validator(mode="after")
    def validate_model(self) -> IntentConfig:
        """Validate the entire model for consistency."""
        # Ensure at least one plugin is configured
        if not self.plugins:
            # This is OK - empty plugin list is valid
            pass

        # Validate that global defaults are reasonable
        if self.global_defaults.middleware:
            for name, config in self.global_defaults.middleware.items():
                if not isinstance(config, dict):
                    raise ValueError(f"Global middleware config for {name} must be a dictionary")

        return self

    def get_plugin_config(self, package_name: str) -> PluginOverride:
        """Get configuration for a specific plugin."""
        config = self.plugins.get(package_name)
        if isinstance(config, str):
            return PluginOverride()  # Return default if simple string format
        return config or PluginOverride()

    def set_plugin_config(self, package_name: str, config: PluginOverride | dict) -> None:
        """Set configuration for a specific plugin."""
        if isinstance(config, dict):
            config = PluginOverride(**config)
        self.plugins[package_name] = config

    def add_plugin(self, package_name: str, config: PluginOverride | None = None) -> None:
        """Add a plugin to the intent configuration."""
        if package_name not in self.plugins:
            self.plugins[package_name] = config or PluginOverride()

    def remove_plugin(self, package_name: str) -> None:
        """Remove a plugin from the intent configuration."""
        if package_name in self.plugins:
            del self.plugins[package_name]

    def model_dump_yaml_friendly(self) -> dict[str, Any]:
        """
        Export to a YAML-friendly dictionary.

        Handles both simple and complex plugin configurations.
        """
        result = {}

        # API version first
        result["apiVersion"] = self.apiVersion

        # Basic fields
        result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.version:
            result["version"] = self.version

        # Plugin configurations
        plugins_dict = {}
        if self.plugins:
            for package_name, config in self.plugins.items():
                if isinstance(config, str):
                    # This shouldn't happen with new model, but handle it
                    plugins_dict[package_name] = {"enabled": True}
                else:
                    # Convert PluginOverride to dict, excluding defaults
                    config_data = config.model_dump(exclude_unset=True, exclude_defaults=True)
                    if config_data:
                        plugins_dict[package_name] = config_data
                    else:
                        # If no overrides, just show enabled: true
                        plugins_dict[package_name] = {"enabled": True}

        result["plugins"] = plugins_dict

        # Global defaults (only include if not empty)
        global_defaults_data = self.global_defaults.model_dump(exclude_unset=True, exclude_defaults=True)
        if global_defaults_data:
            result["global_defaults"] = global_defaults_data

        # Other configuration sections (exclude None values)
        optional_fields = [
            "environment",
            "logging",
            "api",
            "security",
            "middleware",
            "mcp",
            "ai",
            "ai_provider",
            "services",
            "push_notifications",
            "state_management",
            "custom",
        ]

        for field in optional_fields:
            value = getattr(self, field, None)
            if value is not None:
                result[field] = value

        return result


def load_intent_config(file_path: str) -> IntentConfig:
    """Load intent configuration from a YAML file."""
    from pathlib import Path

    import yaml

    path = Path(file_path)
    if not path.exists():
        # Return default config if file doesn't exist
        return IntentConfig(name="AgentUp Agent")

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    # Handle migration from old plugin format
    data = _migrate_from_old_format(data)

    return IntentConfig(**data)


def _migrate_from_old_format(data: dict) -> dict:
    """
    Migrate configuration from old plugin formats to new unified format.

    Handles multiple migration scenarios:
    1. Old complex format: plugins: [{'plugin_id': 'foo', 'package': 'bar', ...}]
    2. Simple list format: plugins: ['package1', 'package2']
    3. New dict format: plugins: {'package': {...}}
    """
    # Add API version if missing
    if "apiVersion" not in data:
        data["apiVersion"] = "v1"

    if "plugins" in data and data["plugins"]:
        old_plugins = data["plugins"]

        # Case 1: Old complex format with dicts containing plugin_id/package
        if isinstance(old_plugins, list) and old_plugins and isinstance(old_plugins[0], dict):
            new_plugins = {}
            for plugin_config in old_plugins:
                package_name = None
                config_overrides = {}

                if "package" in plugin_config:
                    package_name = plugin_config["package"]
                elif "plugin_id" in plugin_config:
                    # Fallback: convert plugin_id to package name format
                    package_name = plugin_config["plugin_id"].replace("_", "-")

                if package_name:
                    # Extract any configuration that can be migrated
                    if "enabled" in plugin_config:
                        config_overrides["enabled"] = plugin_config["enabled"]

                    # Migrate middleware_override to new format
                    if "middleware_override" in plugin_config:
                        middleware_list = []
                        for mw in plugin_config["middleware_override"]:
                            if isinstance(mw, dict) and "name" in mw:
                                middleware_obj = {"name": mw["name"]}
                                if "params" in mw:
                                    middleware_obj["params"] = mw["params"]
                                middleware_list.append(middleware_obj)
                        if middleware_list:
                            config_overrides["middleware"] = middleware_list

                    # Migrate capability-specific configurations
                    if "capabilities" in plugin_config:
                        cap_overrides = {}
                        for cap in plugin_config["capabilities"]:
                            if isinstance(cap, dict) and "capability_id" in cap:
                                cap_id = cap["capability_id"]
                                cap_config = {}

                                if "enabled" in cap:
                                    cap_config["enabled"] = cap["enabled"]
                                if "required_scopes" in cap:
                                    cap_config["required_scopes"] = cap["required_scopes"]
                                if "middleware_override" in cap:
                                    cap_middleware = []
                                    for mw in cap["middleware_override"]:
                                        if isinstance(mw, dict) and "name" in mw:
                                            cap_mw = {"name": mw["name"]}
                                            if "params" in mw:
                                                cap_mw["params"] = mw["params"]
                                            cap_middleware.append(cap_mw)
                                    if cap_middleware:
                                        cap_config["middleware"] = cap_middleware

                                if cap_config:
                                    cap_overrides[cap_id] = cap_config

                        if cap_overrides:
                            config_overrides["capabilities"] = cap_overrides

                    new_plugins[package_name] = config_overrides if config_overrides else {"enabled": True}

            data["plugins"] = new_plugins

        # Case 2: Simple list format - convert to dict format
        elif isinstance(old_plugins, list) and old_plugins and isinstance(old_plugins[0], str):
            new_plugins = {}
            for package_name in old_plugins:
                new_plugins[package_name] = {"enabled": True}
            data["plugins"] = new_plugins

        # Case 3: Dict format but may need capability migration
        elif isinstance(old_plugins, dict):
            new_plugins = {}
            for package_name, plugin_config in old_plugins.items():
                if isinstance(plugin_config, dict):
                    config_overrides = plugin_config.copy()

                    # Migrate capabilities from list to dict format if needed
                    if "capabilities" in config_overrides and isinstance(config_overrides["capabilities"], list):
                        cap_overrides = {}
                        for cap in config_overrides["capabilities"]:
                            if isinstance(cap, dict) and "capability_id" in cap:
                                cap_id = cap["capability_id"]
                                cap_config = {}

                                if "enabled" in cap:
                                    cap_config["enabled"] = cap["enabled"]
                                if "required_scopes" in cap:
                                    cap_config["required_scopes"] = cap["required_scopes"]
                                if "middleware_override" in cap:
                                    cap_middleware = []
                                    for mw in cap["middleware_override"]:
                                        if isinstance(mw, dict) and "name" in mw:
                                            cap_mw = {"name": mw["name"]}
                                            if "params" in mw:
                                                cap_mw["params"] = mw["params"]
                                            cap_middleware.append(cap_mw)
                                    if cap_middleware:
                                        cap_config["middleware"] = cap_middleware

                                if cap_config:
                                    cap_overrides[cap_id] = cap_config

                        config_overrides["capabilities"] = cap_overrides

                    new_plugins[package_name] = config_overrides
                else:
                    # Handle string values (shouldn't happen but be safe)
                    new_plugins[package_name] = {"enabled": True}

            data["plugins"] = new_plugins

    # Migrate global middleware configuration if it exists
    if "middleware" in data and isinstance(data["middleware"], dict):
        # Move global middleware to global_defaults
        if "global_defaults" not in data:
            data["global_defaults"] = {}

        # Extract middleware defaults from global middleware config
        middleware_config = data["middleware"]
        middleware_defaults = {}

        # Common middleware configurations to extract as defaults
        for mw_type in ["cache", "rate_limiting", "retry", "audit"]:
            if mw_type in middleware_config and isinstance(middleware_config[mw_type], dict):
                middleware_defaults[mw_type] = middleware_config[mw_type]

        if middleware_defaults:
            data["global_defaults"]["middleware"] = middleware_defaults

    return data


def save_intent_config(config: IntentConfig, file_path: str) -> None:
    """Save intent configuration to a YAML file with proper formatting."""
    from pathlib import Path

    import yaml

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Export as YAML-friendly dict
    data = config.model_dump_yaml_friendly()

    # Create a custom YAML dumper for better formatting
    class CustomYAMLDumper(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            # This ensures proper list item indentation - ignore indentless param
            return super().increase_indent(flow, False)

    # Configure dumper for clean output
    def represent_none(self, data):  # data param required by PyYAML interface
        return self.represent_scalar("tag:yaml.org,2002:null", "")

    CustomYAMLDumper.add_representer(type(None), represent_none)

    # First dump to string
    yaml_content = yaml.dump(
        data,
        Dumper=CustomYAMLDumper,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
        width=120,  # Prevent excessive line wrapping
        allow_unicode=True,
    )

    # Post-process to add blank lines around sections
    section_keys = [
        "apiVersion:",
        "name:",
        "description:",
        "version:",
        "plugins:",
        "global_defaults:",
        "logging:",
        "api:",
        "security:",
        "middleware:",
        "mcp:",
        "push_notifications:",
        "state_management:",
    ]

    lines = yaml_content.split("\n")
    formatted_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line starts a major section
        is_section = any(line.startswith(key) for key in section_keys)

        # Add blank line before section (except at start of file)
        if is_section and formatted_lines and formatted_lines[-1].strip():
            formatted_lines.append("")

        formatted_lines.append(line)

        # Special handling for plugins section - add blank line after it ends
        if line.startswith("plugins:"):
            # Add all plugin list items
            i += 1
            while i < len(lines) and (lines[i].startswith("-") or lines[i].startswith(" ") or lines[i].strip() == ""):
                if lines[i].strip():  # Skip empty lines within plugins
                    formatted_lines.append(lines[i])
                i += 1

            # Add blank line after plugins section
            if i < len(lines) and lines[i].strip():  # Only if there's more content
                formatted_lines.append("")

            i -= 1  # Adjust because we'll increment at end of loop

        i += 1

    # Remove any duplicate blank lines
    clean_lines = []
    prev_blank = False
    for line in formatted_lines:
        is_blank = line.strip() == ""
        if not (is_blank and prev_blank):  # Skip duplicate blank lines
            clean_lines.append(line)
        prev_blank = is_blank

    # Write the formatted content
    with open(path, "w") as f:
        f.write("\n".join(clean_lines))
