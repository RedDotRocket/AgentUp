import re
import secrets
import string
from pathlib import Path
from typing import Any

import structlog
import yaml
from jinja2 import Environment, FileSystemLoader

from agent.config.model import PluginConfig

from .templates import get_template_features

logger = structlog.get_logger(__name__)


class ProjectGenerator:
    """Generate Agent projects from templates."""

    def __init__(self, output_dir: Path, config: dict[str, Any], features: list[str] = None):
        self.output_dir = Path(output_dir)
        self.config = config
        self.template_name = config.get("template", "minimal")
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

    def _get_features(self) -> list[str]:
        """Get features based on template or custom selection."""
        # Always use config features if they exist (CLI sets this)
        if "features" in self.config:
            return self.config.get("features", [])
        else:
            # Fallback to template defaults
            template_info = get_template_features()
            return template_info.get(self.template_name, {}).get("features", [])

    def _get_llm_provider_info(self, selected_services: list[str]) -> tuple:
        """Get LLM provider info based on selected services."""
        # Provider configuration mapping
        providers = {
            "ollama": {"provider": "ollama", "service_name": "ollama", "model": "qwen3:0.6b"},
            "anthropic": {"provider": "anthropic", "service_name": "anthropic", "model": "claude-3-7-sonnet-20250219"},
            "openai": {"provider": "openai", "service_name": "openai", "model": "gpt-4o-mini"},
        }

        # Find the first LLM provider in the selected services
        for service in ["ollama", "anthropic", "openai"]:
            if service in selected_services:
                info = providers[service]
                return info["provider"], info["service_name"], info["model"]

        return None, None, None

    def _build_llm_service_config(self, service_type: str) -> dict[str, Any]:
        """Build LLM service configuration for a given service type."""
        configs = {
            "openai": {"type": "llm", "provider": "openai", "api_key": "${OPENAI_API_KEY}", "model": "gpt-4o-mini"},
            "anthropic": {
                "type": "llm",
                "provider": "anthropic",
                "api_key": "${ANTHROPIC_API_KEY}",
                "model": "claude-3-7-sonnet-20250219",
            },
            "ollama": {
                "type": "llm",
                "provider": "ollama",
                "base_url": "${OLLAMA_BASE_URL:http://localhost:11434}",
                "model": "qwen3:0.6b",
            },
        }
        return configs.get(service_type, {})

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

    def generate(self):
        """Generate the project structure."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate template files (only documentation/static files)
        self._generate_template_files()

        # Create directories for local development
        self._create_env_file()

        # Generate configuration
        self._generate_config_files()

    def _generate_template_files(self):
        """Generate files from Jinja2 templates (only docs/static files)."""
        # pyproject.toml
        pyproject_content = self._render_template("pyproject.toml")
        (self.output_dir / "pyproject.toml").write_text(pyproject_content)

        # README.md
        readme_content = self._render_template("README.md")
        (self.output_dir / "README.md").write_text(readme_content)

        # .gitignore
        gitignore_content = self._render_template(".gitignore")
        (self.output_dir / ".gitignore").write_text(gitignore_content)

        # Generate deployment files if deployment feature is enabled
        if "deployment" in self.features:
            self._generate_deployment_files()

    def _generate_deployment_files(self):
        """Generate deployment files based on feature configuration."""
        feature_config = self.config.get("feature_config", {})

        # Generate Dockerfile if docker is enabled
        if feature_config.get("docker_enabled", True):
            dockerfile_content = self._render_template("Dockerfile")
            (self.output_dir / "Dockerfile").write_text(dockerfile_content)

            # Generate docker-compose.yml
            docker_compose_content = self._render_template("docker-compose.yml")
            (self.output_dir / "docker-compose.yml").write_text(docker_compose_content)

        # Generate Helm charts if helm is enabled
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
        chart_content = self._render_template("helm/Chart.yaml")
        (helm_dir / "Chart.yaml").write_text(chart_content)

        values_content = self._render_template("helm/values.yaml")
        (helm_dir / "values.yaml").write_text(values_content)

        # Generate template files
        deployment_content = self._render_template("helm/templates/deployment.yaml")
        (helm_templates_dir / "deployment.yaml").write_text(deployment_content)

        service_content = self._render_template("helm/templates/service.yaml")
        (helm_templates_dir / "service.yaml").write_text(service_content)

        helpers_content = self._render_template("helm/templates/_helpers.tpl")
        (helm_templates_dir / "_helpers.tpl").write_text(helpers_content)

    def _create_env_file(self):
        # Create .env file for environment variables
        env_file = self.output_dir / ".env"
        if not env_file.exists():
            env_content = """# Environment Variables for AgentUp Agent

