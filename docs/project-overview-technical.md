# AgentUp: A Framework for A2A-Compliant AI Agents

## What It Is

AgentUp is an open-source framework that implements the Agent-to-Agent (A2A) protocol, enabling developers to build interoperable AI agents that can communicate with each other using standardized JSON-RPC messages. Think of it as a batteries-included toolkit for creating agents that play well with others in a decentralized AI ecosystem.

## The Technical Approach

### Configuration-Driven Architecture

AgentUp takes a deliberate stance: agents are pure configuration projects. No source code in agent directories - just a YAML configuration file, dependencies, and environment variables. All functionality comes from the framework package itself.

```yaml
# agent_config.yaml - This IS your agent
agent:
  name: MyAgent
  version: 1.0.0

skills:
  - skill_id: analyze_data
    input_mode: multimodal
    output_mode: text

middleware:
  - name: cached
    params: {ttl: 300}
  - name: rate_limited
    params: {requests_per_minute: 100}
```

This approach eliminates boilerplate, ensures consistent behavior across agents, and makes framework updates immediately available to all agents without code changes.

### Universal Feature Application

Features like middleware, multi-modal processing, and authentication are applied universally based on configuration. When you define middleware in your config, it automatically wraps every handler and plugin skill. No manual decorator application, no missed endpoints.

The framework also supports per-skill overrides when needed:

```yaml
skills:
  - skill_id: expensive_operation
    middleware_override:
      - name: cached
        params: {ttl: 3600}  # 1 hour cache for this skill only
```

### Plugin System

While agents don't contain code, custom functionality is achieved through plugins. These are standard Python packages that implement a simple hook-based interface:

```python
class MyPlugin:
    def register_skill(self) -> SkillInfo:
        return SkillInfo(id="custom_skill", name="Custom Skill")
    
    def execute_skill(self, context) -> SkillResult:
        # Plugin automatically inherits all configured middleware
        # Has access to multi-modal helpers, service registry, etc.
        return SkillResult(content="Done", success=True)
```

Plugins automatically inherit all framework features - middleware, authentication, multi-modal processing - without any setup code.

### A2A Protocol Compliance

Every agent built with AgentUp is A2A-compliant out of the box. The framework handles:

- JSON-RPC 2.0 message formatting
- AgentCard generation and serving
- Task routing and execution
- Multi-modal content via DataPart types
- Error responses with proper codes

### Multi-modal Processing

Built-in support for processing images, documents, and mixed content. Available universally through helper utilities:

```python
from agentup.multimodal import MultiModalHelper

if MultiModalHelper.has_images(task):
    result = MultiModalHelper.process_first_image(task)
    # Returns metadata: dimensions, format, color analysis
```

### Service Registry Pattern

External integrations (LLMs, databases, caches) are managed through a service registry. Agents configure services in YAML; the framework handles connections, pooling, and lifecycle:

```python
services = get_services()
llm = services.get_llm('openai')
cache = services.get_cache('valkey')
```

## Key Design Decisions

1. **No code generation** - Unlike scaffolding tools, AgentUp doesn't generate code files. Agents remain pure configuration.

2. **Framework as dependency** - Agents depend on `agentup>=0.1.0`. All functionality comes from the installed package.

3. **Explicit configuration** - Features are opt-in through configuration. No magic, no surprises.

4. **Pluggy for plugins** - Uses the battle-tested pluggy library (same as pytest) for plugin management.

5. **FastAPI foundation** - Built on FastAPI for performance, automatic OpenAPI docs, and async support.

## Current Capabilities

- **Built-in handlers**: Text processing, image analysis, document processing, multi-modal chat
- **Middleware system**: Caching, rate limiting, logging, retry logic - automatically applied
- **Authentication**: API key, JWT, OAuth2 - protects all endpoints
- **MCP support**: Model Context Protocol client/server for tool integration
- **State management**: Conversation persistence with pluggable backends
- **Push notifications**: Webhook support for async communication
- **Multiple LLM providers**: OpenAI, Anthropic, Ollama with standardized interface

## The Development Experience

```bash
# Create an agent
agentup agent create my-agent

# Navigate and start
cd my-agent
uv sync
agentup agent serve

# Install a plugin
agentup plugin install agentup-plugin-web-search

# Validate configuration
agentup agent validate
```

Agents can be developed, tested, and deployed without writing handler code. Complex behaviors emerge from configuration and plugin composition.

## Architecture Benefits

1. **Consistency** - All agents behave the same way because they use the same framework code
2. **Maintainability** - Fix a bug once in the framework, all agents benefit
3. **Security** - Authentication and rate limiting can't be accidentally omitted
4. **Performance** - Optimizations in the framework improve all agents
5. **Interoperability** - A2A compliance is guaranteed by the framework

## Current State

AgentUp is in active development with a working implementation of all core features. The middleware and multi-modal systems have just been refactored to support universal application. The plugin system is operational with several example plugins.

The framework is opinionated about architecture (configuration-driven, no code generation) but flexible in deployment. Agents can run standalone, in containers, or on serverless platforms.

## Technical Stack

- Python 3.11+
- FastAPI for HTTP/WebSocket handling
- Pydantic for data validation
- HTTPX for async HTTP
- Pillow for image processing
- Valkey/Redis for caching and state (optional)
- UV for fast dependency management

## What's Different

Many agent frameworks focus on orchestration or code generation. AgentUp takes a different path: agents as pure configuration, with all complexity handled by the framework. This isn't just about reducing boilerplate - it's about ensuring every agent is secure, performant, and interoperable by default.

The A2A protocol compliance means AgentUp agents can participate in a larger ecosystem. They're not just solo actors but participants in agent-to-agent workflows.

## Open Source

AgentUp is open source under the MIT license. The goal is to make A2A-compliant agents accessible to everyone, from individual developers to enterprises. Contributions are welcome, particularly in areas like additional LLM providers, storage backends, and plugin development.

---

*AgentUp is a pragmatic framework for developers who want to build AI agents that work together. It's not about hype - it's about solid engineering that makes agent development more reliable and less repetitive.*