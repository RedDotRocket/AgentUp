# Import the generator to test
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.generator import ProjectGenerator
from tests.utils.test_helpers import create_test_config


class TestProjectGenerator:
    def test_generator_initialization(self, temp_dir: Path):
        config = create_test_config("test-project", ["services"], ["openai"])

        generator = ProjectGenerator(temp_dir, config)

        assert generator.output_dir == temp_dir
        assert generator.config == config
        assert generator.project_name == "test-project"
        assert "services" in generator.features

    def test_generator_features_from_config(self, temp_dir: Path):
        config = create_test_config("feature-test", ["services", "middleware", "auth"], ["openai", "valkey"])

        generator = ProjectGenerator(temp_dir, config)

        assert generator.features == ["services", "middleware", "auth"]
        assert "services" in generator.features
        assert "middleware" in generator.features
        assert "auth" in generator.features

    def test_generator_features_fallback_empty(self, temp_dir: Path):
        config = {"name": "fallback-test"}

        generator = ProjectGenerator(temp_dir, config)

        assert generator.features == []

    def test_ai_provider_context_generation(self, temp_dir: Path):
        config = create_test_config("test", ["services"], ["openai"])
        config["ai_provider_config"] = {"provider": "openai", "model": "gpt-4o-mini", "api_key": "${OPENAI_API_KEY}"}
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_ai_provider_context()
        assert context["ai_provider_config"] is not None
        assert context["llm_provider_config"] is True
        assert context["ai_enabled"] is True
        assert context["has_ai_provider"] is True

    def test_ai_provider_context_no_config(self, temp_dir: Path):
        config = create_test_config("test", ["services"], [])
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_ai_provider_context()
        assert context["ai_provider_config"] is None
        assert context["llm_provider_config"] is False
        assert context["ai_enabled"] is False
        assert context["has_ai_provider"] is False

    def test_replace_template_vars(self, temp_dir: Path):
        config = create_test_config("my-project")
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
    # No longer need template system mocking

    def test_generate_minimal_project(self, temp_dir: Path):
        config = create_test_config("minimal-test", [], [])

        # Mock file operations
        with (
            patch.object(ProjectGenerator, "_generate_template_files") as mock_template,
            patch.object(ProjectGenerator, "_create_env_file") as mock_env,
            patch.object(ProjectGenerator, "_generate_config_files") as mock_config,
        ):
            generator = ProjectGenerator(temp_dir, config)
            generator.generate()

            # Verify methods were called
            mock_template.assert_called_once()
            mock_env.assert_called_once()
            mock_config.assert_called_once()

    def test_generate_standard_project_with_openai(self, temp_dir: Path):
        config = create_test_config("standard-openai-test", ["services", "middleware"], ["openai"])

        with (
            patch.object(ProjectGenerator, "_generate_template_files") as mock_template,
            patch.object(ProjectGenerator, "_create_env_file") as mock_env,
            patch.object(ProjectGenerator, "_generate_config_files") as mock_config,
        ):
            generator = ProjectGenerator(temp_dir, config)
            generator.generate()

            # Verify all generation steps were called
            mock_template.assert_called_once()
            mock_env.assert_called_once()
            mock_config.assert_called_once()

    def test_generate_ollama_project(self, temp_dir: Path):
        config = create_test_config("ollama-test", ["services", "middleware"], ["ollama"])
        config["ai_provider_config"] = {
            "provider": "ollama",
            "model": "qwen3:0.6b",
            "base_url": "http://localhost:11434",
        }

        generator = ProjectGenerator(temp_dir, config)

        # Test AI provider context building
        context = generator._build_ai_provider_context()
        assert context["ai_provider_config"]["provider"] == "ollama"
        assert context["ai_provider_config"]["model"] == "qwen3:0.6b"
        assert context["has_ai_provider"] is True

    def test_generate_anthropic_project(self, temp_dir: Path):
        config = create_test_config("anthropic-test", ["services", "middleware"], ["anthropic"])
        config["ai_provider_config"] = {
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "api_key": "${ANTHROPIC_API_KEY}",
        }

        generator = ProjectGenerator(temp_dir, config)

        # Test AI provider context building
        context = generator._build_ai_provider_context()
        assert context["ai_provider_config"]["provider"] == "anthropic"
        assert context["ai_provider_config"]["model"] == "claude-3-sonnet-20240229"
        assert context["has_ai_provider"] is True


