import os
from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A settings source that reads from a YAML configuration file.

    Supports environment variable substitution using ${VAR_NAME} syntax.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        yaml_file: Path | str | None = None,
        yaml_file_encoding: str | None = None,
    ):
        super().__init__(settings_cls)
        self.yaml_file = Path(yaml_file) if yaml_file else Path("agentup.yml")
        self.yaml_file_encoding = yaml_file_encoding or "utf-8"

    def _read_file(self) -> dict[str, Any]:
        # Check for config path from environment variable first
        env_config_path = os.getenv("AGENT_CONFIG_PATH")
        if env_config_path:
            self.yaml_file = Path(env_config_path)

        if not self.yaml_file.exists():
            return {}

        try:
            with open(self.yaml_file, encoding=self.yaml_file_encoding) as f:
                content = yaml.safe_load(f)
                if content is None:
                    return {}
                # Handle the 'name' alias for 'project_name'
                if "name" in content and "project_name" not in content:
                    content["project_name"] = content["name"]
                return content
        except Exception:
            # If there's any error reading the file, return empty dict
            return {}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        # This method should return (None, field_name, False) to indicate
        # that this source doesn't have a value for this field
        # This allows env variables to take precedence
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._read_file()
