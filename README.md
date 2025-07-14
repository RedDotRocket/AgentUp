# AgentUp

AgentUp is a configuration-driven framework for building A2A-compliant AI agents. The framework provides a CLI for rapid development and a flexible architecture that scales from simple automation to complex multi-modal AI systems.

## Core Philosophy

AgentUp follows a configuration-driven approach where features are controlled through declarative configuration files. This design enables dynamic component loading, simplified maintenance, and consistent behavior across deployment environments. The framework emphasizes standards compliance and developer experience, allowing teams to focus on building functional agents rather than infrastructure.

## Standards-Based Architecture

AgentUp implements the A2A protocol for agent-to-agent communication, capability discovery, and task orchestration. The modular architecture supports custom plugins that integrate directly with the core runtime through Python entry points. AgentUp maintains alignment with open standards and evolving protocol enhancements.

## Feature Overview

AgentUp provides comprehensive functionality for AI agent development. Multi-agent communication follows A2A protocol standards for interoperability. AI provider integration supports multiple LLM providers including OpenAI, Anthropic, and local models. The plugin system manages capabilities through Python's native entry points, allowing installation via standard package managers.

The framework includes middleware for rate limiting, caching, input validation, and authentication. State management provides persistent conversation tracking with configurable TTL and history. Security features encompass authentication, authorization, and secure communication patterns. MCP integration offers Model Context Protocol support for both stdio and server-sent events.

Additional capabilities include asynchronous task management with state tracking, push notifications for real-time updates, agent discovery through A2A Agent Cards, and multi-modal communication supporting text, files, structured data, and streaming content.

## Quick Start

### Installation

Install AgentUp using pip:
```bash
pip install agentup
```

### Creating Agents

Generate a new agent project with interactive configuration:
```bash
agentup agent create my-agent
cd my-agent
```

Select from available templates during creation: minimal for basic A2A compliance, standard for AI-powered assistants, or full for enterprise deployments with comprehensive features.

### Starting Development

Launch the development server:
```bash
agentup agent serve
```

Your agent runs at `http://localhost:8000` with automatic configuration reloading during development.

## Architecture Overview

### Configuration-Driven Design

AgentUp uses declarative configuration through `agent_config.yaml` to define agent behavior, capabilities, and integrations. This approach enables dynamic component loading where features are instantiated only when configured, reducing resource usage and complexity.

The configuration system supports environment variable substitution for sensitive values and provides validation with detailed error messages. Template-based project generation offers starting points for different deployment scenarios.

### Component Architecture

The framework implements a layered architecture with dynamic component loading, middleware systems for cross-cutting concerns, and a service registry for external integrations. The plugin system extends functionality through Python entry points, allowing standard package management for capability installation.

Middleware automatically applies to configured capabilities, providing rate limiting, caching, input validation, and retry logic. State management handles conversation persistence with configurable backends including file storage, databases, and cache systems.

Scoped execution ensures proper isolation between plugin capabilities, with configurable security contexts and resource limits. The architecture supports multi-modal processing for text, images, documents, and structured data through specialized plugins.

## Core Features

### AI Integration

AgentUp supports multiple LLM providers including OpenAI, Anthropic, and local models through OpenAI-compatible APIs. Function calling automatically registers plugin capabilities as callable functions for LLMs. Streaming responses enable real-time generation, while context management maintains conversation state and memory across interactions.

### Plugin System

Plugins extend agent functionality through Python entry points, enabling standard package management workflows. Create custom plugins using the CLI scaffolding tools, or install community plugins through pip. Plugin capabilities are automatically discovered and registered based on configuration.

Example plugin creation:
```bash
agentup plugin create weather-skill --template advanced
```

Install plugins as standard Python packages:
```bash
pip install weather-plugin time-plugin
```

### Development Tools

The CLI provides comprehensive development support including configuration validation, deployment file generation, and development servers with automatic reloading. Agent validation ensures configuration correctness before deployment.

### Enterprise Features

Authentication supports API keys, JWT tokens, and OAuth2 flows with configurable security policies. Security features include input validation, rate limiting, and secure headers. Monitoring provides structured logging, metrics collection, and health checks. State management offers file, database, or cache-based persistence with configurable TTL. Push notifications deliver webhook updates with retry logic.