class TestTemplateRendering:
    def test_render_template_context(self, temp_dir: Path):
        config = create_test_config("context-test", ["services", "middleware", "auth"], ["openai", "valkey"])
        config["ai_provider_config"] = {"provider": "openai", "model": "gpt-4o-mini", "api_key": "${OPENAI_API_KEY}"}

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
        assert call_args["has_middleware"] is True
        assert call_args["has_auth"] is True
        assert call_args["ai_provider_config"] is not None
        assert call_args["llm_provider_config"] is True

    def test_render_template_no_llm_provider(self, temp_dir: Path):
        config = create_test_config(
            "no-llm-test",
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
        assert call_args["ai_provider_config"] is None


class TestConfigurationGeneration:
    def test_template_context_features(self, temp_dir: Path):
        config = create_test_config("feature-test", ["services", "middleware", "auth"], ["openai"])
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_feature_flags()
        assert context["has_services"] is True
        assert context["has_middleware"] is True
        assert context["has_auth"] is True
        assert context["has_ai_provider"] is False  # No ai_provider_config set

    def test_template_context_no_features(self, temp_dir: Path):
        config = create_test_config("minimal-test", [], [])
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_feature_flags()
        assert context["has_services"] is False
        assert context["has_middleware"] is False
        assert context["has_security"] is False
        assert context["has_ai_provider"] is False

    def test_backend_contexts(self, temp_dir: Path):
        config = create_test_config("backend-test", ["state_management"], [])
        config["feature_config"] = {"cache_backend": "redis", "state_backend": "memory"}
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_backend_contexts()
        assert context["cache_backend"] == "redis"
        assert context["state_backend"] == "memory"

    def test_security_context(self, temp_dir: Path):
        config = create_test_config("security-test", ["auth"], [])
        config["feature_config"] = {"auth": "jwt", "scope_config": {"security_level": "enterprise"}}
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_security_context()
        assert context["security_enabled"] is True
        assert context["auth_type"] == "jwt"
        assert context["has_enterprise_scopes"] is True


class TestContextGeneration:
    def test_full_template_context(self, temp_dir: Path):
        config = create_test_config("full-test", ["services", "middleware", "auth"], [])
        config["ai_provider_config"] = {"provider": "openai", "model": "gpt-4o-mini", "api_key": "${OPENAI_API_KEY}"}
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_template_context()

        # Test base context
        assert context["project_name"] == "full-test"
        assert "features" in context

        # Test feature flags
        assert context["has_services"] is True
        assert context["has_middleware"] is True
        assert context["has_auth"] is True
        assert context["has_ai_provider"] is True

        # Test AI provider context
        assert context["ai_provider_config"] is not None
        assert context["llm_provider_config"] is True
        assert context["ai_enabled"] is True

    def test_minimal_template_context(self, temp_dir: Path):
        config = create_test_config("minimal-test", [], [])
        generator = ProjectGenerator(temp_dir, config)

        context = generator._build_template_context()

        # Test base context
        assert context["project_name"] == "minimal-test"
        assert context["features"] == []

        # Test feature flags are all false
        assert context["has_services"] is False
        assert context["has_middleware"] is False
        assert context["has_security"] is False
        assert context["has_ai_provider"] is False

        # Test AI provider context is disabled
        assert context["ai_provider_config"] is None
        assert context["llm_provider_config"] is False
        assert context["ai_enabled"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
