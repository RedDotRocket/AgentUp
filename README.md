# AgentUp

⭐ If you like AgentUp, give it a star on GitHub.

**The fastest way to bootstrap full capability A2A-compliant AI Agents**

AgentUp is a developer-focused framework that provides a complete foundation for building
interoperable AI agents. The framework combines a powerful CLI for rapid development with
a flexible, configuration-driven architecture that scales from simple automation to complex multi-modal AI systems.

## Core Philosophy

AgentUp follows a config-driven/ plugin approach where all features are controlled through configuration.
This design enables dynamic component loading, simplified maintenance, and consistent behavior across
different deployment environments. The framework emphasizes standards compliance, developer experience,
and architectural flexibility / ownership, allowing teams to focus on quickly bootstrapping
intelligent agents with everything they need to get started, out of the box.

## Open Source and Standards-Based

AgentUp is built on open standards - most notably the A2A protocol - which governs agent-to-agent
communication, capability discovery, and task orchestration. Its modular architecture makes it
highly extensible: developers can rapidly author custom plugins (Tools) that plug directly into the
core runtime. The AgentUp maintainers actively contribute to both the A2A specification and its reference
libraries, the framework stays tightly aligned with emerging best practices and evolving protocol enhancements.

The folks behind AgentUp have a proven pedigree in security and open source: they’re the driving force
behind projects like [sigstore](https://sigstore.dev/) and [Bandit](https://bandit.readthedocs.io/),
and have consistently demonstrated a commitment to writing code that is secure, scalable, while also being
transparent and open.

## Rich Feature Set

AgentUp provides a rich set of features to support a wide range of AI agent use cases:

- **Multi-Agent Communication**: Compliant with the A2A protocol for agent-to-agent interactions
- **AI Provider Integration**: Support for multiple LLM providers (OpenAI, Anthropic, local models)
- **Dynamic Skill Management**: Register and manage skills (Tools) dynamically
- **AI Function Calling**: Automatically register skills as callable functions for LLMs
- **Direct and Keyword Routing**: Route requests based on keywords or patterns (for deterministic behavior)
- **Multi-Modal Communication**: Handle text, files, structured data, and streaming content
- **Asynchronous Task Management**: Support for long-running tasks with state tracking
- **Plugin System**: Manage skills (Tools) through Pythons native entry points (aka install plugins with pip, uv, etc.)
- **Push Notifications**: Real-time updates for task progress and completion
- **Agent Discovery**: Publish and consume A2A Agent Cards describing capabilities and endpoints
- **Security**: Authentication, authorization, and secure communication patterns
- **MCP Integration**: Model Context Protocol (MCP) support (stdio and sse)
- **Middleware**: Built-in support for rate limiting, caching, and validation, input validation
- **State Management**: Persistent conversation state with TTL and history tracking
- **Interoperability**: Standard JSON-RPC 2.0 communication with other A2A-compliant agents

## Quick Start

### Installation

```bash
pip install agentup
```

### Create Your First Agent

```bash
# Interactive setup with guided configuration
agentup agent create my-agent

# Quick start with standard template
agentup agent create my-agent --template standard

# Navigate to your agent
cd my-agent
```

### Configure and Launch

```bash
# Start the development server
agentup agent serve
```

Your agent is now running at `http://localhost:8000`

## Architecture Overview

### Configuration-Driven Design

All features are controlled through `agent_config.yaml`:

```yaml
agent:
  name: "My AI Agent"
  description: "Intelligent assistant with custom capabilities"
  version: "1.0.0"

# Skills define agent capabilities
skills:
  - skill_id: ai_assistant
    name: AI Assistant
    description: AI-powered assistant for various tasks
    tags: [ai, assistant, helper]
    input_mode: text
    output_mode: text
    priority: 100

# AI Provider configuration
ai_provider:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 1000
  top_p: 1.0

# External services (databases, caches, etc.)
services:
  valkey:
    type: cache
    config:
      url: ${VALKEY_URL:valkey://localhost:6379}
      db: 1
      max_connections: 10

# Security configuration
security:
  enabled: true
  type: jwt
  config:
    secret: ${JWT_SECRET}
    algorithm: HS256

# State management for conversations
state:
  backend: file
  storage_dir: "./conversation_states"
  ttl: 3600
```

### Component Architecture

- **Dynamic Loading**: Components instantiated only when configured
- **Middleware System**: Rate limiting, caching, validation, retry logic
- **Service Registry**: Pluggable integrations for LLMs, databases, caches
- **Plugin System**: Extensible skills through Python entry points
- **Multi-Modal Processing**: Images, documents, structured data handling

## Core Features

### AI Integration
- **Multiple LLM Providers**: OpenAI, Anthropic, local models
- **Function Calling**: Automatic registration of skills as LLM functions
- **Streaming Responses**: Real-time response generation
- **Context Management**: Conversation state and memory

### Plugin System
```bash
# Create custom skills
agentup plugin create weather-skill --template advanced

# Install community plugins
pip install weather-plugin time-plugin

# Register in agent configuration
# Skills automatically discovered via Python entry points
```

### Development Tools
```bash
# Validate configuration
agentup agent validate

# Generate deployment files
agentup agent deploy --type docker

# Development server with auto-reload
agentup agent serve --reload
```

### Enterprise Features
- **Authentication**: API keys, JWT tokens, OAuth2 flows
- **Security**: Input validation, rate limiting, secure headers
- **Monitoring**: Structured logging, metrics, health checks
- **State Management**: File, database, or cache-based persistence
- **Push Notifications**: Webhook delivery with retry logic

## Agent Templates

### Minimal Template
Basic A2A-compliant agent without AI dependencies:
- Echo skill for request/response testing
- No external service requirements
- Suitable for automation, webhooks, simple processing

### Standard Template (Recommended)
AI-powered agent with essential features:
- OpenAI integration for intelligent responses
- MCP filesystem access for file operations
- Authentication and basic middleware
- Ideal for most AI assistant use cases

### Full Template
Enterprise deployment with comprehensive features:
- Multiple LLM providers and MCP servers
- Database (PostgreSQL) and cache (Valkey) support
- Advanced middleware and monitoring
- State management and push notifications
- Suitable for high-scale deployments


## Plugin Development

### Creating Skills

```bash
# Generate plugin scaffold
agentup plugin create my-skill --template basic

# Implement plugin interface
class Plugin:
    @hookimpl
    def register_skill(self) -> SkillInfo:
        return SkillInfo(
            id="my_skill",
            name="My Custom Skill",
            capabilities=[SkillCapability.TEXT, SkillCapability.AI_FUNCTION]
        )

    @hookimpl
    def execute_skill(self, context: SkillContext) -> SkillResult:
        # Skill implementation
        pass
```

### AI Function Integration

```python
@hookimpl
def get_ai_functions(self) -> list[AIFunction]:
    return [
        AIFunction(
            name="process_data",
            description="Process input data with custom logic",
            parameters={"type": "object", ...},
            handler=self.process_data_handler
        )
    ]
```

## Development Workflow

### Agent Management
```bash
agentup agent create [NAME]          # Create new agent project
agentup agent serve                  # Start development server
agentup agent validate               # Validate configuration
agentup agent deploy                 # Generate deployment files
```

### Plugin Management
```bash
agentup plugin create [NAME]         # Create new plugin
agentup plugin list                  # List installed plugins
agentup plugin install [PLUGIN]      # Install from registry
```

### Configuration Management
- **Environment Variables**: `${VAR_NAME:default}` substitution
- **Template System**: Multiple pre-configured starting points
- **Validation**: Comprehensive config checking with helpful error messages
- **Hot Reload**: Development server updates on configuration changes

## Technical Specifications

### Protocol Implementation
- **JSON-RPC 2.0**: Standard request/response communication
- **Server-Sent Events**: Streaming and real-time updates
- **HTTP/HTTPS**: Standard web protocols with security headers
- **Agent Cards**: Capability discovery and metadata exchange

### Supported Integrations
- **LLM Providers**: OpenAI, Anthropic, local models via OpenAI-compatible APIs
- **Databases**: PostgreSQL, SQLite with SQLAlchemy
- **Caches**: Redis, Valkey for session and response caching
- **MCP Servers**: Filesystem, GitHub, custom implementations
- **Authentication**: Multiple methods with configurable security policies

### Deployment Options
- **Docker**: Generated Dockerfile with multi-stage builds
- **Kubernetes**: Deployment manifests with configmaps and secrets
- **Helm Charts**: Parameterized deployments for different environments
- **Systemd**: Service files for Linux server deployment

## Configuration Reference

### Agent Configuration
```yaml
agent:
  name: string              # Agent display name
  description: string       # Agent description for discovery
  version: string          # Semantic version

skills:
  - skill_id: string       # Unique skill identifier
    name: string          # Human-readable skill name
    description: string   # Skill description
    tags: [string]        # Tags for categorization
    input_mode: string    # Input type (text, multimodal, etc.)
    output_mode: string   # Output type (text, json, etc.)
    priority: number      # Priority for routing (lower = higher priority)
    keywords: [string]    # Direct routing keywords (optional)
    patterns: [string]    # Regex patterns for matching (optional)
    enabled: bool         # Enable/disable skill (optional)

security:
  enabled: bool           # Enable authentication
  type: string           # auth type (api_key, jwt, oauth2)
  config:                # Type-specific configuration
    secret: string       # JWT secret or API keys
    algorithm: string    # JWT algorithm
```

### AI Provider Configuration
```yaml
ai_provider:
  provider: openai|anthropic|ollama    # AI provider
  api_key: ${API_KEY}                 # Provider API key
  model: string                       # Model name
  temperature: number                 # Response creativity (0.0-2.0)
  max_tokens: number                  # Maximum response length
  top_p: number                       # Nucleus sampling parameter
```

### Service Configuration
```yaml
services:
  service_name:
    type: database|cache|http         # Service type (LLM moved to ai_provider)
    config:
      url: ${SERVICE_URL}             # Service connection URL
      # Service-specific configuration
```

## Documentation

- **[Developer Guide](docs/developer-guide.md)**: Comprehensive development environment setup
- **[Plugin Development](docs/plugins/development.md)**: Advanced plugin creation and testing
- **[Authentication Guide](docs/authentication/)**: Security configuration and best practices
- **[Deployment Guide](docs/deployment/)**: Production deployment strategies
- **[Configuration Reference](docs/reference/)**: Complete configuration options

## Contributing

AgentUp welcomes contributions from the community. The project follows standard open-source practices:

1. **Fork and Clone**: Create your development environment
2. **Feature Branches**: Develop features in isolated branches
3. **Testing**: Add tests for new functionality
4. **Documentation**: Update docs for user-facing changes
5. **Pull Requests**: Submit changes for review

### Development Setup
```bash
git clone https://github.com/RedDotRocket/AgentUp.git
cd AgentUp
uv sync                    # Install dependencies
uv run pytest             # Run test suite
```

## License

This project is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file for details.

## Community

- **Issues**: Report bugs and request features on GitHub
- **Discussions**: Community support and development discussions
- **Documentation**: Comprehensive guides and API reference
- **Examples**: Sample agents and plugins for common use cases

AgentUp represents a thoughtful approach to AI agent development, balancing powerful capabilities with developer productivity. The framework's standards-based design ensures compatibility with the broader A2A ecosystem while providing the flexibility needed for custom implementations.