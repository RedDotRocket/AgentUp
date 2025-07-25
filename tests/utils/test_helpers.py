from pathlib import Path
from typing import Any
from unittest.mock import Mock

import yaml


def create_test_config(
    name: str = "test-agent",
    template: str = "standard",
    features: list[str] | None = None,
    services: list[str] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Create a test configuration with customizable parameters."""
    if features is None:
        features = ["services", "middleware"]
    if services is None:
        services = ["openai"]

    config = {
        "name": name,
        "description": f"Test agent {name}",
        "template": template,
        "features": features,
        "services": services,
        **kwargs,
    }
    return config


def create_test_agent_config(
    agent_name: str = "test-agent", llm_service: str = "openai", llm_model: str = "gpt-4o-mini", **kwargs
) -> dict[str, Any]:
    """Create a test agent configuration YAML structure."""
    config = {
        "agent": {"name": agent_name, "description": f"Test agent {agent_name}", "version": "0.3.0"},
        "routing": {"default_mode": "ai", "fallback_capability": "ai_assistant", "fallback_enabled": True},
        "skills": [
            {
                "skill_id": "ai_assistant",
                "name": "AI Assistant",
                "description": "General purpose AI assistant",
                "input_mode": "text",
                "output_mode": "text",
            }
        ],
        "ai": {
            "enabled": True,
            "llm_service": llm_service,
            "model": llm_model,
            "system_prompt": f"You are {agent_name}, an AI assistant.",
            "max_context_turns": 10,
            "fallback_to_routing": True,
        },
        **kwargs,
    }
    return config


def save_test_config(config: dict[str, Any], file_path: Path) -> Path:
    """Save a test configuration to a YAML file."""
    with open(file_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    return file_path


def load_test_config(file_path: Path) -> dict[str, Any]:
    """Load a test configuration from a YAML file."""
    with open(file_path) as f:
        return yaml.safe_load(f)


def assert_config_has_service(config: dict[str, Any], service_name: str, service_type: str):
    """Assert that a configuration has a specific service defined."""
    assert "services" in config, "Configuration missing services section"
    assert service_name in config["services"], f"Service '{service_name}' not found in configuration"
    assert config["services"][service_name]["type"] == service_type, (
        f"Service '{service_name}' has wrong type. Expected '{service_type}', got '{config['services'][service_name]['type']}'"
    )


def assert_config_has_llm_service(config: dict[str, Any], service_name: str, provider: str, model: str):
    """Assert that a configuration has a properly configured LLM service."""
    assert_config_has_service(config, service_name, "llm")
    service = config["services"][service_name]
    assert service["provider"] == provider, (
        f"LLM service provider mismatch. Expected '{provider}', got '{service['provider']}'"
    )
    assert service["model"] == model, f"LLM service model mismatch. Expected '{model}', got '{service['model']}'"

    # Check AI section matches
    if "ai" in config:
        assert config["ai"]["llm_service"] == service_name, (
            f"AI section llm_service mismatch. Expected '{service_name}', got '{config['ai']['llm_service']}'"
        )
        assert config["ai"]["model"] == model, (
            f"AI section model mismatch. Expected '{model}', got '{config['ai']['model']}'"
        )


def assert_files_exist(base_path: Path, expected_files: list[str]):
    """Assert that expected files exist in the given directory."""
    for file_path in expected_files:
        full_path = base_path / file_path
        assert full_path.exists(), f"Expected file does not exist: {full_path}"


def assert_directory_structure(base_path: Path, expected_structure: dict[str, Any]):
    """Assert that a directory has the expected structure.

    Args:
        base_path: Base directory to check
        expected_structure: dictionary where keys are paths and values are:
            - True for files that should exist
            - list of strings for directories containing those files
            - dict for nested directory structures
    """
    for path, expected in expected_structure.items():
        full_path = base_path / path

        if expected is True:
            # File should exist
            assert full_path.is_file(), f"Expected file does not exist: {full_path}"
        elif isinstance(expected, list):
            # Directory containing files
            assert full_path.is_dir(), f"Expected directory does not exist: {full_path}"
            for filename in expected:
                file_path = full_path / filename
                assert file_path.exists(), f"Expected file in directory does not exist: {file_path}"
        elif isinstance(expected, dict):
            # Nested directory structure
            assert full_path.is_dir(), f"Expected directory does not exist: {full_path}"
            assert_directory_structure(full_path, expected)


def mock_questionary_responses(responses: dict[str, Any]):
    """Create mock responses for questionary prompts."""

    def mock_ask(*args, **kwargs):
        # Extract the question text from the prompt
        if args:
            question = args[0]
        else:
            question = kwargs.get("message", "")

        # Find matching response
        for key, value in responses.items():
            if key in question or question in key:
                return value

        # Default response if no match
        return responses.get("default", "test-response")

    mock_questionary = Mock()
    mock_questionary.text.return_value.ask = mock_ask
    mock_questionary.select.return_value.ask = mock_ask
    mock_questionary.checkbox.return_value.ask = mock_ask
    mock_questionary.confirm.return_value.ask = mock_ask

    return mock_questionary


def create_mock_generator_context(
    project_name: str = "test-project",
    template: str = "standard",
    features: list[str] | None = None,
    services: list[str] | None = None,
) -> dict[str, Any]:
    """Create a mock context for generator testing."""
    if features is None:
        features = ["services", "middleware"]
    if services is None:
        services = ["openai"]

    return {
        "project_name": project_name,
        "project_name_snake": project_name.lower().replace("-", "_"),
        "project_name_title": project_name.replace("-", " ").title(),
        "description": f"Test project {project_name}",
        "features": features,
        "template_name": template,
        "has_middleware": "middleware" in features,
        "has_services": "services" in features,
        "has_state_management_management": "state_management" in features,
        "has_auth": "auth" in features,
        "has_monitoring": "monitoring" in features,
        "has_testing": "testing" in features,
        "has_deployment": "deployment" in features,
        "has_mcp": "mcp" in features,
        "services": services,
        "llm_provider_config": "openai" in services or "anthropic" in services or "ollama" in services,
    }


def validate_generated_config(config_path: Path, expected_template: str, expected_services: list[str]):
    """Validate a generated agent configuration file."""
    assert config_path.exists(), f"Generated config file does not exist: {config_path}"

    config = load_test_config(config_path)

    # Basic structure validation
    assert "agent" in config, "Generated config missing 'agent' section"
    assert "skills" in config, "Generated config missing 'skills' section"
    assert "routing" in config, "Generated config missing 'routing' section"

    # Template-specific validation
    if expected_template != "minimal":
        assert "ai" in config, f"Template '{expected_template}' should have AI configuration"
        assert "services" in config, f"Template '{expected_template}' should have services configuration"

    # Service validation
    for service in expected_services:
        if service in ["openai", "anthropic", "ollama"]:
            assert "ai" in config, "LLM service selected but no AI configuration found"
            llm_service = config["ai"].get("llm_service")
            assert llm_service, "AI enabled but no llm_service specified"
            assert llm_service in config.get("services", {}), (
                f"AI references service '{llm_service}' but service not found in services section"
            )


class AgentConfigBuilder:
    """Builder pattern for creating test data."""

    def __init__(self):
        self.config = {}

    def with_agent(self, name: str = "test-agent", description: str = None, version: str = "0.3.0"):
        """Add agent configuration."""
        self.config["agent"] = {"name": name, "description": description or f"Test agent {name}", "version": version}
        return self

    def with_ai(self, llm_service: str = "openai", model: str = "gpt-4o-mini", enabled: bool = True):
        """Add AI configuration."""
        self.config["ai"] = {
            "enabled": enabled,
            "llm_service": llm_service,
            "model": model,
            "system_prompt": f"You are {self.config.get('agent', {}).get('name', 'test-agent')}, an AI assistant.",
            "max_context_turns": 10,
            "fallback_to_routing": True,
        }
        return self

    def with_service(self, name: str, service_type: str, **config):
        """Add a service configuration."""
        if "services" not in self.config:
            self.config["services"] = {}
        self.config["services"][name] = {"type": service_type, **config}
        return self

    def with_openai_service(self, name: str = "openai", model: str = "gpt-4o-mini"):
        """Add OpenAI service configuration."""
        return self.with_service(name, "llm", provider="openai", api_key="${OPENAI_API_KEY}", model=model)

    def with_ollama_service(self, name: str = "ollama", model: str = "qwen3:0.6b"):
        """Add Ollama service configuration."""
        return self.with_service(
            name, "llm", provider="ollama", base_url="${OLLAMA_BASE_URL:http://localhost:11434}", model=model
        )

    def with_anthropic_service(self, name: str = "anthropic", model: str = "claude-3-haiku-20240307"):
        """Add Anthropic service configuration."""
        return self.with_service(name, "llm", provider="anthropic", api_key="${ANTHROPIC_API_KEY}", model=model)

    def with_skill(self, skill_id: str, name: str = None, **config):
        """Add a skill configuration."""
        if "skills" not in self.config:
            self.config["skills"] = []

        skill = {
            "skill_id": skill_id,
            "name": name or skill_id.replace("_", " ").title(),
            "description": f"Test skill {skill_id}",
            "input_mode": "text",
            "output_mode": "text",
            **config,
        }
        self.config["skills"].append(skill)
        return self

    def build(self) -> dict[str, Any]:
        """Build the final configuration."""
        return self.config.copy()


# Common test data builders
def build_minimal_config() -> dict[str, Any]:
    """Build a minimal test configuration."""
    return (
        AgentConfigBuilder()
        .with_agent("minimal-test", "Minimal test agent")
        .with_skill("echo", "Echo", keywords=["echo"])
        .build()
    )


def build_standard_config() -> dict[str, Any]:
    """Build a standard test configuration."""
    return (
        AgentConfigBuilder()
        .with_agent("standard-test", "Standard test agent")
        .with_ai("openai", "gpt-4o-mini")
        .with_openai_service()
        .with_skill("ai_assistant", "AI Assistant")
        .build()
    )


def build_ollama_config() -> dict[str, Any]:
    """Build an Ollama test configuration."""
    return (
        AgentConfigBuilder()
        .with_agent("ollama-test", "Ollama test agent")
        .with_ai("ollama", "qwen3:0.6b")
        .with_ollama_service()
        .with_skill("ai_assistant", "AI Assistant")
        .build()
    )
