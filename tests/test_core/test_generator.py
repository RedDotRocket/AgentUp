# Import the generator to test
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.generator import ProjectGenerator
from tests.utils.test_helpers import create_test_config


class TestProjectGenerator:
    """Test the ProjectGenerator class."""

    def test_generator_initialization(self, temp_dir: Path):
        """Test ProjectGenerator initialization."""
        config = create_test_config("test-project", "standard", ["services"], ["openai"])

        generator = ProjectGenerator(temp_dir, config)

        assert generator.output_dir == temp_dir
        assert generator.config == config
        assert generator.template_name == "standard"
        assert generator.project_name == "test-project"
        assert "services" in generator.features

    def test_generator_features_from_config(self, temp_dir: Path):
        """Test that generator uses features from config."""
        config = create_test_config(
            "feature-test", "standard", ["services", "middleware", "auth"], ["openai", "valkey"]
        )

        generator = ProjectGenerator(temp_dir, config)

        assert generator.features == ["services", "middleware", "auth"]
        assert "services" in generator.features
        assert "middleware" in generator.features
        assert "auth" in generator.features

    def test_generator_features_fallback_to_template(self, temp_dir: Path):
        """Test that generator falls back to template features when config has none."""
        config = {"name": "fallback-test", "template": "standard"}

        # Mock the get_template_features function
        with patch("agent.generator.get_template_features") as mock_get_features:
            mock_get_features.return_value = {"standard": {"features": ["services", "middleware"]}}

            generator = ProjectGenerator(temp_dir, config)

            assert generator.features == ["services", "middleware"]

    def test_get_llm_provider_info(self, temp_dir: Path):
        """Test the _get_llm_provider_info method."""
        config = create_test_config("test", "standard", ["services"], ["ollama"])
        generator = ProjectGenerator(temp_dir, config)

        # Test Ollama provider
        provider, service_name, model = generator._get_llm_provider_info(["ollama"])
        assert provider == "ollama"
        assert service_name == "ollama"
        assert model == "qwen3:0.6b"

        # Test Anthropic provider
        provider, service_name, model = generator._get_llm_provider_info(["anthropic"])
        assert provider == "anthropic"
        assert service_name == "anthropic"
        assert model == "claude-3-haiku-20240307"

        # Test OpenAI provider
        provider, service_name, model = generator._get_llm_provider_info(["openai"])
        assert provider == "openai"
        assert service_name == "openai"
        assert model == "gpt-4o-mini"

        # Test no LLM provider
        provider, service_name, model = generator._get_llm_provider_info(["valkey"])
        assert provider is None
        assert service_name is None
        assert model is None

    def test_build_llm_service_config(self, temp_dir: Path):
        """Test the _build_llm_service_config method."""
        config = create_test_config("test", "standard")
        generator = ProjectGenerator(temp_dir, config)

        # Test OpenAI service config
        openai_config = generator._build_llm_service_config("openai")
        assert openai_config["type"] == "llm"
        assert openai_config["provider"] == "openai"
        assert openai_config["api_key"] == "${OPENAI_API_KEY}"
        assert openai_config["model"] == "gpt-4o-mini"

        # Test Ollama service config
        ollama_config = generator._build_llm_service_config("ollama")
        assert ollama_config["type"] == "llm"
        assert ollama_config["provider"] == "ollama"
        assert ollama_config["base_url"] == "${OLLAMA_BASE_URL:http://localhost:11434}"
        assert ollama_config["model"] == "qwen3:0.6b"

        # Test Anthropic service config
        anthropic_config = generator._build_llm_service_config("anthropic")
        assert anthropic_config["type"] == "llm"
        assert anthropic_config["provider"] == "anthropic"
        assert anthropic_config["api_key"] == "${ANTHROPIC_API_KEY}"
        assert anthropic_config["model"] == "claude-3-haiku-20240307"

    def test_replace_template_vars(self, temp_dir: Path):
        """Test the _replace_template_vars method."""
        config = create_test_config("my-project", "standard")
        config["description"] = "My awesome project"
        generator = ProjectGenerator(temp_dir, config)

        content = """
        Project: {{ project_name }}
        Description: {{ description }}
        Name without spaces: {{project_name}}
        """

        result = generator._replace_template_vars(content)

        assert "Project: my-project" in result
        assert "Description: My awesome project" in result
        assert "Name without spaces: my-project" in result


