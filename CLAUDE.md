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
- `integration`: Tests with external services
- `e2e`: End-to-end system tests
- `performance`: Load and performance tests
- `security`: Security-focused tests
- `mcp`: Model Context Protocol tests
- `a2a`: Agent-to-Agent protocol compliance tests

Run specific test categories: `uv run pytest -m "unit and not slow"`

## Configuration

Agent configuration uses YAML files with these key sections:
- `agent`: Basic agent metadata and description
- `plugins`: Plugin capabilities with scope-based permissions
- `security`: Authentication and authorization settings
- `middleware`: Rate limiting, caching, retry configuration
- `state_management`: Conversation state backends and TTL
- `mcp`: Model Context Protocol server/client configuration

Environment variables can override configuration using the `ENV_VARS` mapping defined in `src/agent/config/constants.py`.