# OpenAI API Key (if using OpenAI provider)
# OPENAI_API_KEY=your_openai_api_key_here

# Anthropic API Key (if using Anthropic provider)
# ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Ollama Base URL (if using Ollama provider)
# OLLAMA_BASE_URL=http://localhost:11434

# Valkey/Redis URL (if using Valkey services)
# VALKEY_URL=valkey://localhost:6379

# OAuth2 Authentication (if using OAuth2)
# GitHub OAuth2
# GITHUB_CLIENT_ID=your_github_client_id
# GITHUB_CLIENT_SECRET=your_github_client_secret

# Google OAuth2
# GOOGLE_CLIENT_ID=your_google_client_id

# Keycloak OAuth2
# KEYCLOAK_JWKS_URL=https://your-keycloak.com/auth/realms/your-realm/protocol/openid_connect/certs
# KEYCLOAK_ISSUER=https://your-keycloak.com/auth/realms/your-realm
# KEYCLOAK_CLIENT_ID=your_keycloak_client_id

# Generic OAuth2
# OAUTH2_VALIDATION_STRATEGY=jwt
# OAUTH2_JWKS_URL=https://your-provider.com/.well-known/jwks.json
# OAUTH2_JWT_ALGORITHM=RS256
# OAUTH2_JWT_ISSUER=https://your-provider.com
# OAUTH2_JWT_AUDIENCE=your_audience
# OAUTH2_INTROSPECTION_ENDPOINT=https://your-provider.com/oauth/introspect
# OAUTH2_CLIENT_ID=your_client_id
# OAUTH2_CLIENT_SECRET=your_client_secret
"""
            env_file.write_text(env_content)

    def _generate_config_files(self):
        """Generate configuration files."""
        config_path = self.output_dir / "agentup.yml"

        # Use Jinja2 templates for config generation
        try:
            template_name = f"config/agentup_{self.template_name}.yml"
            config_content = self._render_template(template_name)
            config_path.write_text(config_content)
        except Exception as e:
            # Fallback to programmatic generation if template fails
            logger.warning(f"Template generation failed ({e}), falling back to programmatic generation")
            config_data = self._build_agent_config()
            with open(config_path, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    def _render_template(self, template_path: str) -> str:
        """Render a template file with project context using Jinja2."""
        # Convert path to template filename
        # e.g., 'llm_providers/base.py' -> 'llm_providers/base.py.j2'
        if template_path.startswith("src/agent/"):
            # For src/agent paths, strip the path prefix
            template_filename = Path(template_path).name + ".j2"
        else:
            # For other paths (like llm_providers), preserve the path structure
            template_filename = template_path + ".j2"

        # Create template context
        context = {
            "project_name": self.project_name,
            "project_name_snake": self._to_snake_case(self.project_name),
            "project_name_title": self._to_title_case(self.project_name),
            "description": self.config.get("description", ""),
            "features": self.features,
            "has_middleware": "middleware" in self.features,
            "has_state_management": "state_management" in self.features,
            "has_auth": "auth" in self.features,
            "has_mcp": "mcp" in self.features,
            "has_push_notifications": "push_notifications" in self.features,
            "has_development": "development" in self.features,
            "has_deployment": "deployment" in self.features,
            "template_name": self.template_name,
        }

        # Add AI provider context for templates (new structure)
        ai_provider_config = self.config.get("ai_provider_config")
        if ai_provider_config:
            context.update(
                {
                    "ai_provider_config": ai_provider_config,
                    "llm_provider_config": True,  # For backward compatibility with existing templates
                    "ai_enabled": True,  # Enable AI when provider is configured
                    "has_ai_provider": True,
                }
            )
        else:
            context.update(
                {
                    "ai_provider_config": None,
                    "llm_provider_config": False,
                    "ai_enabled": False,  # Disable AI when no provider configured
                    "has_ai_provider": False,
                }
            )

        # Legacy LLM provider context for old templates (if still needed)
        if "services" in self.features:
            selected_services = self.config.get("services", [])
            llm_provider, llm_service_name, llm_model = self._get_llm_provider_info(selected_services)

            if llm_provider:
                context.update(
                    {
                        "llm_provider": llm_provider,
                        "llm_service_name": llm_service_name,
                        "llm_model": llm_model,
                        "llm_provider_config": True,  # Set to True when LLM services are available
                    }
                )
            else:
                context.update(
                    {
                        "llm_provider": None,
                        "llm_service_name": None,
                        "llm_model": None,
                    }
                )

        # Add feature config
        if "feature_config" in self.config:
            context["feature_config"] = self.config["feature_config"]
        else:
            context["feature_config"] = {}

        # Add cache backend configuration
        feature_config = self.config.get("feature_config", {})
        cache_backend = feature_config.get("cache_backend", "memory")
        context["cache_backend"] = cache_backend

        # Add deployment-specific context variables
        context["has_env_file"] = True  # Most agents will have .env file

        # Add AgentUp Security Framework variables
        auth_enabled = "auth" in self.features
        auth_type = self.config.get("feature_config", {}).get("auth", "api_key")
        scope_config = self.config.get("feature_config", {}).get("scope_config", {})

        context.update(
            {
                "asf_enabled": auth_enabled,  # AgentUp Security Framework enabled
                "auth_type": auth_type,
                "scope_hierarchy_enabled": bool(scope_config.get("scope_hierarchy")),
                "has_enterprise_scopes": self.template_name == "full"
                or scope_config.get("security_level") == "enterprise",
                "context_aware_middleware": "middleware" in self.features and auth_enabled,
            }
        )

        # Add state backend configuration
        state_backend = None
        if "feature_config" in self.config and "state_backend" in self.config["feature_config"]:
            state_backend = self.config["feature_config"]["state_backend"]
        elif "state_management" in self.features:
            # Default to appropriate backend based on template
            if self.template_name == "minimal":
                state_backend = "memory"
            elif self.template_name == "full":
                state_backend = "valkey"
            else:
                state_backend = "memory"

        context["state_backend"] = state_backend

        # Render template with Jinja2
        template = self.jinja_env.get_template(template_filename)
        return template.render(context)

    def _build_agent_config(self) -> dict[str, Any]:
        """Build agentup.yml content."""
        config = {
            # Agent Information (flat structure)
            "name": self.project_name,
            "description": self.config.get("description", ""),
            "version": "0.3.0",
            "plugins": self._build_plugins_config(),
        }

        # Add AgentUp Security Framework configuration
        config["security"] = self._build_asf_config()

        # Add AI configuration for LLM-powered agents
        if "ai_provider" in self.features:
            # Use ai_provider_config if available, otherwise use defaults
            ai_provider_config = self.config.get("ai_provider_config")
            if ai_provider_config:
                llm_service_name = ai_provider_config.get("provider", "openai")
                llm_model = ai_provider_config.get("model", "gpt-4o-mini")
            else:
                llm_service_name = "openai"
                llm_model = "gpt-4o-mini"

            config["ai"] = {
                "enabled": True,
                "llm_service": llm_service_name,
                "model": llm_model,
                "system_prompt": f"""You are {self.project_name}, an AI agent with access to specific functions/plugins.

