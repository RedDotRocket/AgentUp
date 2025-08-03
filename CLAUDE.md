# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentUp is a Python framework for creating AI agents with production-ready features including security, scalability, and extensibility. It uses a configuration-driven architecture where agent behaviors, data sources, and workflows are defined through YAML configuration rather than code.

**Key Features:**
- Configuration-over-code approach with YAML-driven agent definitions
- Security-first design with scope-based access control and comprehensive audit logging
- Plugin ecosystem with community registry and automatic security scanning
- Multi-provider AI support (OpenAI, Anthropic, Ollama)
- MCP (Model Context Protocol) and A2A (Agent-to-Agent) protocol compliance
- Real-time operations with streaming, async processing, and push notifications

## Technology Stack

- **Python**: >=3.11 required
- **Pydantic**: v2 for data validation and settings management
- **Web Framework**: FastAPI with Uvicorn ASGI server
- **Package Manager**: UV (preferred) for dependency management
- **Plugin System**: Pluggy-based architecture with middleware inheritance
- **Authentication**: OAuth2, JWT, API key support via Authlib
- **Logging**: Structlog with correlation IDs for distributed tracing
- **Testing**: Pytest with async support and comprehensive markers
- **Code Quality**: Ruff (linting/formatting), MyPy (type checking), Bandit (security)

## Essential Development Commands

### Environment Setup
```bash
uv sync --all-extras --dev    # Install all dependencies including dev tools
uv pip install -e .           # Install package in editable mode
```

### Testing
```bash
# Unit tests only (fast)
uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/ -v -m "not integration and not e2e and not performance"

# Integration tests
chmod +x tests/integration/int.sh && ./tests/integration/int.sh

# All tests with coverage
uv run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# Watch mode for development
uv run pytest-watch --runner "uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/ -m 'not integration and not e2e and not performance'"
```

### Code Quality (Required Before Commits)
```bash
uv run ruff check --fix src/ tests/    # Fix linting issues
uv run ruff format src/ tests/         # Format code
uv run mypy src/                       # Type checking
uv run bandit -r src/ -ll              # Security scanning
```

### Agent Development
```bash
uv run agentup agent create            # Create new agent project
uv run agentup agent serve             # Start development server
uv run agentup validate                # Validate agent configuration
```

### Makefile Shortcuts
```bash
make install-dev      # Complete development setup
make test-unit        # Fast unit tests
make lint-fix         # Fix linting and formatting
make validate-all     # Run all quality checks
make clean           # Clean temporary files
```

## Code Architecture

### Core Structure
```
src/agent/
├── api/           # FastAPI server, routes, middleware
├── capabilities/  # Agent capability system and executors
├── cli/           # Command-line interface commands
├── config/        # Configuration models and loading
├── core/          # Function dispatching and execution
├── llm_providers/ # AI provider integrations
├── mcp_support/   # Model Context Protocol integration
├── plugins/       # Plugin system (pluggy-based)
├── security/      # Authentication, authorization, audit
├── services/      # Service layer abstractions
├── state/         # Conversation and state management
├── templates/     # Project generation templates
└── utils/         # Utility functions and helpers
```

### Key Architectural Patterns

**Plugin System**: Uses pluggy for hook-based architecture where plugins register capabilities with automatic middleware inheritance and scope-based permissions.

**Security Layer**: Unified authentication supporting multiple types (API key, JWT, OAuth2) with hierarchical scope-based authorization and comprehensive audit logging.

**Configuration-Driven**: Agent behavior defined through YAML files with Pydantic validation and environment variable overrides.

**Capability Registration**: AI functions are automatically discovered and registered with optional middleware (rate limiting, caching, retry logic) and state management.

**Pydantic v2**: Utilizes Pydantic v2 features like `@field_validator` and `@model_validator` for data validation, with a focus on modern typing conventions and use of Pydantic Models for configuration.

## Code Style and Conventions