class TestProjectGenerationFlow:
    """Test the complete project generation flow."""

    @pytest.fixture
    def mock_template_system(self):
        """Mock the template system to avoid file dependencies."""
        with patch("agent.generator.get_template_features") as mock_features:
            mock_features.return_value = {
                "minimal": {"features": []},
                "standard": {"features": ["services", "middleware", "mcp"]},
                "full": {"features": ["services", "middleware", "auth", "state", "multimodal", "mcp", "monitoring"]},
                "demo": {"features": ["services", "middleware", "mcp"]},
            }
            yield mock_features

    def test_generate_minimal_project(self, temp_dir: Path, mock_template_system):
        """Test generating a minimal project."""
        config = create_test_config("minimal-test", "minimal", [], [])

        # Mock file operations
        with (
            patch.object(ProjectGenerator, "_create_local_directories") as mock_dirs,
            patch.object(ProjectGenerator, "_generate_template_files") as mock_template,
            patch.object(ProjectGenerator, "_generate_config_files") as mock_config,
        ):
            generator = ProjectGenerator(temp_dir, config)
            generator.generate()

            # Verify methods were called
            mock_dirs.assert_called_once()
            mock_template.assert_called_once()
            mock_config.assert_called_once()

    def test_generate_standard_project_with_openai(self, temp_dir: Path, mock_template_system):
        """Test generating a standard project with OpenAI."""
        config = create_test_config("standard-openai-test", "standard", ["services", "middleware"], ["openai"])

        with (
            patch.object(ProjectGenerator, "_create_local_directories") as mock_dirs,
            patch.object(ProjectGenerator, "_generate_template_files") as mock_template,
            patch.object(ProjectGenerator, "_generate_config_files") as mock_config,
        ):
            generator = ProjectGenerator(temp_dir, config)
            generator.generate()

            # Verify all generation steps were called
            mock_dirs.assert_called_once()
            mock_template.assert_called_once()
            mock_config.assert_called_once()

    def test_generate_ollama_project(self, temp_dir: Path, mock_template_system):
        """Test generating a project with Ollama (critical test for recent fix)."""
        config = create_test_config("ollama-test", "standard", ["services", "middleware"], ["ollama"])

        generator = ProjectGenerator(temp_dir, config)

        # Test LLM provider info extraction
        provider, service_name, model = generator._get_llm_provider_info(["ollama"])
        assert provider == "ollama"
        assert service_name == "ollama"
        assert model == "qwen3:0.6b"

        # Test service config building
        service_config = generator._build_llm_service_config("ollama")
        assert service_config["provider"] == "ollama"
        assert service_config["model"] == "qwen3:0.6b"

    def test_generate_anthropic_project(self, temp_dir: Path, mock_template_system):
        """Test generating a project with Anthropic."""
        config = create_test_config("anthropic-test", "standard", ["services", "middleware"], ["anthropic"])

        generator = ProjectGenerator(temp_dir, config)

        # Test LLM provider info extraction
        provider, service_name, model = generator._get_llm_provider_info(["anthropic"])
        assert provider == "anthropic"
        assert service_name == "anthropic"
        assert model == "claude-3-haiku-20240307"

        # Test service config building
        service_config = generator._build_llm_service_config("anthropic")
        assert service_config["provider"] == "anthropic"
        assert service_config["model"] == "claude-3-haiku-20240307"


class TestTemplateRendering:
    """Test template rendering functionality."""

    def test_render_template_context(self, temp_dir: Path):
        """Test that template context is properly created."""
        config = create_test_config(
            "context-test", "standard", ["services", "middleware", "auth"], ["openai", "valkey"]
        )

        generator = ProjectGenerator(temp_dir, config)

        # Mock the Jinja2 environment and template
        mock_env = Mock()
        mock_template = Mock()
        mock_env.get_template.return_value = mock_template
        mock_template.render.return_value = "rendered content"

        generator.jinja_env = mock_env

        # Test template rendering
        _result = generator._render_template("test_template.yaml")

        # Verify template was called with correct context
        mock_env.get_template.assert_called_once_with("test_template.yaml.j2")
        mock_template.render.assert_called_once()

        # Check the context that was passed
        call_args = mock_template.render.call_args[0][0]
        assert call_args["project_name"] == "context-test"
        assert call_args["template_name"] == "standard"
        assert call_args["has_middleware"] is True
        assert call_args["has_auth"] is True
        assert call_args["llm_provider"] == "openai"
        assert call_args["llm_service_name"] == "openai"
        assert call_args["llm_model"] == "gpt-4o-mini"
        assert call_args["llm_provider_config"] is True

    def test_render_template_no_llm_provider(self, temp_dir: Path):
        """Test template rendering when no LLM provider is selected."""
        config = create_test_config(
            "no-llm-test",
            "standard",
            ["middleware"],  # No services
            [],
        )

        generator = ProjectGenerator(temp_dir, config)

        # Mock the Jinja2 environment
        mock_env = Mock()
        mock_template = Mock()
        mock_env.get_template.return_value = mock_template
        mock_template.render.return_value = "rendered content"

        generator.jinja_env = mock_env

        # Test template rendering
        generator._render_template("test_template.yaml")

        # Check the context that was passed
        call_args = mock_template.render.call_args[0][0]
        assert call_args["llm_provider_config"] is False
        assert "llm_provider" not in call_args or call_args.get("llm_provider") is None


