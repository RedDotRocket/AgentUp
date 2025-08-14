[![MSeeP.ai Security Assessment Badge](https://mseep.net/pr/reddotrocket-agentup-badge.png)](https://mseep.ai/app/reddotrocket-agentup)

<div align="center">
  <img src="https://raw.githubusercontent.com/RedDotRocket/AgentUp/main/assets/logo.png" alt="AgentUp Logo" width="400"/>
  <h3>The Operating System for AI Agents</h3>
  <br/>

  <!-- CTA Buttons -->
  <p>
    <a href="https://github.com/RedDotRocket/AgentUp/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22">
      <img src="https://img.shields.io/badge/Contribute-Good%20First%20Issues-green?style=for-the-badge&logo=github" alt="Good First Issues"/>
    </a>
    &nbsp;
    <a href="https://discord.gg/pPcjYzGvbS">
      <img src="https://img.shields.io/badge/Chat-Join%20Discord-7289da?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord"/>
    </a>
  </p>

  <!-- Badges -->
  <p>
    <a href="https://opensource.org/licenses/Apache-2.0">
      <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"/>
    </a>
    <a href="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml">
      <img src="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml/badge.svg" alt="CI Status"/>
    </a>
    <a href="https://pypi.org/project/AgentUp/">
      <img src="https://img.shields.io/pypi/v/AgentUp.svg" alt="PyPI Version"/>
    </a>
    <a href="https://pepy.tech/project/agentup">
      <img src="https://static.pepy.tech/badge/agentup" alt="Downloads"/>
    </a>
    <a href="https://discord.gg/pPcjYzGvbS">
      <img src="https://img.shields.io/discord/1384081906773131274?color=7289da&label=Discord&logo=discord&logoColor=white" alt="Discord"/>
    </a>
  </p>
  <br/>
</div>

<!-- Status Box -->
<div align="center">
   <table>
    <tr>
      <td align="center">
        <strong>🚀 Active Development</strong>
        <br/>
        <sub>🏃‍♂️ We are moving fast, things will break!</sub>
        <br/>
        <sub>Contributions are welcome! Grab a <a href="https://github.com/RedDotRocket/AgentUp/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22">good-first-issue</a> and dive in</sub>
      </td>
    </tr>
  </table>
</div>

  <br/>

## Why AgentUp?

**Operating System for AI Agents** - Built on operating system principles, AgentUp provides a robust foundation for creating AI agents through its highly extensible architecture. Its pluggable design lets you customize and add functionality without touching core code - giving you the flexibility to build exactly what you need while maintaining system stability, and ensuring your agents are portable and maintainable.

**Configuration Over Code** - Define complex agent behaviors, data sources, and workflows through rich configuration. No weeks writing boilerplate, figuring out framework internals. Your agents are portable, versionable, and maintainable, with contracts that define their capabilities and interactions.

**Security by Design** - Tools / MCP servers (Plugins!) are protected with AgentUp's fine-grained scope-based access control system. Fine-grained permissions ensure your plugins and MCP servers only access what they need, when they need it and only if granted so by you (`file:write`, `api:read`, `db:write`). Built-in authentication for OAuth2, JWT, and API keys integrates with your existing identity providers.

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

### Current Integrations

AgentUp Agents are able to present themselves as Tools to different frameworks, which brings the advantage of ensuring all Tool usage
is consistent and secure, tracked and traceable.

- [CrewAI](https://crewai.com), see [documentation](docs/integrations/crewai.md) for details.

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

## What is DCO Bot?

We use the Developer Certificate of Origin (DCO) to keep our project legally sound and protect our community. Its very common in open source projects (The Linux Kernel, Kubernetes, Docker).

The DCO prevents issues like accidentally including proprietary code and ensures all contributors have the right to submit their changes.

This protects both contributors and users of the project.

### How to sign commits
Simply add the `-s` flag when committing:

```bash
git commit -s -m "Add awesome new feature"
```

This adds a "Signed-off-by" line certifying you wrote the code or have permission to contribute it under Apache 2.0. You keep ownership of your contributions - no paperwork required!

## Show Your Support ⭐

If AgentUp is helping you build better AI agents, or you want to encourage development, please consider giving it a star to help others discover the project and it let's me know it's worth continuing to invest time into this framework!

[![GitHub stars](https://img.shields.io/github/stars/RedDotRocket/AgentUp.svg?style=social&label=Star)](https://github.com/RedDotRocket/AgentUp)

---

**License** - Apache 2.0


[badge-discord-img]: https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord
[badge-discord-url]: https://discord.gg/pPcjYzGvbS
