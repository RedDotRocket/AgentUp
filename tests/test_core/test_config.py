import os

# Import the configuration functions to test
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.config import _process_env_vars, load_config, merge_configs
from tests.utils.test_helpers import (
    assert_config_has_service,
    build_ollama_config,
    build_standard_config,
    create_test_agent_config,
)


class TestLoadConfig:
    """Test the load_config function."""

    def test_load_config_basic(self, temp_dir: Path, sample_agent_config: dict[str, Any], env_vars):
        """Test basic configuration loading."""
        config_file = temp_dir / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(sample_agent_config, f)

        loaded_config = load_config(str(config_file))

        assert loaded_config["agent"]["name"] == "test-agent"
        assert loaded_config["ai_provider"]["provider"] == "openai"
        assert loaded_config["ai_provider"]["model"] == "gpt-4o-mini"

    def test_load_config_file_not_found(self):
        """Test error handling when configuration file doesn't exist."""
        with pytest.raises(FileNotFoundError) as excinfo:
            load_config("nonexistent_config.yaml")

        assert "Configuration file not found" in str(excinfo.value)
        assert "nonexistent_config.yaml" in str(excinfo.value)

    def test_load_config_from_env_var(self, temp_dir: Path, sample_agent_config: dict[str, Any], env_vars):
        """Test loading configuration from AGENT_CONFIG_PATH environment variable."""
        config_file = temp_dir / "env_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(sample_agent_config, f)

        with patch.dict(os.environ, {"AGENT_CONFIG_PATH": str(config_file)}):
            loaded_config = load_config("should_be_ignored.yaml")

        assert loaded_config["agent"]["name"] == "test-agent"

    def test_load_config_invalid_yaml(self, temp_dir: Path):
        """Test error handling for invalid YAML syntax."""
        config_file = temp_dir / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))

    def test_load_config_empty_file(self, temp_dir: Path):
        """Test loading an empty configuration file."""
        config_file = temp_dir / "empty.yaml"
        config_file.write_text("")

        loaded_config = load_config(str(config_file))
        assert loaded_config is None

    def test_load_config_with_env_vars(self, temp_dir: Path, env_vars):
        """Test configuration loading with environment variable substitution."""
        config_data = {
            "agent": {"name": "test-agent"},
            "services": {
                "openai": {"api_key": "${OPENAI_API_KEY}", "base_url": "${OPENAI_BASE_URL:https://api.openai.com}"}
            },
        }

        config_file = temp_dir / "env_test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        loaded_config = load_config(str(config_file))

        assert loaded_config["services"]["openai"]["api_key"] == "test_openai_key"
        assert loaded_config["services"]["openai"]["base_url"] == "https://api.openai.com"


