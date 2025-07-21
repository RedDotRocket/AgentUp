# Core Concepts

Let's revisit the core concepts of AgentUp to understand how it works and what makes it unique.


## What is AgentUp?

AgentUp is a framework for quickly building AI agents that communicate using the Agent-to-Agent (A2A) protocol. It uses a **plugin-based architecture** and **config-driven** architecture where agents are lightweight configuration projects,
extended with plugins to provide capabilities.

## Key Architecture Principles

### 1. Plugin-Based Architecture

```
┌─────────────────┐    ┌──────────────────┐
│   Your Agent    │    │  AgentUp Package │
│ (Configuration) │───▶│   (Framework)    │
│                 │    │                  │
│ • agentup.yml   │    │ • Core Runtime   │
│ • No Code       │    │ • Plugin System  │
│ • Just YAML     │    │ • A2A Protocol   │
└─────────────────┘    └──────────────────┘
```

**What this means:**

  - **Agents contain only configuration** - No source code to maintain
  - **Framework provides all functionality** - Runtime, protocols, plugins
  - **Easy updates** - Update framework core, keep your config and plugins pinned to versions

### 2. Configuration-Driven Design

Everything in AgentUp is controlled through `agent_config.yaml`:

```yaml
name: "My Agent"
description: "What this agent does"
version: "1.0.0"

# Enable plugins for functionality
plugins:
  - plugin_id: system_tools
  - plugin_id: web_search

# Auto-applied middleware
middleware:
  - name: rate_limiting
    config:
      requests_per_minute: 60

# Conversation state management
state_management:
  enabled: true
  backend: memory
```

### 3. Plugin System

Plugins provide capabilities to your agent:

```
Agent Config ──┐
               │
               ▼
        Plugin Loader
               │
               ▼
    ┌──────────────────┐
    │   Capabilities   │
    │                  │
    │ • read_file      │
    │ • write_file     │
    │ • web_search     │
    │ • send_email     │
    └──────────────────┘
```

**Key concepts:**

  - **Plugins** = Python packages with capabilities
  - **Capabilities** = Individual functions (read_file, web_search)
  - **Scopes** = How capabilities are grouped and applied policy

## AgentUp Taxonomy

### Framework Components


#### Plugin Capabilities
Provided by plugins, configured in your agent:

  - File operations (`read_file`, `write_file`)
  - System commands (`execute_command`)
  - Web requests (`http_request`)
  - Custom capabilities (your plugins)

### Communication Protocols

#### A2A (Agent-to-Agent)
- **Purpose**: Agent discovery and inter-agent communication
- **Format**: JSON-RPC 2.0 over HTTP
- **Features**: Capability discovery, secure communication, standardized errors

#### MCP (Model Context Protocol)
- **Purpose**: Pluggable tools for AI models
- **Integration**: Works with AgentUp plugins
- **Benefit**: Standardized tool interfaces

## Auto-Application Pattern

AgentUp automatically applies cross-cutting concerns:

```yaml
# Global settings applied everywhere
middleware:
  - name: rate_limiting
  - name: authentication
  - name: logging

state_management:
  enabled: true

# Per-plugin overrides possible
plugins:
  - plugin_id: expensive_api
    middleware_override:
      - name: rate_limiting
        config:
          requests_per_minute: 10  # Slower for this plugin
```

**Benefits:**

- **No boilerplate code** - Framework handles common concerns
- **Consistent behavior** - Same patterns across all capabilities
- **Override flexibility** - Customize per plugin if needed
- **Core Decoupling** - Core functionality remains clean and focused, no backport hell to worry about
