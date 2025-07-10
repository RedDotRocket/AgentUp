"""Basic foundation tests to validate the test setup."""

from pathlib import Path
from typing import Any

import pytest

from tests.utils.mock_services import MockLLMResponse, create_mock_services
from tests.utils.test_helpers import (
    AgentConfigBuilder,
    assert_config_has_service,
    build_minimal_config,
    build_standard_config,
    create_test_config,
)


class TestTestFoundation:
    """Test the test foundation itself to ensure everything is working."""

    def test_basic_pytest_setup(self):
        """Test that pytest is working correctly."""
        assert True, "Basic pytest functionality works"

    def test_temp_dir_fixture(self, temp_dir: Path):
        """Test the temp_dir fixture."""
        assert temp_dir.exists(), "Temporary directory should exist"
        assert temp_dir.is_dir(), "Temporary directory should be a directory"

        # Test we can create files in it
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, test!")
        assert test_file.exists(), "Should be able to create files in temp directory"
        assert test_file.read_text() == "Hello, test!", "File content should be preserved"

    def test_sample_agent_config_fixture(self, sample_agent_config: dict[str, Any]):
        """Test the sample agent configuration fixture."""
        assert "agent" in sample_agent_config, "Should have agent section"
        assert "plugins" in sample_agent_config, "Should have plugins section"
        assert "ai_provider" in sample_agent_config, "Should have ai_provider section"
        assert "services" in sample_agent_config, "Should have services section"

        # Test specific values
        assert sample_agent_config["agent"]["name"] == "test-agent"
        assert sample_agent_config["ai_provider"]["provider"] == "openai"
        assert sample_agent_config["ai_provider"]["model"] == "gpt-4o-mini"

    def test_minimal_agent_config_fixture(self, minimal_agent_config: dict[str, Any]):
        """Test the minimal agent configuration fixture."""
        assert "agent" in minimal_agent_config, "Should have agent section"
        assert "plugins" in minimal_agent_config, "Should have plugins section"
        assert minimal_agent_config["agent"]["name"] == "minimal-test"
        assert len(minimal_agent_config["plugins"]) == 1
        assert minimal_agent_config["plugins"][0]["plugin_id"] == "echo"

    def test_provider_specific_configs(
        self, ollama_agent_config: dict[str, Any], anthropic_agent_config: dict[str, Any]
    ):
        """Test provider-specific configuration fixtures."""
        # Test Ollama config
        assert ollama_agent_config["ai_provider"]["provider"] == "ollama"
        assert ollama_agent_config["ai_provider"]["model"] == "qwen3:0.6b"
        assert ollama_agent_config["services"] == {}

        # Test Anthropic config
        assert anthropic_agent_config["ai_provider"]["provider"] == "anthropic"
        assert anthropic_agent_config["ai_provider"]["model"] == "claude-3-haiku-20240307"
        assert anthropic_agent_config["services"] == {}

    def test_project_config_fixture(self, project_config: dict[str, Any]):
        """Test the project configuration fixture."""
        assert "name" in project_config, "Should have project name"
        assert "template" in project_config, "Should have template"
        assert "features" in project_config, "Should have features"
        assert "services" in project_config, "Should have services"

        assert project_config["template"] == "standard"
        assert "services" in project_config["features"]
        assert "ai_provider" in project_config["features"]
        assert "valkey" in project_config["services"]


class TestTestHelpers:
    """Test the test helper functions."""

    def test_create_test_config(self):
        """Test the create_test_config helper."""
        config = create_test_config("my-test", "standard", ["services"], ["openai"])

        assert config["name"] == "my-test"
        assert config["template"] == "standard"
        assert config["features"] == ["services"]
        assert config["services"] == ["openai"]

    def test_assert_config_has_service(self, sample_agent_config: dict[str, Any]):
        """Test the assert_config_has_service helper."""
        # The sample config no longer has openai in services (it's in ai_provider)
        # So we test that the assertion correctly fails
        with pytest.raises(AssertionError):
            assert_config_has_service(sample_agent_config, "openai", "llm")

        # This should also fail
        with pytest.raises(AssertionError):
            assert_config_has_service(sample_agent_config, "nonexistent", "llm")

    def test_agent_config_builder(self):
        """Test the AgentConfigBuilder class."""
        config = (
            AgentConfigBuilder()
            .with_agent("builder-test", "Builder test agent")
            .with_ai("openai", "gpt-4")
            .with_openai_service("openai", "gpt-4")
            .with_skill("test_skill", "Test Skill")
            .build()
        )

        assert config["agent"]["name"] == "builder-test"
        assert config["ai"]["llm_service"] == "openai"
        assert config["ai"]["model"] == "gpt-4"
        assert "openai" in config["services"]
        assert config["services"]["openai"]["model"] == "gpt-4"
        assert len(config["skills"]) == 1
        assert config["skills"][0]["skill_id"] == "test_skill"

    def test_build_predefined_configs(self):
        """Test the predefined config builders."""
        minimal = build_minimal_config()
        standard = build_standard_config()

        # Test minimal
        assert minimal["agent"]["name"] == "minimal-test"
        assert len(minimal["skills"]) == 1
        assert minimal["skills"][0]["skill_id"] == "echo"

        # Test standard
        assert standard["agent"]["name"] == "standard-test"
        assert standard["ai"]["enabled"] is True
        assert "openai" in standard["services"]


