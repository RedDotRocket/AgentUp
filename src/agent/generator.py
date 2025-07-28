import re
import secrets
import string
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader

from .config.model import AgentConfig, MiddlewareConfig

logger = structlog.get_logger(__name__)

# Default values from configuration models
_default_agent_config = AgentConfig()
_default_middleware_config = MiddlewareConfig()

DEFAULT_AUTH_TYPE = "api_key"
DEFAULT_CACHE_BACKEND = _default_middleware_config.caching["backend"]
DEFAULT_STATE_BACKEND = DEFAULT_CACHE_BACKEND  # Use same default as cache
DEFAULT_ENVIRONMENT = _default_agent_config.environment


class ProjectGenerator:
    """Generate Agent projects from templates."""

    def __init__(self, output_dir: Path, config: dict[str, Any], features: list[str] = None):
        self.output_dir = Path(output_dir)
        self.config = config
        self.project_name = config["name"]
        self.features = features if features is not None else self._get_features()

        # Setup Jinja2 environment
        templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir), autoescape=True, trim_blocks=True, lstrip_blocks=True
        )

        # Add custom functions to Jinja2 environment
        self.jinja_env.globals["generate_api_key"] = self._generate_api_key
        self.jinja_env.globals["generate_jwt_secret"] = self._generate_jwt_secret
        self.jinja_env.globals["generate_client_secret"] = self._generate_client_secret

    # ============================================================================
    # PUBLIC API
    # ============================================================================

    def generate(self):
        """Generate the project structure."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate all project files
        self._generate_template_files()
        self._create_env_file()
        self._generate_config_files()

    # ============================================================================
    # CONFIGURATION & FEATURES
    # ============================================================================

    def _get_features(self) -> list[str]:
        """Get enabled features from config."""
        return self.config.get("features", [])

    # ============================================================================
    # FILE GENERATION
    # ============================================================================

    def _generate_template_files(self):
        """Generate files from Jinja2 templates (docs/static files)."""
        # Core project files
        self._write_template_file("pyproject.toml")
        self._write_template_file("README.md")
        self._write_template_file(".gitignore")

        # Generate deployment files if deployment feature is enabled
        if "deployment" in self.features:
            self._generate_deployment_files()

    def _generate_deployment_files(self):
        """Generate deployment files based on feature configuration."""
        feature_config = self.config.get("feature_config", {})

        # Docker files
        if feature_config.get("docker_enabled", True):
            self._write_template_file("Dockerfile")
            self._write_template_file("docker-compose.yml")

        # Helm charts
        if feature_config.get("helm_enabled", True):
            self._generate_helm_charts()

    def _generate_helm_charts(self):
        """Generate Helm chart files."""
        helm_dir = self.output_dir / "helm"
        helm_templates_dir = helm_dir / "templates"

        # Create directories
        helm_dir.mkdir(exist_ok=True)
        helm_templates_dir.mkdir(exist_ok=True)

        # Generate Helm chart files
        helm_files = {
            "helm/Chart.yaml": helm_dir / "Chart.yaml",
            "helm/values.yaml": helm_dir / "values.yaml",
            "helm/templates/deployment.yaml": helm_templates_dir / "deployment.yaml",
            "helm/templates/service.yaml": helm_templates_dir / "service.yaml",
            "helm/templates/_helpers.tpl": helm_templates_dir / "_helpers.tpl",
        }

        for template_path, output_path in helm_files.items():
            content = self._render_template(template_path)
            output_path.write_text(content)

    def _create_env_file(self):
        """Create .env file for environment variables."""
        env_file = self.output_dir / ".env"
        if not env_file.exists():
            env_content = self._render_template(".env")
            env_file.write_text(env_content)

    def _generate_config_files(self):
        """Generate configuration files."""
        config_path = self.output_dir / "agentup.yml"
        config_content = self._render_template("config/agentup.yml")
        config_path.write_text(config_content)

    def _write_template_file(self, template_name: str):
        """Helper to render template and write to output directory."""
        content = self._render_template(template_name)
        output_path = self.output_dir / template_name
        output_path.write_text(content)

    # ============================================================================
    # TEMPLATE RENDERING
    # ============================================================================

    def _render_template(self, template_path: str) -> str:
        """
        Render a template file with project context using Jinja2.

        Args:
            template_path: Path to the template file relative to templates directory.
        Returns:
            Rendered template content.
        """
        template_filename = self._get_template_filename(template_path)
        context = self._build_template_context()

        template = self.jinja_env.get_template(template_filename)
        return template.render(context)

    def _get_template_filename(self, template_path: str) -> str:
        """Convert template path to template filename with .j2 extension."""
        if template_path.startswith("src/agent/"):
            # For src/agent paths, strip the path prefix and only use filename
            return Path(template_path).name + ".j2"
        else:
            # For other paths, preserve the path structure
            return template_path + ".j2"

    def _build_template_context(self) -> dict[str, Any]:
        """Build the complete context dictionary for template rendering."""
        context = self._build_base_context()
        context.update(self._build_feature_flags())
        context.update(self._build_ai_provider_context())
        context.update(self._build_security_context())
        context.update(self._build_backend_contexts())
        context.update(self._build_development_context())

        return context

    def _build_base_context(self) -> dict[str, Any]:
        """Build base template context with project information."""
        return {
            "project_name": self.project_name,
            "project_name_snake": self._to_snake_case(self.project_name),
            "project_name_title": self._to_title_case(self.project_name),
            "description": self.config.get("description", ""),
            "features": self.features,
            "feature_config": self.config.get("feature_config", {}),
            "has_env_file": True,  # Most agents will have .env file
        }

    def _build_feature_flags(self) -> dict[str, Any]:
        """Build feature flag context variables."""
        return {
            "has_ai_provider": "ai_provider" in self.features,
            "has_services": "services" in self.features,
            "has_security": "security" in self.features,
            "has_middleware": "middleware" in self.features,
            "has_state_management": "state_management" in self.features,
            "has_auth": "auth" in self.features,
            "has_mcp": "mcp" in self.features,
            "has_push_notifications": "push_notifications" in self.features,
            "has_development": "development" in self.features,
            "has_deployment": "deployment" in self.features,
        }

    def _build_ai_provider_context(self) -> dict[str, Any]:
        """Build AI provider context for templates."""
        ai_provider_config = self.config.get("ai_provider_config")

        if ai_provider_config:
            return {
                "ai_provider_config": ai_provider_config,
                "llm_provider_config": True,
                "ai_enabled": True,
                "has_ai_provider": True,
            }
        else:
            return {
                "ai_provider_config": None,
                "llm_provider_config": False,
                "ai_enabled": False,
                "has_ai_provider": False,
            }

    def _build_security_context(self) -> dict[str, Any]:
        """Build security and authentication context."""
        auth_enabled = "auth" in self.features
        auth_type = self.config.get("feature_config", {}).get("auth", DEFAULT_AUTH_TYPE)
        scope_config = self.config.get("feature_config", {}).get("scope_config", {})
        oauth2_provider = self.config.get("feature_config", {}).get("oauth2_provider")

        context = {
            "security_enabled": auth_enabled,
            "auth_type": auth_type,
            "scope_hierarchy_enabled": bool(scope_config.get("scope_hierarchy")),
            "has_enterprise_scopes": scope_config.get("security_level") == "enterprise",
            "context_aware_middleware": "middleware" in self.features and auth_enabled,
        }

        # Add OAuth2 provider for template
        if auth_type == "oauth2" and oauth2_provider:
            context["oauth2_provider"] = oauth2_provider

        return context

    def _build_backend_contexts(self) -> dict[str, Any]:
        """Build backend configuration contexts (cache, state)."""
        feature_config = self.config.get("feature_config", {})

        # Cache backend
        cache_backend = feature_config.get("cache_backend", DEFAULT_CACHE_BACKEND)

        # State backend
        state_backend = None
        if "state_backend" in feature_config:
            state_backend = feature_config["state_backend"]
        elif "state_management" in self.features:
            state_backend = DEFAULT_STATE_BACKEND

        return {
            "cache_backend": cache_backend,
            "state_backend": state_backend,
        }

    def _build_development_context(self) -> dict[str, Any]:
        """Build development configuration context."""
        feature_config = self.config.get("feature_config", {})

        return {
            "development_enabled": feature_config.get("development_enabled", False),
            "filesystem_plugins_enabled": feature_config.get("filesystem_plugins_enabled", False),
            "plugin_directory": feature_config.get("plugin_directory"),
        }

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def _replace_template_vars(self, content: str) -> str:
        """Replace template variables in Python files."""
        replacements = {
            "{{ project_name }}": self.project_name,
            "{{project_name}}": self.project_name,  # Handle without spaces
            "{{ description }}": self.config.get("description", ""),
            "{{description}}": self.config.get("description", ""),  # Handle without spaces
        }

        for old, new in replacements.items():
            content = content.replace(old, new)

        return content

    def _to_snake_case(self, text: str) -> str:
        """Convert text to snake_case."""
        # Remove special characters and split by spaces/hyphens
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "_", text)
        # Convert camelCase to snake_case
        text = re.sub(r"([a-z])([A-Z])", r"\1_\2", text)
        return text.lower()

    def _to_title_case(self, text: str) -> str:
        """Convert text to PascalCase for class names."""
        # Remove special characters and split by spaces/hyphens/underscores
        text = re.sub(r"[^\w\s-]", "", text)
        words = re.split(r"[-\s_]+", text)
        return "".join(word.capitalize() for word in words if word)

    def _generate_api_key(self, length: int = 32) -> str:
        """Generate a random API key."""
        # Use URL-safe characters (letters, digits, -, _)
        alphabet = string.ascii_letters + string.digits + "-_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _generate_jwt_secret(self, length: int = 64) -> str:
        """Generate a random JWT secret."""
        # Use all printable ASCII characters except quotes for JWT secrets
        # Avoid characters that could interfere with parsing (", ', \, `, etc.).
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _generate_client_secret(self, length: int = 48) -> str:
        """Generate a random OAuth client secret."""
        # Use URL-safe characters for OAuth client secrets
        alphabet = string.ascii_letters + string.digits + "-_"
        return "".join(secrets.choice(alphabet) for _ in range(length))