- **Formatting**: Ruff with 120-character line length, double quotes, 4-space indentation
- **Linting**: Enabled rules include pycodestyle, pyflakes, isort, flake8-bugbear, pyupgrade
- **Type Hints**: Encouraged but not strictly enforced; MyPy configured for gradual typing
- **Modern Typing**: Use built-in `dict` and `list` instead of `typing.Dict` and `typing.List` (Python 3.9+)
- **Pydantic v2**: Use `@field_validator` and `@model_validator` decorators (not deprecated `@validator`)
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE_CASE for constants
- **Logging**: Use `structlog.get_logger(__name__)` pattern with structured logging
- **Imports**: Automatic organization via Ruff isort integration

### Typing Guidelines
- ✅ **Use**: `dict[str, Any]`, `list[str]`, `str | None`
- ❌ **Avoid**: `Dict[str, Any]`, `List[str]`, `Optional[str]`
- ❌ **Avoid**: `hasinstance` checks for types; use `isinstance` with Pydantic models
- **Import from typing**: Only `Union`, `Literal`, `Any`, `TypeVar`, `Generic`, `Protocol`
- **See**: `docs/MODERN_TYPING_GUIDE.md` for complete typing conventions

## Development Guidelines

- **Pydantic Handling**:
  - ALWAYS USE PYDANTIC MODELS over .get style dict

## Task Completion Workflow

After making code changes, always run:

1. **Linting and Formatting**: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
2. **Type Checking**: `uv run mypy src/`
3. **Security Scanning**: `uv run bandit -r src/ -ll`
4. **Unit Tests**: `uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/ -v -m "not integration and not e2e and not performance"`

**Quick Commands**: Use `make lint-fix && make test-unit` for rapid development cycle, or `make validate-all` for comprehensive validation before commits.

## Testing Strategy

Tests are organized with pytest markers:
- `unit`: Fast tests without external dependencies

Run `make test-unit`

Run specific test categories: `uv run pytest -m "unit and not slow"`

## Calling the main endpoint

AgentUp has a single A2A JSON-RPC endoint that should be used to test or validate fixes against an Agent:

```
```
```
curl -s -X POST http://localhost:8000/ \
```
      -H "Content-Type: application/json" \
      -H "X-API-Key: admin-key-123" \
      -d '{
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
          "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "delete a folder called test"}],
            "message_id": "msg-001",
            "kind": "message"
          }
        },
        "id": "req-001"
      }'
```
```
```

```

## Configuration Structure

AgentUp uses a comprehensive YAML-based configuration system with Pydantic v2 models for validation. The main configuration file is `agentup.yml` in the project root.

### Core Configuration Sections

#### Agent Metadata
```yaml
name: My Agent                    # Project name (alias for project_name)
description: AI Agent Description # Agent description
version: 1.0.0                   # Semantic version (required format: x.y.z)
environment: development         # development, staging, or production
```

#### Plugin System
```yaml
plugins:
  - plugin_id: hello             # Unique plugin identifier
    name: Hello Plugin           # Display name
    description: Plugin description
    enabled: true                # Enable/disable plugin
    capabilities:                # Plugin capabilities list
      - capability_id: hello
        name: Hello Capability
        description: Capability description
        required_scopes: ["api:read"]  # Required permission scopes
        enabled: true
    default_scopes: []           # Default scopes for all capabilities
    middleware: []               # Plugin-specific middleware
    config: {}                   # Plugin configuration dictionary
```

#### AI Provider Configuration
```yaml
ai_provider:
  provider: openai              # openai, anthropic, ollama
  api_key: ${OPENAI_API_KEY}   # Environment variable substitution
  model: gpt-4o-mini           # Model name
  temperature: 0.7             # Model parameters
```

#### Security & Authentication
```yaml
security:
  enabled: true                # Enable security features
  auth:
    api_key:
      header_name: "X-API-Key"
      keys:
        - key: "admin-key-123"
          scopes: ["system:read"]
  scope_hierarchy:             # Permission inheritance
    admin: ["*"]               # Universal access
    files:admin: ["files:write", "files:read"]
    files:write: ["files:read"]
```

