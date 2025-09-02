<div align="center">
English | <a href="README.cn.md">简体中文</a>
</div>

<div align="center">
  <img src="https://raw.githubusercontent.com/RedDotRocket/AgentUp/main/assets/logo.png" alt="AgentUp Logo" width="400"/>

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
      </td>
    </tr>
  </table>
</div>

  <br/>

## Why AgentUp?

Just as Docker made applications immutable, reproducible, and ops-friendly, **AgentUp** does the same for AI agents. Define your agent with configuration, and it runs consistently anywhere. Share agents with teammates who can clone / fork and run them instantly. Deploy knowing your agent will behave identically across development, staging, and production environments.

<img src="assets/init.gif" width="100%" height="100%"/>

When you need to customize, write your code as clean abstraction and load into AgentUp's runtime and inherit all of AgentUp's middleware and security. You can the manage your code as a depedency , along with any other communiity based plugins you used. No more fighting against a framework that breaks your app each time they changed something. Check out the [AgentUp Plugin registry](https://agentup.dev/packages) for a few of the current plugins on offer. 

<img src="/assets/plugins.gif" width="100%" height="100%"/>

AgentUp is built by engineers who've created open-source solutions powering mission-critical systems at **Google, GitHub, Nvidia, Red Hat, Shopify and more**. We understand what it takes to build stable, secure, scalable software - and we're applying those same principles to make AI agents truly production-ready, secure and reliable.

## AgentUp: Developer-First Agent Framework

AgentUp delivers enterprise-grade agent infrastructure built for professional developers who demand both power and simplicity.

**Developer-First Operations**: Built by developers who understand real-world constraints. Each agent lives in its own repository with a single AgentUp configuration file. Clone, run `agentup run`, and all dependencies resolve during initialization - no more environment setup headaches.

**Secure by Design**: Fine-grained, scope-based access control with OAuth2, JWT, and API key authentication built-in,
preventing unauthorized Tools / MCP access, ensuring data protection. Security isn't an afterthought - it's foundational architecture in AgentUp.

**Configuration-Driven Architecture**: Define complex agent behaviors, data sources, and workflows through declarative configuration. Skip weeks of boilerplate and framework wrestling. Your agents become portable, versionable assets with clear contracts defining their capabilities and interactions.

**Extensible Ecosystem for customizations**: Need RAG, image processing, custom API logic? No problem. Leverage community plugins or build custom extensions that automatically inherit AgentUp's middleware, security, and operational features. Independent plugin versioning integrates seamlessly with existing CI/CD pipelines, ensuring core platform updates don't break your implementations. With AgentUp you get the immediate feedback of a running agent, along with the extensibility of a framework.

**Agent-to-Agent Discovery**: Automatic A2A Agent Card generation exposes your agent's capabilities to other agents in the ecosystem, enabling seamless inter-agent communication and orchestration.

**Asynchronous Task Architecture**: Message-driven task management supports long-running operations with callback-based notifications. Perfect for research agents, data processing workflows, and event-driven automation. State persistence across Redis and other backends ensures reliability at scale.

**Deterministic routing**: Most frameworks place everything in the LLM's execution path, but this is often not optimal. Frequently, the better solution is through deterministic code, aka good old software engineering. For this reason, AgentUp allows for deterministic keyword based routing, where requests can natural language driven, but instead be sent to existing non-LLM services that utilize caching and other efficiency mechanisms.

**MCP Support**: AgentUp includes built-in support for Model-Context Protocol (MCP), allowing agents to seamlessly interact with various communication channels and APIs. Full support is available for STDIO, SSE and Streamable HTTP. Simply add a configuration in as
much the same way as you would for Claude, Cursor or VSCode.

## Multi Agent Type

Within AgentUp there are what we term multiple Agent types. 

**Reactive Agents**: These agents respond to user inputs and events as single shot interactions, making them ideal for chatbots and interactive applications.

**Iterative Agents**: Designed for tasks that require multiple planning steps or iterations, making them ideal for research, these agents break down a goal into smaller, manageable tasks and execute them sequentially, maintaining context and state throughout the process. Goals must reach a confidence threshold before concluding.

## Stay Updated

AgentUp development is moving at a fast pace 🏃‍♂️, for a great way to follow the project and to be instantly notified of new releases, **Star the repo**.

<img src="/assets/star.gif" width="40%" height="40%"/>

## Get Started in Minutes

### Installation

Install AgentUp using your preferred Python package manager:

```bash
pip install agentup
```

### Create Your First Agent

Generate a new agent project with interactive configuration:

```bash
agentup init
```

Choose from available options and configure your agent's capabilities, authentication, and AI provider settings through the interactive prompts.

### Start your Agent

Launch the development server and begin building:

```bash
agentup run
```

Your agent is now running at `http://localhost:8000` with a full A2A-compliant  JSON RPC API, security middleware, and all configured capabilities available.

### Next Steps

#### Need a UI?

Grab hold of the AgentUp chat client to converse with your Agents through a simple interface using [AgentUpChat](https://github.com/RedDotRocket/AgentUpChat)

<img src="/assets/demo.gif" width="100%" height="100%"/>

#### Check out the Docs!

Explore the comprehensive [documentation](https://docs.agentup.dev) to learn about advanced features, tutorials, API references, and real-world examples to get you building agents quickly.

### Current Integrations

AgentUp Agents are able to present themselves as Tools to different frameworks, which brings the advantage of ensuring all Tool usage
is consistent and secure, tracked and traceable.

- [CrewAI](https://crewai.com), see [documentation](docs/integrations/crewai.md) for details.

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

---

**License** - Apache 2.0


[badge-discord-img]: https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord
[badge-discord-url]: https://discord.gg/pPcjYzGvbS
