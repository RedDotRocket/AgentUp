import re
import secrets
import string
from pathlib import Path
from typing import Any

import structlog
import yaml
from jinja2 import Environment, FileSystemLoader

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
            "anthropic": {"provider": "anthropic", "service_name": "anthropic", "model": "claude-3-haiku-20240307"},
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
                "model": "claude-3-haiku-20240307",
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
"""
            env_file.write_text(env_content)

    def _generate_config_files(self):
        """Generate configuration files."""
        config_path = self.output_dir / "agent_config.yaml"

        # Use Jinja2 templates for config generation
        try:
            template_name = f"config/agent_config_{self.template_name}.yaml"
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
            "has_state": "state" in self.features,
            "has_auth": "auth" in self.features,
            "has_mcp": "mcp" in self.features,
            "template_name": self.template_name,
        }

        # Add AI provider context for templates (new structure)
        ai_provider_config = self.config.get("ai_provider_config")
        if ai_provider_config:
            context.update(
                {
                    "ai_provider_config": ai_provider_config,
                    "llm_provider_config": True,  # For backward compatibility with existing templates
                }
            )
        else:
            context.update({"ai_provider_config": None, "llm_provider_config": False})

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

        # Add state backend configuration
        state_backend = None
        if "feature_config" in self.config and "state_backend" in self.config["feature_config"]:
            state_backend = self.config["feature_config"]["state_backend"]
        elif "state" in self.features:
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
        """Build agent_config.yaml content."""
        config = {
            # Agent Information
            "agent": {
                "name": self.project_name,
                "description": self.config.get("description", ""),
                "version": "0.1.0",
            },
            # Legacy configuration (kept for backward compatibility)
            # 'project_name': self.project_name,
            # 'description': self.config.get('description', ''),
            # 'version': '0.1.0',
            # Core configuration
            "skills": self._build_skills_config(),
            "routing": self._build_routing_config(),
            # Registry skills section - for skills installed from AgentUp Skills Registry
            "registry_skills": [],
        }

        # Add AgentUp security configuration
        config["security"] = {
            "enabled": False,  # Set to True to enable authentication
            "type": "api_key",  # Options: 'api_key', 'bearer', 'oauth2'
            "api_key": {
                "header_name": "X-API-Key",
                "location": "header",  # Options: 'header', 'query', 'cookie'
                "keys": [
                    # Generated API keys - replace with your own
                    self._generate_api_key(),
                    self._generate_api_key(),
                ],
            },
            "bearer": {
                "jwt_secret": self._generate_jwt_secret(),
                "algorithm": "HS256",
                "issuer": "your-agent",
                "audience": "a2a-clients",
            },
            "oauth2": {
                "token_url": "${OAUTH_TOKEN_URL:/oauth/token}",
                "client_id": "${OAUTH_CLIENT_ID:your-client-id}",
                "client_secret": self._generate_client_secret(),
                "scopes": {
                    "read": "Read access to agent capabilities",
                    "write": "Write access to send messages",
                    "admin": "Administrative access",
                },
            },
        }

        # Add routing configuration (for backward compatibility)
        config["routing"] = self._build_routing_config()

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
                "system_prompt": f"""You are {self.project_name}, an AI agent with access to specific functions/skills.

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
                "fallback_to_routing": True,  # Fall back to keyword routing if LLM fails
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
        config["state"] = {
            "backend": "memory",
            "ttl": 3600,  # 1 hour
        }

        return config

    def _build_skills_config(self) -> list[dict[str, Any]]:
        """Build skills configuration based on template."""
        if self.template_name == "minimal":
            return [
                {
                    "skill_id": "echo",
                    "name": "Echo",
                    "description": "Echo back the input text",
                    "input_mode": "text",
                    "output_mode": "text",
                    "routing_mode": "direct",
                    "keywords": ["echo", "repeat", "say"],
                    "patterns": [".*"],
                }
            ]
        elif self.template_name == "full":
            # Full template gets multiple skills
            return [
                {
                    "skill_id": "ai_assistant",
                    "name": "AI Assistant",
                    "description": "General purpose AI assistant",
                    "input_mode": "text",
                    "output_mode": "text",
                },
                {
                    "skill_id": "data_analyzer",
                    "name": "Data Analyzer",
                    "description": "Analyze and visualize data",
                    "input_mode": "text",
                    "output_mode": "text",
                },
            ]
        else:
            # Standard template
            return [
                {
                    "skill_id": "ai_assistant",
                    "name": "AI Assistant",
                    "description": "General purpose AI assistant",
                    "input_mode": "text",
                    "output_mode": "text",
                    "routing_mode": "ai",
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

    def _build_middleware_config(self) -> list[dict[str, Any]]:
        """Build middleware configuration for A2A protocol."""
        middleware = []

        # Always include basic middleware for A2A
        middleware.extend(
            [
                {"name": "timed", "params": {}},
            ]
        )

        # Add feature-specific middleware
        if "middleware" in self.features:
            feature_config = self.config.get("feature_config", {})
            selected_middleware = feature_config.get("middleware", [])

            if "cache" in selected_middleware:
                middleware.append(
                    {
                        "name": "cached",
                        "params": {
                            "ttl": 300  # 5 minutes
                        },
                    }
                )

            if "rate_limit" in selected_middleware:
                middleware.append({"name": "rate_limited", "params": {"requests_per_minute": 60}})

            if "retry" in selected_middleware:
                middleware.append({"name": "retryable", "params": {"max_retries": 3, "backoff_factor": 2}})

        return middleware

    def _build_routing_config(self) -> dict[str, Any]:
        """Build routing configuration based on template."""
        # Determine routing mode and fallback skill based on template
        if self.template_name == "minimal":
            default_mode = "direct"
            fallback_skill = "echo"
        else:
            default_mode = "ai"
            fallback_skill = "ai_assistant"

        return {"default_mode": default_mode, "fallback_skill": fallback_skill, "fallback_enabled": True}

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