class TestProcessEnvVars:
    """Test the _process_env_vars function."""

    def test_process_env_vars_simple_string(self, env_vars):
        """Test processing a simple environment variable."""
        result = _process_env_vars("${OPENAI_API_KEY}")
        assert result == "test_openai_key"

    def test_process_env_vars_with_default(self):
        """Test processing environment variable with default value."""
        result = _process_env_vars("${NONEXISTENT_VAR:default_value}")
        assert result == "default_value"

    def test_process_env_vars_no_default_missing(self):
        """Test error when environment variable is missing and no default."""
        with pytest.raises(ValueError) as excinfo:
            _process_env_vars("${NONEXISTENT_VAR}")

        assert "Environment variable NONEXISTENT_VAR not set" in str(excinfo.value)

    def test_process_env_vars_nested_dict(self, env_vars):
        """Test processing environment variables in nested dictionaries."""
        config = {
            "services": {
                "openai": {"api_key": "${OPENAI_API_KEY}", "model": "gpt-4"},
                "valkey": {"url": "${VALKEY_URL}"},
            }
        }

        result = _process_env_vars(config)

        assert result["services"]["openai"]["api_key"] == "test_openai_key"
        assert result["services"]["openai"]["model"] == "gpt-4"  # unchanged
        assert result["services"]["valkey"]["url"] == "valkey://localhost:6379"

    def test_process_env_vars_list(self, env_vars):
        """Test processing environment variables in lists."""
        config = {"servers": ["${OPENAI_API_KEY}", "static_value", "${VALKEY_URL}"]}

        result = _process_env_vars(config)

        assert result["servers"][0] == "test_openai_key"
        assert result["servers"][1] == "static_value"
        assert result["servers"][2] == "valkey://localhost:6379"

    def test_process_env_vars_non_env_strings(self):
        """Test that non-environment variable strings are left unchanged."""
        config = {
            "normal_string": "just a string",
            "partial_match": "prefix${VAR}suffix",
            "missing_brace": "${VAR",
        }

        result = _process_env_vars(config)

        assert result["normal_string"] == "just a string"
        assert result["partial_match"] == "prefix${VAR}suffix"
        assert result["missing_brace"] == "${VAR"

    def test_process_env_vars_empty_var_name(self):
        """Test handling of empty environment variable name."""
        with pytest.raises(ValueError) as excinfo:
            _process_env_vars("${}")

        assert "Environment variable  not set" in str(excinfo.value)

    def test_process_env_vars_complex_nested(self, env_vars):
        """Test processing environment variables in complex nested structures."""
        config = {
            "agent": {"name": "test-agent"},
            "services": [
                {"name": "openai", "config": {"api_key": "${OPENAI_API_KEY}", "timeout": 30}},
                {"name": "valkey", "config": {"url": "${VALKEY_URL}", "db": "${VALKEY_DB:0}"}},
            ],
            "middleware": {"auth": {"secret": "${JWT_SECRET:default-secret}"}},
        }

        result = _process_env_vars(config)

        assert result["agent"]["name"] == "test-agent"
        assert result["services"][0]["config"]["api_key"] == "test_openai_key"
        assert result["services"][0]["config"]["timeout"] == 30
        assert result["services"][1]["config"]["url"] == "valkey://localhost:6379"
        assert result["services"][1]["config"]["db"] == "0"
        assert result["middleware"]["auth"]["secret"] == "default-secret"


