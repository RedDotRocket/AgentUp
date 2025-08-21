from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from agent.types import ConfigDict as ConfigDictType


class MiddlewareOverride(BaseModel):
    """Model for middleware override configuration."""

    name: str = Field(..., description="Middleware name")
    config: ConfigDictType = Field(default_factory=dict, description="Middleware configuration")

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
    capability_override: list[MiddlewareOverride] = Field(
        default_factory=list, description="Capability-specific middleware overrides"
    )
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
    capabilities: dict[str, CapabilityOverride] = Field(
        default_factory=dict, description="Capability-specific overrides"
    )
    plugin_override: list[MiddlewareOverride] = Field(
        default_factory=list, description="Plugin-level middleware overrides"
    )
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


class PluginDefaults(BaseModel):
    """Model for plugin default configurations that plugins inherit."""

    middleware: dict[str, ConfigDictType] = Field(default_factory=dict, description="Plugin middleware defaults")

    @field_validator("middleware", mode="before")
    @classmethod
    def validate_middleware_none(cls, v):
        """Handle None values for middleware."""
        if v is None:
            return {}
        return v


class GlobalDefaults(BaseModel):
    """Model for global system-wide configurations."""

    middleware: dict[str, ConfigDictType] = Field(
        default_factory=dict, description="System-wide middleware configuration"
    )

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
    url: str | None = Field(None, description="Agent URL")
    provider_organization: str | None = Field(None, description="Provider organization")
    provider_url: str | None = Field(None, description="Provider URL")
    icon_url: str | None = Field(None, description="Icon URL")
    documentation_url: str | None = Field(None, description="Documentation URL")

    # Plugin configuration - supports both simple strings and complex objects
    plugins: dict[str, PluginConfig] = Field(default_factory=dict, description="Plugin configurations")

    @field_validator("plugins", mode="before")
    @classmethod
    def validate_plugins(cls, v):
        """Handle None values."""
        if v is None:
            return {}
        return v

    # Plugin defaults applied to all plugins
    plugin_defaults: PluginDefaults = Field(default_factory=PluginDefaults, description="Plugin default configurations")

    # Global system-wide defaults
    global_defaults: GlobalDefaults = Field(
        default_factory=GlobalDefaults, description="Global system-wide configurations"
    )

    # All other existing configuration sections remain unchanged
    # These are passed through as-is to maintain compatibility
    environment: str | None = Field(None, description="Environment setting")
    logging: dict[str, Any] | None = Field(None, description="Logging configuration")
    api: dict[str, Any] | None = Field(None, description="API configuration")
    cors: dict[str, Any] | None = Field(None, description="CORS configuration")
    security: dict[str, Any] | None = Field(None, description="Security configuration")
    middleware: dict[str, Any] | None = Field(None, description="Middleware configuration")
    mcp: dict[str, Any] | None = Field(None, description="MCP configuration")
    ai: dict[str, Any] | None = Field(None, description="AI configuration")
    ai_provider: dict[str, Any] | None = Field(None, description="AI provider configuration")
    services: dict[str, Any] | None = Field(None, description="Services configuration")
    push_notifications: dict[str, Any] | None = Field(None, description="Push notifications configuration")
    state_management: dict[str, Any] | None = Field(None, description="State management configuration")
    development: dict[str, Any] | None = Field(None, description="Development configuration")
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
        """Validate plugin configuration."""
        if not isinstance(v, dict):
            raise ValueError("Plugins must be a dictionary")

        validated = {}
        for package_name, config in v.items():
            # Validate package name
            if not package_name.replace("-", "").replace("_", "").replace(".", "").replace(":", "").isalnum():
                raise ValueError(f"Invalid plugin package name: {package_name}")

            # Validate configuration
            if isinstance(config, dict):
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

        # Validate that plugin defaults are reasonable
        if self.plugin_defaults.middleware:
            for name, config in self.plugin_defaults.middleware.items():
                if not isinstance(config, dict):
                    raise ValueError(f"Plugin middleware config for {name} must be a dictionary")

        # Validate that global defaults are reasonable
        if self.global_defaults.middleware:
            for name, config in self.global_defaults.middleware.items():
                if not isinstance(config, dict):
                    raise ValueError(f"Global middleware config for {name} must be a dictionary")

        return self

    def get_plugin_config(self, package_name: str) -> PluginOverride:
        """Get configuration for a specific plugin."""
        return self.plugins.get(package_name, PluginOverride())

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
        if self.url:
            result["url"] = self.url
        if self.provider_organization:
            result["provider_organization"] = self.provider_organization
        if self.provider_url:
            result["provider_url"] = self.provider_url
        if self.icon_url:
            result["icon_url"] = self.icon_url
        if self.documentation_url:
            result["documentation_url"] = self.documentation_url

        # Plugin configurations
        plugins_dict = {}
        if self.plugins:
            for package_name, config in self.plugins.items():
                # Convert PluginOverride to dict, excluding defaults
                config_data = config.model_dump(exclude_unset=True, exclude_defaults=True)
                plugins_dict[package_name] = config_data

        result["plugins"] = plugins_dict

        # Plugin defaults (only include if not empty)
        plugin_defaults_data = self.plugin_defaults.model_dump(exclude_unset=True, exclude_defaults=True)
        if plugin_defaults_data:
            result["plugin_defaults"] = plugin_defaults_data

        # Global defaults (only include if not empty)
        global_defaults_data = self.global_defaults.model_dump(exclude_unset=True, exclude_defaults=True)
        if global_defaults_data:
            result["global_defaults"] = global_defaults_data

        # Other configuration sections (exclude None values)
        optional_fields = [
            "environment",
            "logging",
            "api",
            "cors",
            "security",
            "middleware",
            "mcp",
            "ai",
            "ai_provider",
            "services",
            "push_notifications",
            "state_management",
            "development",
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

    # Add API version if missing
    if "apiVersion" not in data:
        data["apiVersion"] = "v1"

    return IntentConfig(**data)


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

    # Post-process to add blank lines around major sections only
    section_keys = [
        "plugins:",
        "plugin_defaults:",
        "global_defaults:",
        "environment:",
        "logging:",
        "api:",
        "cors:",
        "security:",
        "middleware:",
        "mcp:",
        "ai:",
        "ai_provider:",
        "services:",
        "push_notifications:",
        "state_management:",
        "development:",
        "custom:",
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
