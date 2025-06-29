import logging
import re
import secrets
import string
from pathlib import Path
from typing import Any, Dict, List

import yaml
from jinja2 import Environment, FileSystemLoader

from .templates import get_template_features

logger = logging.getLogger(__name__)


class ProjectGenerator:
    """Generate Agent projects from templates."""

    def __init__(self, output_dir: Path, config: Dict[str, Any], features: List[str] = None):
        self.output_dir = Path(output_dir)
        self.config = config
        self.template_name = config.get('template', 'minimal')
        self.project_name = config['name']
        self.features = features if features is not None else self._get_features()

        # Setup Jinja2 environment
        templates_dir = Path(__file__).parent / 'templates'
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom functions to Jinja2 environment
        self.jinja_env.globals['generate_api_key'] = self._generate_api_key
        self.jinja_env.globals['generate_jwt_secret'] = self._generate_jwt_secret
        self.jinja_env.globals['generate_client_secret'] = self._generate_client_secret

    def _get_features(self) -> List[str]:
        """Get features based on template or custom selection."""
        if self.template_name == 'custom':
            return self.config.get('features', [])
        else:
            template_info = get_template_features()
            return template_info.get(self.template_name, {}).get('features', [])

    def _replace_template_vars(self, content: str) -> str:
        """Replace template variables in Python files."""
        replacements = {
            '{{ project_name }}': self.project_name,
            '{{project_name}}': self.project_name,  # Handle without spaces
            '{{ description }}': self.config.get('description', ''),
            '{{description}}': self.config.get('description', ''),  # Handle without spaces
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

        # Copy framework files
        self._copy_framework_files()

        # Generate configuration
        self._generate_config_files()

    def _generate_template_files(self):
        """Generate files from Jinja2 templates (only docs/static files)."""
        # pyproject.toml
        pyproject_content = self._render_template('pyproject.toml')
        (self.output_dir / 'pyproject.toml').write_text(pyproject_content)

        # README.md
        readme_content = self._render_template('README.md')
        (self.output_dir / 'README.md').write_text(readme_content)

        # .gitignore
        gitignore_content = self._render_template('.gitignore')
        (self.output_dir / '.gitignore').write_text(gitignore_content)

    def _copy_framework_files(self):
        """Copy the AgentUp framework files to the project."""
        # Use static src/agent structure for consistency and CLI compatibility
        src_dir = self.output_dir / 'src' / 'agent'
        src_dir.mkdir(parents=True, exist_ok=True)

        # Copy all Python files from src/agentup to the new project
        agentup_src = Path(__file__).parent

        # Core files to copy
        core_files = [
            '__init__.py',
            'api.py',
            'config.py',
            'context.py',
            'handlers.py',
            'main.py',
            'middleware.py',
            'models.py',
            'multimodal.py',
            'services.py',
            'utils.py',
            'messages.py',               # Message processing and conversation context
            'function_dispatcher.py',    # Main dispatch logic
            'llm_manager.py',            # LLM provider management
            'function_executor.py',      # Function execution logic
            'conversation_manager.py',   # Conversation state
            'streaming_handler.py',      # Streaming operations
            'agent_executor.py',         # New AgentUp executor
            'dependencies.py',           # AgentUp dependencies
        ]

        # Copy core files with import updates
        for file_name in core_files:
            src_file = agentup_src / file_name
            if src_file.exists():
                content = src_file.read_text()
                # Replace template variables
                content = self._replace_template_vars(content)
                # Update imports to use src.agent instead of relative imports
                # content = self._update_imports(content)
                (src_dir / file_name).write_text(content)

        # Copy demo_handlers.py only for demo template
        if self.template_name == 'demo':
            demo_file = agentup_src / 'demo_handlers.py'
            if demo_file.exists():
                content = demo_file.read_text()
                # Replace template variables
                content = self._replace_template_vars(content)
                (src_dir / 'demo_handlers.py').write_text(content)

        # Copy subdirectories
        subdirs = ['handlers', 'llm_providers', 'mcp_support', 'security']
        for subdir in subdirs:
            src_subdir = agentup_src / subdir
            if src_subdir.exists() and src_subdir.is_dir():
                dest_subdir = src_dir / subdir
                dest_subdir.mkdir(exist_ok=True)

                # Copy Python files
                for py_file in src_subdir.glob('*.py'):
                    content = py_file.read_text()
                    # Replace template variables
                    content = self._replace_template_vars(content)
                    # Update imports to use src.agent instead of relative imports
                    # content = self._update_imports(content, is_subdir=True, subdir_name=subdir)
                    (dest_subdir / py_file.name).write_text(content)

                # Copy non-Python files (like weak.txt, configs, etc.)
                for other_file in src_subdir.glob('*'):
                    if other_file.is_file() and not other_file.name.endswith('.py'):
                        # Copy static files directly without template processing
                        (dest_subdir / other_file.name).write_bytes(other_file.read_bytes())

                # Copy nested subdirectories (like security/authenticators)
                for nested_subdir in src_subdir.iterdir():
                    if nested_subdir.is_dir():
                        dest_nested = dest_subdir / nested_subdir.name
                        dest_nested.mkdir(exist_ok=True)

                        # Copy Python files in nested subdirectories
                        for py_file in nested_subdir.glob('*.py'):
                            content = py_file.read_text()
                            # Replace template variables
                            content = self._replace_template_vars(content)
                            (dest_nested / py_file.name).write_text(content)

                        # Copy non-Python files in nested subdirectories
                        for other_file in nested_subdir.glob('*'):
                            if other_file.is_file() and not other_file.name.endswith('.py'):
                                # Copy static files directly without template processing
                                (dest_nested / other_file.name).write_bytes(other_file.read_bytes())


    def _generate_config_files(self):
        """Generate configuration files."""
        config_path = self.output_dir / 'agent_config.yaml'

        # Use Jinja2 templates for config generation
        try:
            template_name = f'config/agent_config_{self.template_name}.yaml'
            config_content = self._render_template(template_name)
            config_path.write_text(config_content)
        except Exception as e:
            # Fallback to programmatic generation if template fails
            logger.warning(f"Template generation failed ({e}), falling back to programmatic generation")
            config_data = self._build_agent_config()
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)


    def _render_template(self, template_path: str) -> str:
        """Render a template file with project context using Jinja2."""
        # Convert path to template filename
        # e.g., 'llm_providers/base.py' -> 'llm_providers/base.py.j2'
        if template_path.startswith('src/agent/'):
            # For src/agent paths, strip the path prefix
            template_filename = Path(template_path).name + '.j2'
        else:
            # For other paths (like llm_providers), preserve the path structure
            template_filename = template_path + '.j2'

        # Create template context
        context = {
            'project_name': self.project_name,
            'project_name_snake': self._to_snake_case(self.project_name),
            'project_name_title': self._to_title_case(self.project_name),
            'description': self.config.get('description', ''),
            'features': self.features,
            'has_middleware': 'middleware' in self.features,
            'has_services': 'services' in self.features,
            'has_state': 'state' in self.features,
            'has_multimodal': 'multimodal' in self.features,
            'has_auth': 'auth' in self.features,
            'has_monitoring': 'monitoring' in self.features,
            'has_testing': 'testing' in self.features,
            'has_deployment': 'deployment' in self.features,
            'has_mcp': 'mcp' in self.features,
            'template_name': self.template_name,
        }

        # Add feature config
        if 'feature_config' in self.config:
            context['feature_config'] = self.config['feature_config']
        else:
            context['feature_config'] = {}

        # Render template with Jinja2
        template = self.jinja_env.get_template(template_filename)
        return template.render(context)



    def _build_agent_config(self) -> Dict[str, Any]:
        """Build agent_config.yaml content."""
        config = {
            # Agent Information
            'agent': {
                'name': self.project_name,
                'description': self.config.get('description', ''),
                'version': '0.1.0',
            },

            # Legacy configuration (kept for backward compatibility)
            # 'project_name': self.project_name,
            # 'description': self.config.get('description', ''),
            # 'version': '0.1.0',

            # Core configuration
            'skills': self._build_skills_config(),
            'routing': self._build_routing_config(),

            # Registry skills section - for skills installed from AgentUp Skills Registry
            'registry_skills': [],
        }

        # Add AgentUp security configuration
        config['security'] = {
            'enabled': False,  # Set to True to enable authentication
            'type': 'api_key',  # Options: 'api_key', 'bearer', 'oauth2'
            'api_key': {
                'header_name': 'X-API-Key',
                'location': 'header',  # Options: 'header', 'query', 'cookie'
                'keys': [
                    # Generated API keys - replace with your own
                    self._generate_api_key(),
                    self._generate_api_key()
                ]
            },
            'bearer': {
                'jwt_secret': self._generate_jwt_secret(),
                'algorithm': 'HS256',
                'issuer': 'your-agent',
                'audience': 'a2a-clients'
            },
            'oauth2': {
                'token_url': '${OAUTH_TOKEN_URL:/oauth/token}',
                'client_id': '${OAUTH_CLIENT_ID:your-client-id}',
                'client_secret': self._generate_client_secret(),
                'scopes': {
                    'read': 'Read access to agent capabilities',
                    'write': 'Write access to send messages',
                    'admin': 'Administrative access'
                }
            }
        }

        # Add routing configuration (for backward compatibility)
        config['routing'] = self._build_routing_config()

        # Add AI configuration for LLM-powered agents
        if 'services' in self.features:
            config['ai'] = {
                'enabled': True,
                'llm_service': 'openai',
                'model': 'gpt-4o-mini',
                'system_prompt': f'''You are {self.project_name}, an AI agent with access to specific functions/skills.

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

Always be helpful, accurate, and maintain a friendly tone. You are designed to assist users effectively while being natural and conversational.''',
                'max_context_turns': 10,
                'fallback_to_routing': True  # Fall back to keyword routing if LLM fails
            }

        # Add features-specific configuration
        if 'auth' in self.features:
            # Enable security if auth feature is selected
            config['security']['enabled'] = True
            auth_type = self.config.get('feature_config', {}).get('auth', 'api_key')
            config['security']['type'] = auth_type

        if 'services' in self.features:
            config['services'] = self._build_services_config()

        if 'mcp' in self.features:
            config['mcp'] = self._build_mcp_config()

        # Add AgentUp middleware configuration
        config['middleware'] = self._build_middleware_config()

        # Add AgentUp push notifications
        config['push_notifications'] = {
            'enabled': True
        }

        # Add AgentUp state management
        config['state'] = {
            'backend': 'memory',
            'ttl': 3600  # 1 hour
        }

        return config


    def _build_skills_config(self) -> List[Dict[str, Any]]:
        """Build skills configuration based on template."""
        if self.template_name == 'minimal':
            return [{
                'skill_id': 'echo',
                'name': 'Echo',
                'description': 'Echo back the input text',
                'input_mode': 'text',
                'output_mode': 'text',
                'routing_mode': 'direct',
                'keywords': ['echo', 'repeat', 'say'],
                'patterns': ['.*']
            }]
        elif self.template_name == 'demo':
            return [
                {
                    'skill_id': 'file_assistant',
                    'name': 'File Assistant',
                    'description': 'Read and write files using MCP',
                    'input_mode': 'text',
                    'output_mode': 'text',
                },
                {
                    'skill_id': 'weather_bot',
                    'name': 'Weather Bot',
                    'description': 'Get weather information using function calling',
                    'input_mode': 'text',
                    'output_mode': 'text',
                },
                {
                    'skill_id': 'code_analyzer',
                    'name': 'Code Analyzer',
                    'description': 'Analyze code repositories',
                    'input_mode': 'text',
                    'output_mode': 'text',
                },
                {
                    'skill_id': 'joke_teller',
                    'name': 'Joke Teller',
                    'description': 'Tell jokes on demand',
                    'input_mode': 'text',
                    'output_mode': 'text',
                }
            ]
        elif self.template_name == 'full':
            # Full template gets multiple skills
            return [
                {
                    'skill_id': 'ai_assistant',
                    'name': 'AI Assistant',
                    'description': 'General purpose AI assistant',
                    'input_mode': 'text',
                    'output_mode': 'text',
                },
                {
                    'skill_id': 'document_processor',
                    'name': 'Document Processor',
                    'description': 'Process and analyze documents',
                    'input_mode': 'multimodal',
                    'output_mode': 'text',
                },
                {
                    'skill_id': 'data_analyzer',
                    'name': 'Data Analyzer',
                    'description': 'Analyze and visualize data',
                    'input_mode': 'text',
                    'output_mode': 'multimodal',
                }
            ]
        else:
            # Standard template
            return [{
                'skill_id': 'ai_assistant',
                'name': 'AI Assistant',
                'description': 'General purpose AI assistant',
                'input_mode': 'text',
                'output_mode': 'text',
                'routing_mode': 'ai'
            }]

    def _build_services_config(self) -> Dict[str, Any]:
        """Build services configuration based on template."""
        if 'services' not in self.features:
            return {}

        services = {
            'llm': [],
            'database': [],
            'cache': []
        }

        # Standard and demo templates get basic OpenAI
        if self.template_name in ['standard', 'demo']:
            services['llm'] = [{
                'name': 'openai',
                'type': 'openai',
                'config': {
                    'api_key': '${OPENAI_API_KEY}',
                    'model': 'gpt-4o-mini'
                }
            }]

        # Full template gets everything
        elif self.template_name == 'full':
            services['llm'] = [{
                'name': 'openai',
                'type': 'openai',
                'config': {
                    'api_key': '${OPENAI_API_KEY}',
                    'model': 'gpt-4o-mini'
                }
            }]
            services['database'] = [{
                'name': 'postgres',
                'type': 'postgres',
                'config': {
                    'url': '${DATABASE_URL:postgresql://user:pass@localhost/db}'
                }
            }]
            services['cache'] = [{
                'name': 'redis',
                'type': 'redis',
                'config': {
                    'url': '${REDIS_URL:redis://localhost:6379}'
                }
            }]

        return services

    def _build_mcp_config(self) -> Dict[str, Any]:
        """Build MCP configuration based on template."""
        if 'mcp' not in self.features:
            return {}

        mcp_config = {
            'enabled': True,
            'client': {
                'enabled': True,
                'servers': []
            },
            'server': {
                'enabled': True,
                'name': f'{self.project_name}-mcp-server',
                'expose_handlers': True,
                'expose_resources': ['agent_status', 'agent_capabilities'],
                'port': 8001
            }
        }

        # Add template-specific MCP servers
        if self.template_name == 'standard':
            # Basic filesystem access for standard template
            mcp_config['client']['servers'] = [
                {
                    'name': 'filesystem',
                    'command': 'npx',
                    'args': ['-y', '@modelcontextprotocol/server-filesystem', '/tmp'],
                    'env': {}
                }
            ]
        elif self.template_name == 'full':
            # Multiple MCP servers for full template
            mcp_config['client']['servers'] = [
                {
                    'name': 'filesystem',
                    'command': 'npx',
                    'args': ['-y', '@modelcontextprotocol/server-filesystem', '/'],
                    'env': {}
                },
                {
                    'name': 'github',
                    'command': 'npx',
                    'args': ['-y', '@modelcontextprotocol/server-github'],
                    'env': {
                        'GITHUB_PERSONAL_ACCESS_TOKEN': '${GITHUB_TOKEN}'
                    }
                }
            ]
        elif self.template_name == 'demo':
            # Demo-specific MCP configuration
            mcp_config['client']['servers'] = [
                {
                    'name': 'demo-filesystem',
                    'command': 'npx',
                    'args': ['-y', '@modelcontextprotocol/server-filesystem', './demo-files'],
                    'env': {}
                }
            ]

        return mcp_config

    def _build_middleware_config(self) -> List[Dict[str, Any]]:
        """Build middleware configuration for A2A protocol."""
        middleware = []

        # Always include basic middleware for A2A
        middleware.extend([
            {
                'name': 'logged',
                'params': {
                    'log_level': 20  # INFO level
                }
            },
            {
                'name': 'timed',
                'params': {}
            }
        ])

        # Add feature-specific middleware
        if 'middleware' in self.features:
            feature_config = self.config.get('feature_config', {})
            selected_middleware = feature_config.get('middleware', [])

            if 'cache' in selected_middleware:
                middleware.append({
                    'name': 'cached',
                    'params': {
                        'ttl': 300  # 5 minutes
                    }
                })

            if 'rate_limit' in selected_middleware:
                middleware.append({
                    'name': 'rate_limited',
                    'params': {
                        'requests_per_minute': 60
                    }
                })

            if 'retry' in selected_middleware:
                middleware.append({
                    'name': 'retryable',
                    'params': {
                        'max_retries': 3,
                        'backoff_factor': 2
                    }
                })

        return middleware

    def _build_routing_config(self) -> Dict[str, Any]:
        """Build routing configuration based on template."""
        # Determine routing mode and fallback skill based on template
        if self.template_name == 'minimal':
            default_mode = 'direct'
            fallback_skill = 'echo'
        else:
            default_mode = 'ai'
            fallback_skill = 'ai_assistant'

        return {
            'default_mode': default_mode,
            'fallback_skill': fallback_skill,
            'fallback_enabled': True
        }

    def _get_auth_config(self, auth_type: str) -> Dict[str, Any]:
        """Get authentication configuration."""
        if auth_type == 'api_key':
            return {
                'header_name': 'X-API-Key',
            }
        elif auth_type == 'jwt':
            return {
                'secret': self._generate_jwt_secret(),
                'algorithm': 'HS256',
            }
        elif auth_type == 'oauth2':
            return {
                'provider': 'google',
                'client_id': '${OAUTH_CLIENT_ID}',
                'client_secret': '${OAUTH_CLIENT_SECRET}',
            }
        return {}


    def _to_snake_case(self, text: str) -> str:
        """Convert text to snake_case."""
        # Remove special characters and split by spaces/hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        # Convert camelCase to snake_case
        text = re.sub(r'([a-z])([A-Z])', r'\1_\2', text)
        return text.lower()

    def _to_title_case(self, text: str) -> str:
        """Convert text to PascalCase for class names."""
        # Remove special characters and split by spaces/hyphens/underscores
        text = re.sub(r'[^\w\s-]', '', text)
        words = re.split(r'[-\s_]+', text)
        return ''.join(word.capitalize() for word in words if word)

    def _generate_api_key(self, length: int = 32) -> str:
        """Generate a random API key."""
        # Use URL-safe characters (letters, digits, -, _)
        alphabet = string.ascii_letters + string.digits + '-_'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _generate_jwt_secret(self, length: int = 64) -> str:
        """Generate a random JWT secret."""
        # Use all printable ASCII characters except quotes for JWT secrets
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*()_+-=[]{}|;:,.<>?'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _generate_client_secret(self, length: int = 48) -> str:
        """Generate a random OAuth client secret."""
        # Use URL-safe characters for OAuth client secrets
        alphabet = string.ascii_letters + string.digits + '-_'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