class TestMergeConfigs:
    """Test the merge_configs function."""

    def test_merge_configs_simple(self):
        """Test merging simple configurations."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = merge_configs(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}
        assert base == {"a": 1, "b": 2}  # Base should be unchanged

    def test_merge_configs_nested_dicts(self):
        """Test merging nested dictionary configurations."""
        base = {"agent": {"name": "base-agent", "version": "1.0"}, "services": {"openai": {"model": "gpt-3.5-turbo"}}}
        override = {"agent": {"name": "override-agent"}, "services": {"openai": {"api_key": "new-key"}}}

        result = merge_configs(base, override)

        expected = {
            "agent": {"name": "override-agent", "version": "1.0"},
            "services": {"openai": {"model": "gpt-3.5-turbo", "api_key": "new-key"}},
        }
        assert result == expected

    def test_merge_configs_override_replaces_non_dict(self):
        """Test that non-dict values are completely replaced."""
        base = {"services": ["service1", "service2"]}
        override = {"services": {"openai": {"model": "gpt-4"}}}

        result = merge_configs(base, override)

        assert result == {"services": {"openai": {"model": "gpt-4"}}}

    def test_merge_configs_deep_nesting(self):
        """Test merging deeply nested configurations."""
        base = {"level1": {"level2": {"level3": {"value1": "base", "value2": "unchanged"}}}}
        override = {"level1": {"level2": {"level3": {"value1": "overridden", "value3": "new"}}}}

        result = merge_configs(base, override)

        expected = {"level1": {"level2": {"level3": {"value1": "overridden", "value2": "unchanged", "value3": "new"}}}}
        assert result == expected

    def test_merge_configs_empty_configs(self):
        """Test merging with empty configurations."""
        base = {"a": 1, "b": 2}

        # Merge with empty override
        result1 = merge_configs(base, {})
        assert result1 == base

        # Merge empty base with override
        result2 = merge_configs({}, base)
        assert result2 == base

        # Merge two empty configs
        result3 = merge_configs({}, {})
        assert result3 == {}


class TestConfigValidation:
    """Test configuration validation and edge cases."""

    def test_ollama_config_structure(self, temp_dir: Path):
        """Test that Ollama configuration is properly structured."""
        ollama_config = build_ollama_config()

        config_file = temp_dir / "ollama_test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(ollama_config, f)

        loaded_config = load_config(str(config_file))

        # Test service name matching (critical for recent fix)
        assert loaded_config["ai"]["llm_service"] == "ollama"
        assert "ollama" in loaded_config["services"]
        assert_config_has_service(loaded_config, "ollama", "llm")
        assert loaded_config["services"]["ollama"]["provider"] == "ollama"
        assert loaded_config["services"]["ollama"]["model"] == "qwen3:0.6b"

    def test_anthropic_config_structure(self, temp_dir: Path, env_vars):
        """Test that Anthropic configuration is properly structured."""
        anthropic_config = create_test_agent_config("anthropic-test", "anthropic", "claude-3-haiku-20240307")
        anthropic_config["services"] = {
            "anthropic": {
                "type": "llm",
                "provider": "anthropic",
                "api_key": "${ANTHROPIC_API_KEY}",
                "model": "claude-3-haiku-20240307",
            }
        }

        config_file = temp_dir / "anthropic_test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(anthropic_config, f)

        loaded_config = load_config(str(config_file))

        # Test service name matching
        assert loaded_config["ai"]["llm_service"] == "anthropic"
        assert "anthropic" in loaded_config["services"]
        assert_config_has_service(loaded_config, "anthropic", "llm")
        assert loaded_config["services"]["anthropic"]["provider"] == "anthropic"
        assert loaded_config["services"]["anthropic"]["api_key"] == "test_anthropic_key"

    def test_openai_config_structure(self, temp_dir: Path, env_vars):
        """Test that OpenAI configuration is properly structured."""
        openai_config = build_standard_config()

        config_file = temp_dir / "openai_test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(openai_config, f)

        loaded_config = load_config(str(config_file))

        # Test service name matching
        assert loaded_config["ai"]["llm_service"] == "openai"
        assert "openai" in loaded_config["services"]
        assert_config_has_service(loaded_config, "openai", "llm")
        assert loaded_config["services"]["openai"]["provider"] == "openai"

    def test_missing_service_validation(self, temp_dir: Path):
        """Test validation of configurations with missing services."""
        invalid_config = {
            "agent": {"name": "invalid-test"},
            "ai": {
                "enabled": True,
                "llm_service": "nonexistent_service",  # Service not defined
                "model": "some-model",
            },
            "services": {
                "valkey": {"type": "cache"}  # Missing the required LLM service
            },
        }

        config_file = temp_dir / "invalid_test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(invalid_config, f)

        loaded_config = load_config(str(config_file))

        # Config loads but should fail validation
        assert loaded_config["ai"]["llm_service"] == "nonexistent_service"
        assert "nonexistent_service" not in loaded_config.get("services", {})

    def test_minimal_config_no_services(self, temp_dir: Path):
        """Test minimal configuration without services section."""
        minimal_config = {
            "agent": {"name": "minimal-test", "version": "0.1.0"},
            "skills": [{"skill_id": "echo", "name": "Echo", "description": "Echo back input"}],
            "routing": {"default_mode": "direct", "fallback_capability": "echo"},
        }

        config_file = temp_dir / "minimal_test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(minimal_config, f)

        loaded_config = load_config(str(config_file))

        assert loaded_config["agent"]["name"] == "minimal-test"
        assert len(loaded_config["skills"]) == 1
        assert "services" not in loaded_config
        assert "ai" not in loaded_config

    def test_config_with_all_env_var_patterns(self, temp_dir: Path):
        """Test configuration with various environment variable patterns."""
        # Set up some test environment variables
        test_env = {"TEST_VAR_1": "value1", "TEST_VAR_2": "value2", "TEST_VAR_3": "value3"}

        config_data = {
            "simple_var": "${TEST_VAR_1}",
            "var_with_default": "${TEST_VAR_MISSING:default_val}",
            "nested": {"var": "${TEST_VAR_2}", "list": ["${TEST_VAR_3}", "static", "${TEST_VAR_MISSING:list_default}"]},
            "no_substitution": "regular string",
            "partial_match": "prefix_${not_a_var",
        }

        config_file = temp_dir / "env_patterns.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch.dict(os.environ, test_env):
            loaded_config = load_config(str(config_file))

        assert loaded_config["simple_var"] == "value1"
        assert loaded_config["var_with_default"] == "default_val"
        assert loaded_config["nested"]["var"] == "value2"
        assert loaded_config["nested"]["list"][0] == "value3"
        assert loaded_config["nested"]["list"][1] == "static"
        assert loaded_config["nested"]["list"][2] == "list_default"
        assert loaded_config["no_substitution"] == "regular string"
        assert loaded_config["partial_match"] == "prefix_${not_a_var"


class TestConfigIntegration:
    """Integration tests for the configuration system."""

    def test_full_config_loading_and_processing(self, temp_dir: Path, env_vars):
        """Test loading and processing a full configuration."""
        full_config = {
            "agent": {"name": "integration-test", "description": "Integration test agent", "version": "0.1.0"},
            "routing": {"default_mode": "ai", "fallback_capability": "ai_assistant", "fallback_enabled": True},
            "skills": [
                {
                    "skill_id": "ai_assistant",
                    "name": "AI Assistant",
                    "description": "General purpose AI assistant",
                    "input_mode": "text",
                    "output_mode": "text",
                    "routing_mode": "ai",
                }
            ],
            "ai": {
                "enabled": True,
                "llm_service": "openai",
                "model": "gpt-4o-mini",
                "system_prompt": "You are an AI assistant.",
                "max_context_turns": 10,
                "fallback_to_routing": True,
            },
            "services": {
                "openai": {"type": "llm", "provider": "openai", "api_key": "${OPENAI_API_KEY}", "model": "gpt-4o-mini"},
                "valkey": {"type": "cache", "config": {"url": "${VALKEY_URL}", "db": 1, "max_connections": 10}},
            },
            "security": {"enabled": False, "type": "api_key"},
            "middleware": [{"name": "logged", "params": {"log_level": 20}}],
        }

        config_file = temp_dir / "full_integration.yaml"
        with open(config_file, "w") as f:
            yaml.dump(full_config, f)

        loaded_config = load_config(str(config_file))

        # Validate structure
        assert loaded_config["agent"]["name"] == "integration-test"
        assert loaded_config["ai"]["enabled"] is True
        assert loaded_config["ai"]["llm_service"] == "openai"

        # Validate environment variable processing
        assert loaded_config["services"]["openai"]["api_key"] == "test_openai_key"
        assert loaded_config["services"]["valkey"]["config"]["url"] == "valkey://localhost:6379"

        # Validate service name consistency (critical test)
        ai_service = loaded_config["ai"]["llm_service"]
        assert ai_service in loaded_config["services"]
        assert loaded_config["services"][ai_service]["type"] == "llm"
        assert loaded_config["services"][ai_service]["provider"] == "openai"

    def test_config_merge_integration(self, temp_dir: Path):
        """Test configuration merging in a realistic scenario."""
        base_config = {
            "agent": {"name": "base-agent", "version": "1.0"},
            "services": {"openai": {"model": "gpt-3.5-turbo", "timeout": 30}},
            "middleware": [{"name": "logged"}],
        }

        override_config = {
            "agent": {"name": "production-agent"},
            "services": {"openai": {"model": "gpt-4", "api_key": "prod-key"}, "valkey": {"url": "valkey://prod:6379"}},
            "security": {"enabled": True},
        }

        merged = merge_configs(base_config, override_config)

        # Verify merge results
        assert merged["agent"]["name"] == "production-agent"
        assert merged["agent"]["version"] == "1.0"  # Preserved from base
        assert merged["services"]["openai"]["model"] == "gpt-4"  # Overridden
        assert merged["services"]["openai"]["timeout"] == 30  # Preserved from base
        assert merged["services"]["openai"]["api_key"] == "prod-key"  # Added
        assert merged["services"]["valkey"]["url"] == "valkey://prod:6379"  # New service
        assert merged["security"]["enabled"] is True  # New section
        assert merged["middleware"] == [{"name": "logged"}]  # Preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
