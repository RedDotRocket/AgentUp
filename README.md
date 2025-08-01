<p align="center">
  <img src="https://raw.githubusercontent.com/RedDotRocket/AgentUp/main/assets/logo.png" alt="Project Logo" width="200"/>
</p>

<p align="center"><strong>
  Designed with security, scalability, and extensibility at its foundation, AgentUp streamlines development through a configuration-driven architecture. It removes boilerplate and offers a growing ecosystem of community plugins to expand functionality as needed. Move fast, extend when needed.</strong>
</p>
<p align="center">
  Built by the creator of <a href="https://sigstore.dev">Sigstore</a>.
</p>

<p align="center">
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache2.0-brightgreen.svg?style=flat" alt="License: Apache 2.0"/></a>
  |
  <a href="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml"><img src="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  |
  <a href="https://discord.gg/pPcjYzGvbS"><img src="https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord" alt="Discord"/></a>
  |
  <a href="https://pypi.org/project/AgentUp/"><img src="https://img.shields.io/pypi/v/AgentUp.svg" alt="PyPI Version"/></a>
  |
  <a href="https://pepy.tech/project/agentup"><img src="https://static.pepy.tech/badge/agentup" alt="Downloads"/></a>
</p>



<div align="center">

### 🚧 Project Status: In Active Development 🚧

Join the future of AI Agent Engineering! We're actively building **AgentUp** and looking for contributors.

[![Good First Issues](https://img.shields.io/github/issues/RedDotRocket/AgentUp/good%20first%20issue?style=for-the-badge)](https://github.com/RedDotRocket/AgentUp/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

Connect with our growing community on [Discord](https://discord.gg/pPcjYzGvbS) to discuss ideas, get help, and find a mentor to help you contribute to the project.

</div>


## Why AgentUp?

**Configuration Over Code** - Define complex agent behaviors, data sources, and workflows through YAML configuration. No boilerplate, no framework internals, no lengthy development cycles. Your agents are portable, versionable, and maintainable.

**Security by Design** - Tools / MCP servers (Plugins!) are protected with AgentUp's fine-grained scope-based access control system. Fine-grained permissions ensure your plugins and MCP servers only access what they need, when they need it and only if granted so by you. Built-in authentication for OAuth2, JWT, and API keys integrates with your existing identity providers.

**Plugin Ecosystem** - Extend functionality through a growing ecosystem of community plugins, or build your own. Plugins inherit all of AgentUp's middleware, security, and operational features automatically. Version plugins independently and integrate seamlessly with your existing CI/CD pipeline.


## Advanced Architecture with Production Aspirations

AgentUp is designed with production deployment in mind, featuring architecture patterns that will scale as the framework matures. While currently in alpha, the core security and extensibility features provide a solid foundation for building serious AI agents.

### Advanced Security Model

**Scope-Based Access Control** - AgentUp's permission system controls exactly what each plugin, MCP server, and capability can access. Create hierarchical scope policies that scale from simple setups to complex requirements. Built-in OAuth2, JWT, and API key authentication provide flexible integration options.

**Comprehensive Audit Logging** - Every action is logged with sanitized audit trails. Security events are automatically classified by risk level, making it easy to monitor agent behavior. Configurable data retention policies support various compliance requirements.

**Security-First Design** - AgentUp follows security-first principles with fail-closed access control, input sanitization, and comprehensive error handling. The framework is designed to protect against privilege escalation, injection attacks, and information disclosure.

### Scalable Plugin System

**Zero-Friction Development** - Create custom capabilities without touching core code. Plugins automatically inherit AgentUp's middleware stack, security model, and operational features. Use your existing package manager (pip, uv, poetry) for dependency management and distribution.

**Community Ecosystem** - Discover and install plugins through the [AgentUp Plugin Registry](https://agentup.dev) or publish your own. Browse plugins for system tools, image processing, data analysis, and specialized capabilities. Install using your preferred Python tools (pip, uv, poetry) or publish with twine. Each plugin is independently versioned and can be updated without affecting other components. Every plugin published to the registry is automatically scanned for security vulnerabilities, insecure coding patterns and malware - ensuring a safe ecosystem.

**MCP Integration** - Leverage the expanding Model Context Protocol ecosystem. All MCP servers are automatically secured through AgentUp's scope system, and you can expose your own Agent capabilities as MCP streamable endpoints for other systems to consume!

### Flexible Infrastructure

**Multi-Provider AI Support** - Connect to OpenAI, Anthropic, or local models through OpenAI-compatible APIs (Ollama). Switch providers without code changes, and use multiple providers simultaneously for different capabilities.

**Configurable State Management** - Choose your storage backend to match your needs. File system / Memory for development, databases for structured queries, or Redis/Valkey for high-performance distributed caching. Built-in conversation tracking with configurable TTL and history management.

**Agent-to-Agent Communication** - Build multi-agent systems through A2A (Agent-to-Agent) protocol compliance. Agents can discover and communicate with each other securely, enabling complex workflows and distributed processing. AgentUp
is built on the A2A (Agent-to-Agent) specification, and the maintainer is actively involved in the A2A community.

### Developer Experience

**CLI-First Workflow** - Everything you need is available through the command line. Create new agents from templates, start development servers, manage plugins, and deploy to production using intuitive commands that integrate with your existing toolchain.

**Configuration as Code** - Agent behavior, data sources, and workflows are defined through version-controlled YAML configuration. No framework internals to learn, no boilerplate to maintain. Your agents are portable across environments and teams.

**Real-Time Operations** - Built-in support for streaming responses, asynchronous operations, and push notifications. Monitor agent performance and behavior through comprehensive logging and configurable metrics collection.

## Get Started in Minutes

### Installation

Install AgentUp using your preferred Python package manager:

```bash
pip install agentup
```

### Create Your First Agent

Generate a new agent project with interactive configuration:

```bash
agentup agent create
```

Choose from available options and configure your agent's capabilities, authentication, and AI provider settings through the interactive prompts.

### Start Development

Launch the development server and begin building:

```bash
agentup agent serve
```

Your agent is now running at `http://localhost:8000` with a full A2A-compliant 
JSON RPC API, security middleware, and all configured capabilities available.

### Next Steps

Explore the comprehensive [documentation](https://docs.agentup.dev) to learn about advanced features, tutorials, API references, and real-world examples to get you building agents quickly.

## Open Source and Community-Driven

AgentUp is Apache 2.0 licensed and built on open standards. The framework implements the A2A (Agent-to-Agent) specification for interoperability and follows the MCP (Model Context Protocol) for integration with the broader AI tooling ecosystem.

**Contributing** - Whether you're fixing bugs, adding features, or improving documentation, contributions are welcome. Join the growing community of developers building the future of AI agent infrastructure.

**Community Support** - Report issues, request features, and get help through [GitHub Issues](https://github.com/RedDotRocket/AgentUp/issues). Join real-time discussions and connect with other developers on [Discord](https://discord.gg/pPcjYzGvbS).

## Show Your Support ⭐

If AgentUp is helping you build better AI agents, or you want to encourage development, please consider giving it a star to help others discover the project and it let's me know it's worth continuing to invest time into this framework!

[![GitHub stars](https://img.shields.io/github/stars/RedDotRocket/AgentUp.svg?style=social&label=Star)](https://github.com/RedDotRocket/AgentUp)

---

**License** - Apache 2.0


[badge-discord-img]: https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord
[badge-discord-url]: https://discord.gg/pPcjYzGvbS
