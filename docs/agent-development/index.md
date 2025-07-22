# Agent Development Guide

Learn how to create, configure, and deploy production-ready AgentUp agents.

## Overview

AgentUp agents are lightweight configuration projects that depend on the AgentUp framework for functionality. This guide covers everything from basic setup to advanced customization.

## Guides in This Section

### Getting Started
1. **[Configuration](configuration.md)** - Master agent configuration files
2. **[Customization](customization.md)** - Customize CLI commands and templates
3. **[Deployment](deployment.md)** - Deploy agents to production

## Key Concepts

### Package-Based Architecture
Agents are configuration projects that:
- Contain only configuration files (no source code)
- Depend on the AgentUp framework package
- Use plugins for extended functionality

### Configuration-Driven Design
Everything is controlled through `agent_config.yaml`:
- Plugin selection and configuration
- Middleware and state management
- Authentication and security settings
- Per-skill configuration overrides

## Quick Reference

### Essential Commands
```bash
agentup agent create my-agent     # Create new agent
agentup agent serve              # Start development server
agentup agent validate           # Validate configuration
```

### Basic Configuration Structure
```yaml
name: "My Agent"
description: "Agent description"
version: "1.0.0"

plugins:
  - plugin_id: system_tools

middleware:
  - name: rate_limiting
    config:
      requests_per_minute: 60

state_management:
  enabled: true
  backend: valkey
```

## Best Practices

1. **Start Simple**: Begin with minimal configuration and add complexity gradually
2. **Use Templates**: Leverage existing templates for common patterns
3. **Validate Early**: Use `agentup agent validate` frequently during development
4. **Test Thoroughly**: Test all capabilities and error conditions
5. **Document Configuration**: Comment your YAML files for clarity

## Common Patterns

### Development Workflow
1. Create agent with template
2. Configure plugins and middleware
3. Test with development server
4. Validate configuration
5. Deploy to target environment

### Plugin Integration
- Enable plugins in configuration
- Override middleware per plugin if needed
- Test plugin capabilities individually
- Monitor plugin performance

## Need Help?

- **[Configuration Reference](../../reference/configuration-schema.md)** - Complete configuration options
- **[Plugin Guides](../plugin-development/)** - Learn about available plugins
- **[Troubleshooting](../../troubleshooting/)** - Common issues and solutions
- **[Examples](../../examples/)** - Working agent examples