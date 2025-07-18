# AgentUp

[![Tests](https://github.com/RedDotDocket/AgentUp/actions/workflows/ci.yml/badge.svg)](https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/AgentUp.svg)](https://pypi.org/project/AgentUp/)

<p align="center">
  <img src="assets/agentup_logo.png" alt="AgentUp Logo" width="400"/>
</p>

## Core Philosophy

AgentUp is a configuration-driven framework for building AI agents that comply with the A2A specification for agent-to-agent communication, capability discovery, and task orchestration. Through declarative configuration files and a modular architecture supporting custom plugins via Python entry points, AgentUp enables dynamic component loading, simplified maintenance, and consistent behavior across deployment environments while maintaining alignment with open standards and evolving protocol enhancements.

## Feature Overview

The framework includes pluggable middleware for rate limiting, caching, input validation, and authentication to either the core engine or individual plugins. 

State management provides persistent conversation tracking with configurable TTL and history. A customizable backend allows for file, database, or cache-based storage such as Redis or Valkey.

Security encompasses authentication, authorization, and secure communication patterns.

AgentUp leveragges scope hierarchy allows granular control over plugin capabilities, enabling fine-tuned access management, using scopes to define permissions for each capability, making it easy to integrate with OAuth2 and other scope-based bearer token systems.

Additional capabilities include asynchronous task management with state tracking, push notifications for real-time updates, agent discovery through A2A Agent Cards. AI provider support includes OpenAI, Anthropic, and local models through OpenAI-compatible APIs (Ollama).

MCP client and server support to allow your Agent to leverage the growing ecosystem of MCP servers for file storage, GitHub integration, and more, or expose your Agent's capabilities through a custom MCP endpoint.

## Project Status

AgentUp is in active development and not yet ready for production use. There will be lots of bugs,
Types need 'tightening up', and the API is still evolving.

## Contributing

I could do with lots of help, so if you are interested in contributing, please get in touch! I always
value contributions, whether they are code, documentation, or just feedback on the project, and wil
do my best to make all feel welcome.

## ⭐ Show Your Support

If you find this project useful or interesting, please consider giving it a star! It helps me know that people are finding value in this work and motivates me to keep improving it.

[![GitHub stars](https://img.shields.io/github/stars/RedDotRocker/AgentUp.svg?style=social&label=Star)](https://github.com/RedDotRocker/AgentUp)

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

Select from available options.

### Starting Development

Launch the development server:
```bash
agentup agent serve
```

Your agent runs at `http://localhost:8000`

From here, you really should read the [documentation](https://agentup.readthedocs.io/en/latest/) to understand how to configure your agent, add plugins, and customize its behavior, there are lots of examples and guides to help you get started!


## License

This project is licensed under the Apache 2.0 License.

## Community

Report bugs and request features through GitHub issues. Community support and development discussions are available through project channels. The documentation provides comprehensive guides and API reference materials along with sample agents and plugins for common use cases.

AgentUp provides a practical approach to AI agent development, balancing functionality with developer productivity. The standards-based design ensures compatibility with the A2A ecosystem while maintaining flexibility for custom implementations.