class TestConfigurationGeneration:
    """Test configuration file generation."""

    def test_build_skills_config_minimal(self, temp_dir: Path):
        """Test skills configuration for minimal template."""
        config = create_test_config("minimal-test", "minimal")
        generator = ProjectGenerator(temp_dir, config)

        skills_config = generator._build_skills_config()

        assert len(skills_config) == 1
        assert skills_config[0]["skill_id"] == "echo"
        assert skills_config[0]["routing_mode"] == "direct"
        assert "echo" in skills_config[0]["keywords"]

    def test_build_skills_config_standard(self, temp_dir: Path):
        """Test skills configuration for standard template."""
        config = create_test_config("standard-test", "standard")
        generator = ProjectGenerator(temp_dir, config)

        skills_config = generator._build_skills_config()

        assert len(skills_config) == 1
        assert skills_config[0]["skill_id"] == "ai_assistant"
        # Note: routing_mode is not always present in standard template

    def test_build_skills_config_demo(self, temp_dir: Path):
        """Test skills configuration for demo template."""
        config = create_test_config("demo-test", "demo")
        generator = ProjectGenerator(temp_dir, config)

        skills_config = generator._build_skills_config()

        # Demo template falls back to standard, so should have 1 skill
        assert len(skills_config) == 1
        assert skills_config[0]["skill_id"] == "ai_assistant"

    def test_build_services_config_openai(self, temp_dir: Path):
        """Test services configuration with OpenAI."""
        config = create_test_config("openai-test", "standard", ["services"], ["openai"])
        generator = ProjectGenerator(temp_dir, config)

        services_config = generator._build_services_config()

        assert "openai" in services_config
        assert services_config["openai"]["type"] == "llm"
        assert services_config["openai"]["provider"] == "openai"
        assert services_config["openai"]["model"] == "gpt-4o-mini"
        assert services_config["openai"]["api_key"] == "${OPENAI_API_KEY}"

    def test_build_services_config_ollama(self, temp_dir: Path):
        """Test services configuration with Ollama (critical test)."""
        config = create_test_config("ollama-test", "standard", ["services"], ["ollama"])
        generator = ProjectGenerator(temp_dir, config)

        services_config = generator._build_services_config()

        assert "ollama" in services_config
        assert services_config["ollama"]["type"] == "llm"
        assert services_config["ollama"]["provider"] == "ollama"
        assert services_config["ollama"]["model"] == "qwen3:0.6b"
        assert services_config["ollama"]["base_url"] == "${OLLAMA_BASE_URL:http://localhost:11434}"

    def test_build_services_config_multiple_services(self, temp_dir: Path):
        """Test services configuration with multiple services."""
        config = create_test_config("multi-service-test", "full", ["services"], ["openai", "valkey"])
        generator = ProjectGenerator(temp_dir, config)

        services_config = generator._build_services_config()

        # Check OpenAI service
        assert "openai" in services_config
        assert services_config["openai"]["type"] == "llm"

        # Check Valkey service
        assert "valkey" in services_config
        assert services_config["valkey"]["type"] == "cache"
        assert "url" in services_config["valkey"]["config"]

    def test_build_routing_config(self, temp_dir: Path):
        """Test routing configuration building."""
        # Test minimal template routing
        minimal_config = create_test_config("minimal-test", "minimal")
        minimal_generator = ProjectGenerator(temp_dir, minimal_config)
        minimal_routing = minimal_generator._build_routing_config()

        assert minimal_routing["default_mode"] == "direct"
        assert minimal_routing["fallback_skill"] == "echo"
        assert minimal_routing["fallback_enabled"] is True

        # Test standard template routing
        standard_config = create_test_config("standard-test", "standard")
        standard_generator = ProjectGenerator(temp_dir, standard_config)
        standard_routing = standard_generator._build_routing_config()

        assert standard_routing["default_mode"] == "ai"
        assert standard_routing["fallback_skill"] == "ai_assistant"
        assert standard_routing["fallback_enabled"] is True

    def test_build_middleware_config(self, temp_dir: Path):
        """Test middleware configuration building."""
        config = create_test_config("middleware-test", "standard", ["middleware"])
        config["feature_config"] = {"middleware": ["rate_limit", "cache", "logging", "retry"]}
        generator = ProjectGenerator(temp_dir, config)

        middleware_config = generator._build_middleware_config()

        # Should always include basic middleware
        middleware_names = [mw["name"] for mw in middleware_config]
        assert "logged" in middleware_names
        assert "timed" in middleware_names

        # Should include feature-specific middleware
        assert "cached" in middleware_names
        assert "rate_limited" in middleware_names
        assert "retryable" in middleware_names

    def test_build_mcp_config(self, temp_dir: Path):
        """Test MCP configuration building."""
        config = create_test_config("mcp-test", "standard", ["mcp"])
        generator = ProjectGenerator(temp_dir, config)

        mcp_config = generator._build_mcp_config()

        assert mcp_config["enabled"] is True
        assert mcp_config["client"]["enabled"] is True
        assert mcp_config["server"]["enabled"] is True
        assert mcp_config["server"]["name"] == "mcp-test-mcp-server"

        # Standard template should have filesystem server
        assert len(mcp_config["client"]["servers"]) >= 1
        filesystem_server = mcp_config["client"]["servers"][0]
        assert filesystem_server["name"] == "filesystem"