## Agent Templates

### Minimal Template
Provides basic A2A-compliant agent functionality without AI dependencies. Includes echo capabilities for request/response testing and requires no external services. Suitable for automation, webhooks, and simple processing tasks.

### Standard Template
Offers AI-powered agent capabilities with essential features including OpenAI integration for intelligent responses, MCP filesystem access for file operations, authentication, and basic middleware. Ideal for most AI assistant use cases.

### Full Template
Delivers enterprise deployment capabilities with comprehensive features including multiple LLM providers, MCP servers, database and cache support, advanced middleware, monitoring, state management, and push notifications. Designed for high-scale deployments.

## Plugin Development

### Creating Plugins

Generate plugin scaffolding using the CLI with template selection for different complexity levels. Plugins implement the standard interface for capability registration and execution within the agent runtime.

Generate a new plugin:
```bash
agentup plugin create my-skill --template basic
```

### Plugin Integration

Plugins integrate with the agent runtime through Python entry points, providing automatic discovery and registration. The framework handles middleware application, security scoping, and state management for plugin capabilities.

## Development Workflow

### Agent Management

Create new agent projects with interactive configuration selection. Start development servers with automatic reloading for rapid iteration. Validate configurations before deployment to ensure correctness. Generate deployment files for various target environments.

### Plugin Management

Create new plugins using scaffolding templates. List installed plugins and their capabilities. Install plugins from registries or local development packages. The system automatically discovers and registers plugin capabilities through Python entry points.

### Configuration Management

Environment variable substitution supports default values using `${VAR_NAME:default}` syntax. Template systems provide multiple pre-configured starting points for different deployment scenarios. Configuration validation offers comprehensive checking with detailed error messages. Development servers support hot reload for configuration changes without restart.

## Technical Specifications

### Protocol Implementation

AgentUp implements JSON-RPC 2.0 for standard request/response communication and server-sent events for streaming and real-time updates. HTTP/HTTPS protocols include security headers and proper error handling. Agent Cards enable capability discovery and metadata exchange between agents.

### Supported Integrations

LLM provider support includes OpenAI, Anthropic, and local models through OpenAI-compatible APIs. Database integration covers PostgreSQL and SQLite with SQLAlchemy. Cache systems support Redis and Valkey for session and response caching. MCP servers include filesystem, GitHub, and custom implementations. Authentication methods provide multiple approaches with configurable security policies.

### Deployment Options

Docker support generates optimized Dockerfiles with multi-stage builds. Kubernetes deployment includes manifests with configmaps and secrets. Helm charts provide parameterized deployments for different environments. Systemd service files enable Linux server deployment.

## Configuration Reference

AgentUp uses YAML configuration files to define agent behavior, capabilities, and integrations. The configuration system supports environment variable substitution, validation, and template-based generation.

Agent configuration defines basic metadata including name, description, and version. Plugin configuration specifies which capabilities to enable and their settings. AI provider configuration handles LLM integration parameters. Service configuration manages external integrations including databases and caches.

Security configuration controls authentication methods and policies. Middleware configuration applies cross-cutting concerns like rate limiting and caching. State management configuration handles conversation persistence and TTL settings.

## Documentation

The framework includes comprehensive documentation covering development environment setup, plugin creation and testing, security configuration and best practices, production deployment strategies, and complete configuration options.

## Contributing

AgentUp welcomes community contributions following standard open-source practices. Contributors should fork the repository, develop features in isolated branches, add tests for new functionality, update documentation for user-facing changes, and submit pull requests for review.

Development setup requires cloning the repository, installing dependencies with uv sync, and running the test suite with uv run pytest.

## License

This project is licensed under the Apache 2.0 License.

## Community

Report bugs and request features through GitHub issues. Community support and development discussions are available through project channels. The documentation provides comprehensive guides and API reference materials along with sample agents and plugins for common use cases.

AgentUp provides a practical approach to AI agent development, balancing functionality with developer productivity. The standards-based design ensures compatibility with the A2A ecosystem while maintaining flexibility for custom implementations.