Your role:
- Understand user requests naturally and conversationally
- Use the appropriate functions when needed to help users
- Provide helpful, accurate, and friendly responses
- Maintain context across conversations

When users ask for something:
1. If you have a relevant function, call it with appropriate parameters
2. If multiple functions are needed, call them in logical order
3. Synthesize the results into a natural, helpful response
4. If no function is needed, respond conversationally

Always be helpful, accurate, and maintain a friendly tone. You are designed to assist users effectively while being natural and conversational.""",
                "max_context_turns": 10,
                "fallback_enabled": True,  # Enable fallback to basic capabilities
            }

        # Add features-specific configuration
        if "auth" in self.features:
            # Enable security if auth feature is selected
            config["security"]["enabled"] = True
            auth_type = self.config.get("feature_config", {}).get("auth", "api_key")
            config["security"]["type"] = auth_type

        if "ai_provider" in self.features:
            ai_provider_config = self.config.get("ai_provider_config")
            if ai_provider_config:
                config["ai_provider"] = ai_provider_config
            else:
                # Default AI provider configuration
                config["ai_provider"] = {
                    "provider": "openai",
                    "api_key": "${OPENAI_API_KEY}",
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "top_p": 1.0,
                }

        if "services" in self.features:
            config["services"] = self._build_services_config()

        if "mcp" in self.features:
            config["mcp"] = self._build_mcp_config()

        # Add AgentUp middleware configuration
        config["middleware"] = self._build_middleware_config()

        # Add AgentUp push notifications
        config["push_notifications"] = {"enabled": True}

        # Add AgentUp state management
        config["state_management"] = {
            "enabled": True,
            "backend": "memory",
            "ttl": 3600,  # 1 hour
            "config": {},
        }

        return config

    # TODO: Don't need this anymore, we have hello plugin
    def _build_plugins_config(self) -> list[PluginConfig]:
        """Build plugins configuration with AgentUp Security Framework classification."""
        if self.template_name == "minimal":
            return [
                {
                    "plugin_id": "echo",
                    "name": "Echo Service",
                    "description": "Simple echo service for testing",
                    "keywords": ["echo", "test", "ping"],
                    "input_mode": "text",
                    "output_mode": "text",
                    "priority": 100,
                }
            ]
        else:
            return [
                {
                    "plugin_id": "ai_assistant",
                    "name": "AI Assistant",
                    "description": "AI-powered assistant for various tasks",
                    "input_mode": "text",
                    "output_mode": "text",
                    "priority": 100,
                    "middleware_override": [
                        {
                            "name": "rate_limited",
                            "params": {
                                "requests_per_minute": 20  # Conservative rate for AI operations
                            },
                        },
                        {"name": "timed", "params": {}},
                        # No caching for AI to ensure fresh responses
                    ],
                }
            ]

    def _build_services_config(self) -> dict[str, Any]:
        """Build services configuration based on template and selected services."""
        if "services" not in self.features:
            return {}

        services = {}
        selected_services = self.config.get("services", [])

        # If no services selected, use template defaults
        if not selected_services:
            # Full template gets everything
            if self.template_name == "full":
                services["openai"] = self._build_llm_service_config("openai")
                services["valkey"] = {
                    "type": "cache",
                    "config": {"url": "${VALKEY_URL:valkey://localhost:6379}", "db": 1, "max_connections": 10},
                }
        else:
            # Build services based on user selection
            for service_type in selected_services:
                # Handle LLM services
                if service_type in ["openai", "anthropic", "ollama"]:
                    services[service_type] = self._build_llm_service_config(service_type)
                elif service_type == "valkey":
                    services["valkey"] = {
                        "type": "cache",
                        "config": {"url": "${VALKEY_URL:valkey://localhost:6379}", "db": 1, "max_connections": 10},
                    }
                elif service_type == "custom":
                    services["custom_api"] = {
                        "type": "web_api",
                        "config": {
                            "base_url": "${CUSTOM_API_URL:http://localhost:8080}",
                            "api_key": "${CUSTOM_API_KEY}",
                            "timeout": 30,
                        },
                    }

        return services

    def _build_mcp_config(self) -> dict[str, Any]:
        """Build MCP configuration based on template."""
        if "mcp" not in self.features:
            return {}

        mcp_config = {
            "enabled": True,
            "client": {"enabled": True, "servers": []},
            "server": {
                "enabled": True,
                "name": f"{self.project_name}-mcp-server",
                "expose_handlers": True,
                "expose_resources": ["agent_status", "agent_capabilities"],
                "port": 8001,
            },
        }

        # Add template-specific MCP servers
        if self.template_name == "full":
            # Multiple MCP servers for full template
            mcp_config["client"]["servers"] = [
                {
                    "name": "filesystem",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"],
                    "env": {},
                },
                {
                    "name": "github",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
                },
            ]

        return mcp_config

    def _build_middleware_config(self) -> dict[str, Any]:
        """Build context-aware middleware configuration for AgentUp Security Framework."""
        # Check if middleware feature is enabled
        middleware_enabled = "middleware" in self.features
        feature_config = self.config.get("feature_config", {})
        selected_middleware = feature_config.get("middleware", []) if middleware_enabled else []

        # Build rate limiting configuration
        rate_limit_enabled = "rate_limit" in selected_middleware
        base_rpm = 60 if self.template_name == "minimal" else 120 if self.template_name == "full" else 60
        burst_size = 144 if self.template_name == "full" else 72  # Ensure burst_size > requests_per_minute

        # Build caching configuration
        cache_enabled = "cache" in selected_middleware
        cache_backend = feature_config.get("cache_backend", "memory")
        base_ttl = 300 if self.template_name != "full" else 600
        max_size = 2000 if self.template_name == "full" else 1000

        # Build retry configuration
        retry_enabled = "retry" in selected_middleware
        max_attempts = 5 if self.template_name == "full" else 3
        max_delay = 60.0 if self.template_name == "full" else 30.0

        return {
            "enabled": middleware_enabled,
            "rate_limiting": {
                "enabled": rate_limit_enabled,
                "requests_per_minute": base_rpm,
                "burst_size": burst_size,
            },
            "caching": self._build_caching_config(cache_enabled, cache_backend, base_ttl, max_size),
            "retry": {
                "enabled": retry_enabled,
                "max_attempts": max_attempts,
                "initial_delay": 1.0,
                "max_delay": max_delay,
            },
        }

    def _build_caching_config(self, enabled: bool, backend: str, default_ttl: int, max_size: int) -> dict[str, Any]:
        """Build caching configuration with connection details for distributed backends."""
        config = {
            "enabled": enabled,
            "backend": backend,
            "default_ttl": default_ttl,
            "max_size": max_size,
        }

        # Add Valkey connection configuration if using Valkey backend
        if backend == "valkey":
            config.update(
                {
                    "valkey_url": "${VALKEY_URL:valkey://localhost:6379}",
                    "valkey_db": 1,  # Use DB 1 for cache (DB 0 for state)
                    "valkey_max_connections": 20 if self.template_name == "full" else 10,
                    "valkey_connection_timeout": 5,
                }
            )

        return config

    def _build_context_aware_cache_config(self) -> dict[str, Any]:
        """Build context-aware cache configuration."""
        base_ttl = 300 if self.template_name != "full" else 600

        config = {
            "name": "cached",
            "params": {
                "ttl": base_ttl,
                # Context-aware caching based on plugin types
                "plugin_specific_ttl": {
                    "local": base_ttl,
                    "network": base_ttl * 2,  # Longer cache for network plugins
                    "hybrid": base_ttl,
                    "ai_function": 60,  # Shorter cache for AI functions (fresh responses)
                    "core": base_ttl * 2,
                },
            },
        }

        if self.template_name == "full":
            # Enterprise-specific cache settings
            config["params"]["cache_errors"] = False
            config["params"]["max_cache_size"] = 10000

        return config

    def _build_context_aware_rate_limit_config(self) -> dict[str, Any]:
        """Build context-aware rate limiting configuration."""
        base_rpm = 60 if self.template_name == "minimal" else 120 if self.template_name == "full" else 60

        config = {
            "name": "rate_limited",
            "params": {
                "requests_per_minute": base_rpm,
            },
        }

        if self.template_name == "full":
            # Enterprise rate limiting with burst support
            config["params"]["burst_size"] = 30

        return config

    def _build_context_aware_retry_config(self) -> dict[str, Any]:
        """Build context-aware retry configuration."""
        max_retries = 3 if self.template_name != "full" else 5

        return {
            "name": "retryable",
            "params": {
                "max_retries": max_retries,
                "backoff_factor": 2.0,
                "max_delay": 60.0 if self.template_name == "full" else 30.0,
                # Plugin-specific retry configuration
                "plugin_compatibility": {
                    "local": False,  # Local plugins rarely need retries
                    "network": True,  # Network plugins benefit from retries
                    "hybrid": True,  # Hybrid plugins may need retries
                    "ai_function": False,  # AI functions need specialized retry logic
                    "core": False,  # Core functions should be reliable
                },
            },
        }

    def _get_auth_config(self, auth_type: str) -> dict[str, Any]:
        """Get authentication configuration."""
        if auth_type == "api_key":
            return {
                "header_name": "X-API-Key",
            }
        elif auth_type == "jwt":
            return {
                "secret": self._generate_jwt_secret(),
                "algorithm": "HS256",
            }
        elif auth_type == "oauth2":
            return {
                "provider": "google",
                "client_id": "${OAUTH_CLIENT_ID}",
                "client_secret": "${OAUTH_CLIENT_SECRET}",
            }
        return {}

    def _build_asf_config(self) -> dict[str, Any]:
        """Build AgentUp Security Framework configuration with scope hierarchy support."""
        # Determine auth type from feature config or default
        auth_type = self.config.get("feature_config", {}).get("auth", "api_key")

        # Check if auth feature is enabled
        auth_enabled = "auth" in self.features

        base_config = {
            "enabled": auth_enabled,
            "type": auth_type,
        }

        if not auth_enabled:
            return base_config

        # Build scope hierarchy based on auth type and template
        scope_hierarchy = self._build_scope_hierarchy(auth_type)

        if auth_type == "api_key":
            base_config["api_key"] = {
                "header_name": "X-API-Key",
                "location": "header",
                "scope_hierarchy": scope_hierarchy,
                "keys": [
                    {"key": self._generate_api_key(), "scopes": ["api:read", "files:read"]},
                    {
                        "key": self._generate_api_key(),
                        "scopes": ["admin"],  # Admin key
                    },
                ],
            }
        elif auth_type == "bearer" or auth_type == "jwt":
            base_config["bearer"] = {
                "jwt_secret": self._generate_jwt_secret(),
                "algorithm": "HS256",
                "issuer": self._to_snake_case(self.project_name),
                "audience": "a2a-clients",
                "scope_hierarchy": scope_hierarchy,
            }
        elif auth_type == "oauth2":
            base_config["oauth2"] = {
                "validation_strategy": "jwt",
                "jwks_url": "${JWKS_URL:https://your-provider.com/.well-known/jwks.json}",
                "jwt_algorithm": "RS256",
                "jwt_issuer": "${JWT_ISSUER:https://your-provider.com}",
                "jwt_audience": f"${{JWT_AUDIENCE:{self._to_snake_case(self.project_name)}}}",
                "scope_hierarchy": scope_hierarchy,
            }

        return base_config

    def _build_scope_hierarchy(self, auth_type: str) -> dict[str, list[str]]:
        """Build scope hierarchy based on CLI configuration, auth type and template."""
        # Check if CLI provided scope configuration
        feature_config = self.config.get("feature_config", {})
        scope_config = feature_config.get("scope_config", {})

        if scope_config and "scope_hierarchy" in scope_config:
            # Use CLI-configured scope hierarchy
            return scope_config["scope_hierarchy"]

        # Fall back to template-based defaults
        if self.template_name == "minimal":
            # Basic scope hierarchy for minimal template
            return {"admin": ["*"], "api:read": [], "files:read": []}
        elif self.template_name == "full":
            # Enterprise scope hierarchy for full template
            return {
                # Administrative scopes
                "admin": ["*"],
                "system:admin": ["system:write", "system:read", "files:admin"],
                "api:admin": ["api:write", "api:read", "network:admin"],
                # Functional scopes
                "files:admin": ["files:write", "files:read", "files:sensitive"],
                "files:write": ["files:read"],
                "files:sensitive": ["files:read"],
                # API access scopes
                "api:write": ["api:read"],
                "api:external": ["api:read"],
                # AI-specific scopes
                "ai:admin": ["ai:execute", "ai:train", "ai:model:admin"],
                "ai:execute": ["ai:model:read"],
                "ai:train": ["ai:execute", "ai:model:write"],
                # Enterprise scopes
                "enterprise:admin": ["enterprise:write", "enterprise:read", "api:admin"],
                "enterprise:write": ["enterprise:read", "api:write"],
                "enterprise:read": ["api:read"],
                # Base scopes
                "api:read": [],
                "files:read": [],
                "system:read": [],
            }
        else:
            # Standard scope hierarchy for default template
            return {
                "admin": ["*"],
                "api:write": ["api:read"],
                "api:read": [],
                "files:write": ["files:read"],
                "files:read": [],
                "system:read": [],
            }

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
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _generate_client_secret(self, length: int = 48) -> str:
        """Generate a random OAuth client secret."""
        # Use URL-safe characters for OAuth client secrets
        alphabet = string.ascii_letters + string.digits + "-_"
        return "".join(secrets.choice(alphabet) for _ in range(length))