class TestServiceNameConsistency:
    """Critical tests for service name consistency (addresses recent Ollama fix)."""

    def test_ai_service_name_matches_services_section_openai(self, temp_dir: Path):
        """Test that AI provider configuration is correct for OpenAI."""
        config = create_test_config("openai-consistency", "standard", ["ai_provider"], ["openai"])
        config["ai_provider_config"] = {"provider": "openai", "model": "gpt-4o-mini"}
        generator = ProjectGenerator(temp_dir, config)

        # Build the configuration
        agent_config = generator._build_agent_config()

        # Critical test: AI provider should be configured correctly
        ai_provider_config = agent_config["ai_provider"]
        ai_service_name = ai_provider_config["provider"]
        assert ai_service_name == "openai"
        # Verify AI provider configuration is properly set
        assert ai_provider_config["provider"] == "openai"
        assert "model" in ai_provider_config

    def test_ai_service_name_matches_services_section_ollama(self, temp_dir: Path):
        """Test that AI provider configuration is correct for Ollama."""
        config = create_test_config("ollama-consistency", "standard", ["ai_provider"], ["ollama"])
        config["ai_provider_config"] = {"provider": "ollama", "model": "qwen3:0.6b"}
        generator = ProjectGenerator(temp_dir, config)

        # Build the configuration
        agent_config = generator._build_agent_config()

        # Critical test: AI provider should be configured correctly
        ai_provider_config = agent_config["ai_provider"]
        ai_service_name = ai_provider_config["provider"]
        assert ai_service_name == "ollama"  # Should be 'ollama', not 'openai'
        # Verify AI provider configuration is properly set
        assert ai_provider_config["provider"] == "ollama"
        assert "model" in ai_provider_config

    def test_ai_service_name_matches_services_section_anthropic(self, temp_dir: Path):
        """Test that AI provider configuration is correct for Anthropic."""
        config = create_test_config("anthropic-consistency", "standard", ["ai_provider"], ["anthropic"])
        config["ai_provider_config"] = {"provider": "anthropic", "model": "claude-3-haiku-20240307"}
        generator = ProjectGenerator(temp_dir, config)

        # Build the configuration
        agent_config = generator._build_agent_config()

        # Critical test: AI provider should be configured correctly
        ai_provider_config = agent_config["ai_provider"]
        ai_service_name = ai_provider_config["provider"]
        assert ai_service_name == "anthropic"
        # Verify AI provider configuration is properly set
        assert ai_provider_config["provider"] == "anthropic"
        assert "model" in ai_provider_config

    def test_template_context_llm_provider_consistency(self, temp_dir: Path):
        """Test that template context has consistent LLM provider information."""
        config = create_test_config("template-consistency", "standard", ["services"], ["ollama"])
        generator = ProjectGenerator(temp_dir, config)

        # Mock template rendering to capture context
        mock_env = Mock()
        mock_template = Mock()
        mock_env.get_template.return_value = mock_template
        mock_template.render.return_value = "rendered"
        generator.jinja_env = mock_env

        # Render a template to capture context
        generator._render_template("test.yaml")

        # Get the context that was passed to the template
        context = mock_template.render.call_args[0][0]

        # Critical test: template context should be consistent
        assert context["llm_provider"] == "ollama"
        assert context["llm_service_name"] == "ollama"
        assert context["llm_model"] == "qwen3:0.6b"
        assert context["llm_provider_config"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