class TestMockServices:
    """Test the mock services."""

    def test_mock_llm_response(self):
        """Test the MockLLMResponse class."""
        response = MockLLMResponse("Test response", {"total_tokens": 50})

        assert response.content == "Test response"
        assert response.usage["total_tokens"] == 50
        assert str(response) == "Test response"
        assert response.strip() == "Test response"

    def test_mock_service_registry(self):
        """Test the MockServiceRegistry class."""
        registry = create_mock_services()

        # Test service registration
        assert "openai" in registry.list_services()
        assert "anthropic" in registry.list_services()
        assert "ollama" in registry.list_services()
        assert "valkey" in registry.list_services()

        # Test service retrieval
        openai_service = registry.get_llm("openai")
        assert openai_service is not None

        valkey_service = registry.get_cache("valkey")
        assert valkey_service is not None

    @pytest.mark.asyncio
    async def test_mock_llm_services(self):
        """Test the mock LLM services."""
        registry = create_mock_services()

        # Test OpenAI service
        openai = registry.get_llm("openai")
        response = await openai.generate_response([{"role": "user", "content": "Hello"}])
        assert isinstance(response, MockLLMResponse)
        assert response.content == "Mock OpenAI response"

        # Test Anthropic service
        anthropic = registry.get_llm("anthropic")
        response = await anthropic.generate_response([{"role": "user", "content": "Hello"}])
        assert isinstance(response, MockLLMResponse)
        assert response.content == "Mock Anthropic response"

        # Test Ollama service
        ollama = registry.get_llm("ollama")
        response = await ollama.generate_response([{"role": "user", "content": "Hello"}])
        assert isinstance(response, MockLLMResponse)
        assert response.content == "Mock Ollama response"

    @pytest.mark.asyncio
    async def test_mock_valkey_service(self):
        """Test the mock Valkey service."""
        registry = create_mock_services()
        valkey = registry.get_cache("valkey")

        # Test basic operations
        await valkey.set("test_key", "test_value")
        value = await valkey.get("test_key")
        assert value == "test_value"

        # Test deletion
        deleted = await valkey.delete("test_key")
        assert deleted is True

        value = await valkey.get("test_key")
        assert value is None

    def test_env_vars_fixture(self, env_vars):
        """Test the environment variables fixture."""
        import os

        assert os.environ.get("OPENAI_API_KEY") == "test_openai_key"
        assert os.environ.get("ANTHROPIC_API_KEY") == "test_anthropic_key"
        assert os.environ.get("OLLAMA_BASE_URL") == "http://localhost:11434"
        assert os.environ.get("VALKEY_URL") == "valkey://localhost:6379"


class TestAgentTemplates:
    """Test the agent templates fixture."""

    def test_agent_templates_fixture(self, agent_templates):
        """Test the agent templates fixture."""
        assert "minimal" in agent_templates
        assert "standard" in agent_templates
        assert "full" in agent_templates
        assert "demo" in agent_templates

        # Test template structure
        for _, template_info in agent_templates.items():
            assert "features" in template_info
            assert "description" in template_info
            assert isinstance(template_info["features"], list)
            assert isinstance(template_info["description"], str)

        # Test specific templates
        assert agent_templates["minimal"]["features"] == []
        assert "services" in agent_templates["standard"]["features"]
        assert len(agent_templates["full"]["features"]) > len(agent_templates["standard"]["features"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