#### API Server
```yaml
api:
  enabled: true                # Enable API server
  host: "127.0.0.1"           # Server host
  port: 8000                   # Server port
  workers: 1                   # Number of workers
  reload: false                # Auto-reload in development
  debug: false                 # Debug mode
  max_request_size: 16777216   # Max request size in bytes
  request_timeout: 30          # Request timeout in seconds
  cors_enabled: true           # Enable CORS
  cors_origins: ["*"]          # Allowed origins
  cors_methods: ["GET", "POST", "PUT", "DELETE"]
```

#### Middleware Configuration
```yaml
middleware:
  enabled: true
  rate_limiting:
    enabled: true
    requests_per_minute: 10
    burst_size: 12
  caching:
    enabled: true
    backend: memory            # memory, redis
    default_ttl: 300          # Cache TTL in seconds
    max_size: 1000            # Max cache entries
  retry:
    enabled: true
    max_attempts: 3
    initial_delay: 1.0
    max_delay: 60.0
```

#### MCP (Model Context Protocol)
```yaml
mcp:
  enabled: false               # Enable MCP support
  client_enabled: true         # Enable MCP client
  client_timeout: 30           # Client timeout in seconds
  server_enabled: false        # Enable MCP server
  server_host: "localhost"     # Server host
  server_port: 8080           # Server port
  servers:                     # MCP server configurations
    - name: "filesystem-server"
      type: "stdio"
      command: "uvx"
      args: ["mcp-server-filesystem", "/tmp"]
      tool_scopes:             # Tool-specific scopes
        read_file: ["files:read"]
        write_file: ["files:write"]
```

#### State Management
```yaml
state_management:
  enabled: true
  backend: memory              # memory, redis, database
  ttl: 3600                   # State TTL in seconds
  config: {}                  # Backend-specific configuration
```

#### Logging Configuration
```yaml
logging:
  enabled: true
  level: "INFO"               # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "text"              # text, json
  console:
    enabled: true
    colors: true              # Enable colored output
  file:
    enabled: false
    path: "logs/agent.log"
  correlation_id: false       # Enable correlation ID tracking
  request_logging: false      # Log HTTP requests
  uvicorn:
    access_log: false
    disable_default_handlers: true
```

#### Push Notifications
```yaml
push_notifications:
  enabled: true
  backend: memory             # memory, webhook
  validate_urls: false        # Validate webhook URLs
  config: {}                  # Backend-specific settings
```

### Environment Variable Overrides

Configuration values can be overridden using environment variables with the `AGENTUP_` prefix:

- `AGENTUP_API_HOST` → `api.host`
- `AGENTUP_API_PORT` → `api.port`
- `AGENTUP_LOG_LEVEL` → `logging.level`
- `AGENTUP_DEBUG` → `api.debug`
- `AGENTUP_SECRET_KEY` → Application secret key

**Supported Environment Variables** (from `src/agent/config/constants.py`):
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `OLLAMA_BASE_URL` - Ollama server URL
- `VALKEY_URL` - Redis/Valkey connection URL
- `DATABASE_URL` - Database connection URL
- `AGENT_CONFIG_PATH` - Custom config file path
- `SERVER_HOST` - API server host
- `SERVER_PORT` - API server port

### Configuration Validation

The configuration system uses Pydantic v2 models with comprehensive validation:

- **Semantic Versioning**: Version must follow `x.y.z` format
- **Port Validation**: Ports must be between 1-65535
- **Plugin ID Format**: Alphanumeric with hyphens, underscores, dots
- **Scope Hierarchy**: Automatic permission inheritance validation
- **Environment Consistency**: MCP settings validated for consistency

### Configuration Loading

Configuration is loaded in this order (later values override earlier ones):
1. Default values from Pydantic models
2. `agentup.yml` file in project root
3. Environment variables with `AGENTUP_` prefix
4. Command-line arguments (where applicable)

Use `uv run agentup validate` to validate your configuration file.
