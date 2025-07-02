import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.cli.commands.create_agent import configure_features, create_agent


class TestCreateAgentCommand:
    """Test the create_agent CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_generator(self):
        """Mock the ProjectGenerator class."""
        with patch("agent.cli.commands.create_agent.ProjectGenerator") as mock_gen:
            # Create a mock instance
            mock_instance = Mock()
            mock_gen.return_value = mock_instance
            yield mock_gen

    @pytest.fixture
    def mock_questionary(self):
        """Mock questionary prompts."""
        with patch("agent.cli.commands.create_agent.questionary") as mock_q:
            yield mock_q

    @pytest.fixture
    def mock_template_features(self):
        """Mock all template functions."""
        with (
            patch("agent.cli.commands.create_agent.get_template_features") as mock_features,
            patch("agent.cli.commands.create_agent.get_template_choices") as mock_choices,
            patch("agent.cli.commands.create_agent.get_feature_choices") as mock_feature_choices,
        ):
            mock_features.return_value = {
                "minimal": {"features": []},
                "standard": {"features": ["services", "middleware", "mcp"]},
                "full": {"features": ["services", "middleware", "auth", "state", "multimodal", "mcp", "monitoring"]},
                "demo": {"features": ["services", "middleware", "mcp"]},
            }

            mock_choices.return_value = [
                {"name": "Minimal", "value": "minimal"},
                {"name": "Standard", "value": "standard"},
                {"name": "Full", "value": "full"},
                {"name": "Demo", "value": "demo"},
            ]

            # Mock feature choices with questionary.Choice objects
            from questionary import Choice

            mock_feature_choices.return_value = [
                Choice("External Services", value="services"),
                Choice("Middleware", value="middleware"),
                Choice("Authentication", value="auth"),
                Choice("State Management", value="state"),
                Choice("Multimodal", value="multimodal"),
                Choice("MCP Support", value="mcp"),
                Choice("Monitoring", value="monitoring"),
            ]

            yield mock_features

    def test_create_agent_with_name_argument(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test creating an agent with name provided as argument."""
        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock the service selection questionary (in quick mode, services are still selected)
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            # Use --quick to avoid interactive mode
            result = runner.invoke(create_agent, ["test-agent", "--quick", "--no-git"])

        assert result.exit_code == 0
        assert "✅ Project created successfully!" in result.output

        # Verify generator was called correctly
        mock_generator.assert_called_once()
        call_args = mock_generator.call_args[0]
        assert call_args[0] == temp_dir / "test-agent"  # Directory name (not normalized for simple names)
        assert call_args[1]["name"] == "test-agent"

    def test_create_agent_interactive_mode(
        self, runner, mock_generator, mock_questionary, temp_dir, mock_template_features
    ):
        """Test creating an agent in interactive mode."""
        # Mock questionary responses
        mock_questionary.text.return_value.ask.side_effect = [
            "my-interactive-agent",  # Agent name
            "My awesome interactive agent",  # Description
        ]
        mock_questionary.select.return_value.ask.return_value = "standard"  # Template
        mock_questionary.confirm.return_value.ask.side_effect = [
            False,  # Don't customize features
            False,  # Directory exists confirmation (if needed)
        ]

        # Mock checkbox for service selection (should run even without customization)
        mock_questionary.checkbox.return_value.ask.return_value = ["openai"]

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0
        assert "✅ Project created successfully!" in result.output

        # Verify project configuration
        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["name"] == "my-interactive-agent"
        assert config["description"] == "My awesome interactive agent"
        assert config["template"] == "standard"

    def test_create_agent_quick_mode(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test creating an agent with --quick flag."""
        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["--quick", "quick-agent", "--no-git"])

        assert result.exit_code == 0
        assert "✅ Project created successfully!" in result.output

        # Verify quick mode configuration
        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["name"] == "quick-agent"
        assert config["template"] == "standard"  # Default for quick mode
        assert "features" in config  # Should use template features

    def test_create_agent_minimal_mode(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test creating an agent with --minimal flag."""
        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--minimal", "minimal-agent", "--no-git"])

        assert result.exit_code == 0
        assert "✅ Project created successfully!" in result.output

        # Verify minimal mode configuration
        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["name"] == "minimal-agent"
        assert config["template"] == "minimal"
        assert config["features"] == []  # No features for minimal

    def test_create_agent_with_template_option(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test creating an agent with specific template."""
        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["--quick", "demo-agent", "--template", "demo", "--no-git"])

        assert result.exit_code == 0

        # Verify template was used
        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["template"] == "demo"

    def test_create_agent_with_output_dir(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test creating an agent with custom output directory."""
        custom_dir = temp_dir / "custom_output"

        with patch("agent.cli.commands.create_agent.questionary") as mock_q:
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(
                create_agent, ["--quick", "custom-dir-agent", "--output-dir", str(custom_dir), "--no-git"]
            )

        assert result.exit_code == 0

        # Verify output directory
        call_args = mock_generator.call_args[0]
        assert call_args[0] == custom_dir

    def test_create_agent_directory_exists_cancel(self, runner, mock_questionary, temp_dir, mock_template_features):
        """Test canceling when directory already exists (interactive mode)."""
        # Create existing directory
        existing_dir = temp_dir / "existing-agent"
        existing_dir.mkdir()

        mock_questionary.confirm.return_value.ask.return_value = False  # Don't continue

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            # Remove --quick flag to test interactive mode cancellation
            result = runner.invoke(create_agent, ["existing-agent", "--no-git"])

        assert result.exit_code == 0
        assert "Cancelled." in result.output

    def test_create_agent_directory_exists_quick_mode(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test quick mode automatically continues when directory exists."""
        # Create existing directory
        existing_dir = temp_dir / "existing-agent"
        existing_dir.mkdir()

        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["existing-agent", "--quick", "--no-git"])

        assert result.exit_code == 0
        assert "Directory" in result.output and "already exists. Continuing in quick mode" in result.output
        assert "✅ Project created successfully!" in result.output

    def test_create_agent_git_initialization(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test agent creation with git initialization."""
        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.initialize_git_repo", return_value=True) as mock_git,
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["git-agent", "--quick"])
            # Note: No --no-git flag

        assert result.exit_code == 0
        assert "✅ Git repository initialized" in result.output
        mock_git.assert_called_once()

    def test_create_agent_git_initialization_failure(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test agent creation when git initialization fails."""
        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.initialize_git_repo", return_value=False) as _mock_git,
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["git-fail-agent", "--quick"])

        assert result.exit_code == 0
        assert "Warning: Could not initialize git repository" in result.output

    def test_create_agent_error_handling(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test error handling during agent creation."""
        # Make generator raise an exception
        mock_generator.return_value.generate.side_effect = Exception("Generation failed")

        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["error-agent", "--quick", "--no-git"])

        # Error should be caught and displayed
        assert "Error:" in result.output
        assert "Generation failed" in result.output


class TestServiceSelection:
    """Test service selection logic (critical for Ollama fix)."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_generator(self):
        with patch("agent.cli.commands.create_agent.ProjectGenerator") as mock_gen:
            mock_instance = Mock()
            mock_gen.return_value = mock_instance
            yield mock_gen

    @pytest.fixture
    def mock_questionary(self):
        with patch("agent.cli.commands.create_agent.questionary") as mock_q:
            yield mock_q

    @pytest.fixture
    def mock_template_features(self):
        with patch("agent.cli.commands.create_agent.get_template_features") as mock_features:
            mock_features.return_value = {"standard": {"features": ["services", "middleware", "mcp"]}}
            yield mock_features

    def test_service_selection_with_ollama(
        self, runner, mock_generator, mock_questionary, temp_dir, mock_template_features
    ):
        """Test service selection when Ollama is chosen (critical test)."""
        # Mock questionary responses
        mock_questionary.text.return_value.ask.side_effect = ["ollama-service-test", "Test Ollama service selection"]
        mock_questionary.select.return_value.ask.return_value = "standard"
        mock_questionary.confirm.return_value.ask.return_value = False  # Don't customize

        # Mock service selection - user selects Ollama
        mock_questionary.checkbox.return_value.ask.return_value = ["ollama"]

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0

        # Verify Ollama was selected in configuration
        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["services"] == ["ollama"]

    def test_service_selection_with_anthropic(
        self, runner, mock_generator, mock_questionary, temp_dir, mock_template_features
    ):
        """Test service selection when Anthropic is chosen."""
        mock_questionary.text.return_value.ask.side_effect = [
            "anthropic-service-test",
            "Test Anthropic service selection",
        ]
        mock_questionary.select.return_value.ask.return_value = "standard"
        mock_questionary.confirm.return_value.ask.return_value = False
        mock_questionary.checkbox.return_value.ask.return_value = ["anthropic"]

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0

        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["services"] == ["anthropic"]

    def test_service_selection_multiple_services(
        self, runner, mock_generator, mock_questionary, temp_dir, mock_template_features
    ):
        """Test selecting multiple services."""
        mock_questionary.text.return_value.ask.side_effect = ["multi-service-test", "Test multiple services"]
        mock_questionary.select.return_value.ask.return_value = "standard"
        mock_questionary.confirm.return_value.ask.return_value = False
        mock_questionary.checkbox.return_value.ask.return_value = ["openai", "valkey", "postgres"]

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0

        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert set(config["services"]) == {"openai", "valkey", "postgres"}

    def test_service_selection_no_services(
        self, runner, mock_generator, mock_questionary, temp_dir, mock_template_features
    ):
        """Test when user selects no services."""
        mock_questionary.text.return_value.ask.side_effect = ["no-service-test", "Test no services"]
        mock_questionary.select.return_value.ask.return_value = "standard"
        mock_questionary.confirm.return_value.ask.return_value = False
        mock_questionary.checkbox.return_value.ask.return_value = []  # No services

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0

        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["services"] == []

    def test_service_selection_always_runs_when_services_in_features(
        self, runner, mock_generator, mock_questionary, temp_dir, mock_template_features
    ):
        """Test that service selection runs even when not customizing features (critical fix)."""
        mock_questionary.text.return_value.ask.side_effect = [
            "service-always-test",
            "Test service selection always runs",
        ]
        mock_questionary.select.return_value.ask.return_value = "standard"

        # Key test: User says NO to customizing features
        mock_questionary.confirm.return_value.ask.return_value = False

        # But service selection should still run
        mock_checkbox = Mock()
        mock_checkbox.ask.return_value = ["ollama"]
        mock_questionary.checkbox.return_value = mock_checkbox

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0

        # Verify checkbox was called for service selection
        mock_checkbox.ask.assert_called_once()

        # Verify Ollama was set in config
        call_args = mock_generator.call_args[0]
        config = call_args[1]
        assert config["services"] == ["ollama"]


class TestFeatureCustomization:
    """Test feature customization flow."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_generator(self):
        with patch("agent.cli.commands.create_agent.ProjectGenerator") as mock_gen:
            mock_instance = Mock()
            mock_gen.return_value = mock_instance
            yield mock_gen

    @pytest.fixture
    def mock_questionary(self):
        with patch("agent.cli.commands.create_agent.questionary") as mock_q:
            yield mock_q

    def test_feature_customization_flow(self, runner, mock_generator, mock_questionary, temp_dir):
        """Test customizing features during agent creation."""
        with (
            patch("agent.cli.commands.create_agent.get_template_features") as mock_features,
            patch("agent.cli.commands.create_agent.get_feature_choices") as mock_choices,
        ):
            mock_features.return_value = {"standard": {"features": ["services", "middleware"]}}

            # Mock feature choices
            from questionary import Choice

            mock_choices.return_value = [
                Choice("External Services", value="services", checked=True),
                Choice("Middleware", value="middleware", checked=True),
                Choice("Authentication", value="auth", checked=False),
                Choice("State Management", value="state", checked=False),
            ]

            mock_questionary.text.return_value.ask.side_effect = ["custom-features-test", "Test custom features"]
            mock_questionary.select.return_value.ask.return_value = "standard"
            mock_questionary.confirm.return_value.ask.side_effect = [
                True,  # Yes, customize features
                False,  # For any directory confirmation
            ]

            # User selects additional features
            mock_questionary.checkbox.return_value.ask.side_effect = [
                ["services", "middleware", "auth", "state"],  # Feature selection
                ["openai", "valkey"],  # Service selection
            ]

            # Mock configure_features call
            with patch("agent.cli.commands.create_agent.configure_features") as mock_configure:
                mock_configure.return_value = {"auth": "api_key", "middleware": ["logging", "cache"]}

                with patch("pathlib.Path.cwd", return_value=temp_dir):
                    result = runner.invoke(create_agent, ["--no-git"])

                assert result.exit_code == 0

                # Verify feature configuration
                call_args = mock_generator.call_args[0]
                config = call_args[1]
                assert set(config["features"]) == {"services", "middleware", "auth", "state"}
                assert config["feature_config"]["auth"] == "api_key"
                assert config["services"] == ["openai", "valkey"]

    def test_configure_features_middleware(self, mock_questionary):
        """Test configure_features function for middleware."""
        mock_questionary.checkbox.return_value.ask.return_value = ["rate_limit", "cache", "logging"]

        result = configure_features(["middleware"])

        assert result["middleware"] == ["rate_limit", "cache", "logging"]

    def test_configure_features_auth(self, mock_questionary):
        """Test configure_features function for authentication."""
        mock_questionary.select.return_value.ask.return_value = "jwt"

        result = configure_features(["auth"])

        assert result["auth"] == "jwt"

    def test_configure_features_multiple(self, mock_questionary):
        """Test configure_features with multiple features."""
        mock_questionary.checkbox.return_value.ask.return_value = ["rate_limit", "cache"]
        mock_questionary.select.return_value.ask.return_value = "oauth2"

        result = configure_features(["middleware", "auth"])

        assert result["middleware"] == ["rate_limit", "cache"]
        assert result["auth"] == "oauth2"


class TestProjectNameHandling:
    """Test project name normalization and handling."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_generator(self):
        with patch("agent.cli.commands.create_agent.ProjectGenerator") as mock_gen:
            mock_instance = Mock()
            mock_gen.return_value = mock_instance
            yield mock_gen

    @pytest.fixture
    def mock_template_features(self):
        with patch("agent.cli.commands.create_agent.get_template_features") as mock_features:
            mock_features.return_value = {"standard": {"features": ["services", "middleware", "mcp"]}}
            yield mock_features

    def test_project_name_normalization(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test that project names are normalized for directory names."""
        test_cases = [
            ("My Agent", "my_agent"),
            ("test-agent", "test-agent"),  # Hyphens are preserved, only spaces become underscores
            ("Test Agent 123", "test_agent_123"),
            ("UPPERCASE", "uppercase"),
        ]

        for input_name, expected_dir in test_cases:
            with (
                patch("pathlib.Path.cwd", return_value=temp_dir),
                patch("agent.cli.commands.create_agent.questionary") as mock_q,
            ):
                # Mock service selection
                mock_q.checkbox.return_value.ask.return_value = ["openai"]

                result = runner.invoke(create_agent, [input_name, "--quick", "--no-git"])

            assert result.exit_code == 0

            # Verify directory name normalization
            call_args = mock_generator.call_args[0]
            output_dir = call_args[0]
            assert output_dir.name == expected_dir

            # But config should preserve original name
            config = call_args[1]
            assert config["name"] == input_name


class TestCliOutput:
    """Test CLI output and user feedback."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_generator(self):
        with patch("agent.cli.commands.create_agent.ProjectGenerator") as mock_gen:
            mock_instance = Mock()
            mock_gen.return_value = mock_instance
            yield mock_gen

    @pytest.fixture
    def mock_questionary(self):
        with patch("agent.cli.commands.create_agent.questionary") as mock_q:
            yield mock_q

    @pytest.fixture
    def mock_template_features(self):
        with patch("agent.cli.commands.create_agent.get_template_features") as mock_features:
            mock_features.return_value = {"standard": {"features": ["services", "middleware", "mcp"]}}
            yield mock_features

    def test_cli_output_formatting(self, runner, mock_generator, temp_dir, mock_template_features):
        """Test that CLI output is properly formatted."""
        with (
            patch("pathlib.Path.cwd", return_value=temp_dir),
            patch("agent.cli.commands.create_agent.questionary") as mock_q,
        ):
            # Mock service selection
            mock_q.checkbox.return_value.ask.return_value = ["openai"]

            result = runner.invoke(create_agent, ["output-test", "--quick", "--no-git"])

        # Check for expected output elements
        assert "Create your AI agent:" in result.output
        assert "📁 Creating project..." in result.output
        assert "✅ Project created successfully!" in result.output
        assert "Next steps:" in result.output
        assert "cd output-test" in result.output  # Directory name preserves hyphens
        assert "uv sync" in result.output
        assert "agentup dev" in result.output

    def test_cli_cancel_output(self, runner, mock_questionary):
        """Test output when user cancels."""
        mock_questionary.text.return_value.ask.return_value = None  # Cancel

        result = runner.invoke(create_agent, ["--no-git"])

        assert result.exit_code == 0
        assert "Cancelled." in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
