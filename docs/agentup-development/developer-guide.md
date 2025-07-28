# AgentUp Developer Guide

This guide provides trouble-free development environments and workflows for different types of AgentUp development, eliminating common footguns and path-related issues.

## Overview: Developer Personas

AgentUp supports three distinct developer types, each with different needs:

1. **Framework Developers** - Working on AgentUp itself (core contributors)
2. **Plugin Developers** - Creating reusable skills for the community
3. **Agent Developers** - Building specific AI agents using AgentUp

## Table of Contents

- [Framework Development](#framework-development)
- [Plugin Development](#plugin-development)
- [Agent Development](#agent-development)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Framework Development

> **You are here if:** You're contributing to AgentUp core, working with the source repository

### Environment Setup

```bash
# Clone and setup AgentUp source
git clone https://github.com/RedDotRocket/AgentUp.git
cd AgentUp

# Create isolated development environment
uv sync

# Verify installation
uv run agentup --version
```

### Plugin Development for Framework Contributors

When developing plugins while working on AgentUp source:

#### Option 1: Separate Plugin Directory (Recommended)

```bash
# Create plugin in separate location
cd ~/my-plugins  # Or any directory outside AgentUp source
uv run --directory /path/to/AgentUp agentup plugin create my-plugin

# Install plugin into AgentUp's venv for testing
cd my-plugin
uv --directory /path/to/AgentUp pip install -e .

# Test with AgentUp development server
cd /path/to/AgentUp
uv run agentup agent serve
```

#### Option 2: AgentUp Plugin Development Mode

```bash
# From AgentUp source directory
export AGENTUP_PLUGIN_PATHS="$HOME/my-plugins:./local-plugins"

# Create and test plugins without installation
mkdir -p local-plugins
uv run agentup plugin create local-plugins/test-plugin

# Plugin auto-discovered from AGENTUP_PLUGIN_PATHS
uv run agentup agent serve
```

### Testing Framework Changes

```bash
# Run framework tests
uv run pytest

# Test with example agent
cd examples/basic-agent
uv run --directory ../.. agentup agent serve

# Test CLI commands
uv run agentup agent create test-agent --template minimal
```

### Key Considerations

- **Always use `uv run` from AgentUp source directory**
- **Plugin paths are relative to where AgentUp runs, not where plugins live**
- **Use `AGENTUP_PLUGIN_PATHS` for local plugin development**
- **Never install plugins with system pip - always use AgentUp's venv**

---

## Plugin Development

> **You are here if:** You're creating reusable plugins that others can install

### Scenario 1: Using Installed AgentUp

Most plugin developers will use this approach:

```bash
# Install AgentUp globally or in project venv
pip install agentup
# OR: python -m venv venv && source venv/bin/activate && pip install agentup

# Create plugin anywhere
mkdir -p ~/my-plugins && cd ~/my-plugins
agentup plugin create weather-plugin --template advanced
cd weather-plugin

# Install for development (same environment as AgentUp)
pip install -e .

# Create test agent
mkdir -p ~/test-agents && cd ~/test-agents
agentup agent create weather-test --template standard

# Configure agent to use your plugin
echo "
skills:
  - skill_id: weather_plugin
    routing_mode: ai
" >> weather-test/agent_config.yaml

# Test your plugin
cd weather-test
agentup agent serve
```

### Scenario 2: Using AgentUp Source

If you need to test against AgentUp development version:

```bash
# Setup AgentUp source environment
git clone https://github.com/your-org/AgentUp.git
cd AgentUp && uv sync

# Create plugin in separate directory
cd ~/my-plugins
uv run --directory /path/to/AgentUp agentup plugin create my-plugin
cd my-plugin

# Install into AgentUp's development environment
uv --directory /path/to/AgentUp pip install -e .

# Test with AgentUp source
cd /path/to/AgentUp
uv run agentup agent serve
```

### Plugin Development Workflow

```bash
# Development cycle
cd ~/my-plugins/weather-plugin

# Make changes to plugin.py
vim src/weather_plugin/plugin.py

# Reinstall if entry points changed
pip install -e .

# Test changes
cd ~/test-agents/weather-test
agentup agent serve --reload  # Auto-reloads on file changes
```

### Environment Variables for Plugin Development

```bash
# Add to ~/.bashrc or ~/.zshrc
export AGENTUP_PLUGIN_PATHS="$HOME/my-plugins/dev-plugins:./plugins"
export AGENTUP_DEV_MODE=true  # Enables additional debugging
export AGENTUP_LOG_LEVEL=DEBUG  # More verbose logging
```

### Publishing Plugins

```bash
# Build and publish
cd ~/my-plugins/weather-plugin
python -m build
python -m twine upload dist/*

# Users can then install with:
# pip install weather-plugin
```

---

## Agent Development

> **You are here if:** You're building specific AI agents using AgentUp

### Project-Based Development

Agent development should be project-isolated:

```bash
# Create agent project
mkdir -p ~/my-agents && cd ~/my-agents
agentup agent create customer-service --template standard
cd customer-service

# All commands run from agent directory
agentup agent serve           # Start development server
agentup agent validate        # Validate configuration
agentup agent deploy --type docker  # Generate deployment files
```

### Installing Plugins in Agent Projects

```bash
# From agent directory
cd ~/my-agents/customer-service

# Install community plugins
pip install weather-plugin time-plugin

# Install local development plugins
pip install -e ~/my-plugins/custom-plugin

# Configure in agent_config.yaml
vim agent_config.yaml
```

### Multi-Agent Development

When working with multiple agents:

```bash
# Shared plugin environment approach
python -m venv ~/shared-agent-env
source ~/shared-agent-env/bin/activate
pip install agentup weather-plugin time-plugin custom-plugin

# Create agents using shared environment
agentup agent create agent1
agentup agent create agent2

# Each agent can use the same plugins
cd agent1 && agentup agent serve --port 8001
cd agent2 && agentup agent serve --port 8002
```

### Path Management for Agents

AgentUp uses relative paths that work from any agent directory:

```bash
# These paths are relative to agent working directory
agent_config.yaml           # Always in agent root
./skills/                   # Local skills directory
./conversation_states/      # State storage
./logs/                     # Log files
./.agentup/                 # Agent-specific cache
```

### Configuration Management

```yaml
# agent_config.yaml - paths relative to agent directory
state:
  backend: file
  storage_dir: ./conversation_states  # Relative to agent root

services:
  file_storage:
    type: filesystem
    config:
      base_path: ./data             # Relative to agent root

plugins:
```

---

## Troubleshooting

### Common Issues and Solutions

#### "externally-managed-environment" Error

**Problem:** macOS/Homebrew Python prevents system-wide pip installs

**Solutions:**

```bash
# Option 1: Use virtual environment (recommended)
python -m venv agentup-env
source agentup-env/bin/activate
pip install agentup

# Option 2: Use --user flag
pip install --user agentup

# Option 3: Use pipx for CLI tools
brew install pipx
pipx install agentup

# Option 4: Override (not recommended)
pip install --break-system-packages agentup
```

#### Plugin Not Found After Installation

**Problem:** Plugin installed but not discovered

**Debugging Steps:**

```bash
# Check if plugin is installed
pip list | grep your-plugin

# Verify entry points
python -c "
import importlib.metadata
eps = importlib.metadata.entry_points()
skills = eps.get('agentup.skills', [])
for ep in skills:
    print(f'{ep.name}: {ep.value}')
"

# Check AgentUp discovery
agentup plugin list

# Enable debug logging
AGENTUP_LOG_LEVEL=DEBUG agentup agent serve
```

#### Import Errors in Plugins

**Problem:** Plugin can't import AgentUp components

**Common Causes:**

```bash
# Wrong import path
from agentup.plugins import SkillInfo  # ✗ Wrong

# Correct import path
from agent.plugins import SkillInfo    # ✓ Correct

# Check your plugin's imports
grep -r "from agentup" src/
```

#### Path Resolution Issues

**Problem:** Files not found, relative paths broken

**Solution:** Always run AgentUp commands from agent directory

```bash
# ✗ Wrong - broken relative paths
cd ~ && agentup agent serve --config /path/to/agent/agent_config.yaml

# ✓ Correct - relative paths work
cd /path/to/agent && agentup agent serve
```

#### Virtual Environment Confusion

**Problem:** Plugin installed in wrong environment

**Debugging:**

```bash
# Check which AgentUp you're using
which agentup
python -c "import agent; print(agent.__file__)"

# Check which Python environment
python -c "import sys; print(sys.prefix)"

# Ensure consistent environment
# If using venv:
source venv/bin/activate && pip install -e plugin-path

# If using uv with AgentUp source:
uv pip install -e plugin-path
```

### Environment Debugging Commands

```bash
# Comprehensive environment check
echo "=== AgentUp Environment Debug ==="
echo "AgentUp location: $(which agentup)"
echo "Python location: $(which python)"
echo "Python version: $(python --version)"
echo "Virtual env: $VIRTUAL_ENV"
echo "Python path: $(python -c 'import sys; print(sys.prefix)')"
echo ""
echo "=== Installed Packages ==="
pip list | grep -E "(agentup|agent)"
echo ""
echo "=== Plugin Entry Points ==="
python -c "
import importlib.metadata
try:
    eps = importlib.metadata.entry_points()
    if hasattr(eps, 'select'):
        skills = eps.select(group='agentup.skills')
    else:
        skills = eps.get('agentup.skills', [])
    for ep in skills:
        print(f'{ep.name}: {ep.value}')
except Exception as e:
    print(f'Error: {e}')
"
echo ""
echo "=== Environment Variables ==="
env | grep -i agentup
```

---

## Best Practices

### 1. Environment Isolation

**Framework Development:**
```bash
# Keep AgentUp source isolated
cd ~/code/AgentUp
uv sync  # Creates .venv automatically

# Use uv run for all commands
uv run agentup agent serve
```

**Plugin Development:**
```bash
# Use project-specific environments
cd ~/plugins/weather-plugin
python -m venv .venv
source .venv/bin/activate
pip install agentup
pip install -e .
```

**Agent Development:**
```bash
# Keep agents in project directories
mkdir -p ~/projects/customer-ai && cd ~/projects/customer-ai
agentup agent create .  # Create agent in current directory
```

### 2. Path Management

**Always use relative paths in configuration:**
```yaml
# ✓ Good - relative to agent directory
state:
  backend: file
  storage_dir: ./states

# ✗ Bad - absolute paths break portability
state:
  backend: file
  storage_dir: /Users/you/projects/agent/states
```

**Use environment variables for environment-specific paths:**
```yaml
# agent_config.yaml
services:
  database:
    config:
      url: ${DATABASE_URL:sqlite:///./data.db}  # Default to relative path
```

### 3. Plugin Discovery

**Set up plugin search paths:**
```bash
# Add to shell profile
export AGENTUP_PLUGIN_PATHS="$HOME/.agentup/plugins:./plugins:../shared-plugins"
```

**Use consistent plugin structure:**
```
plugins/
├── weather-plugin/
│   ├── pyproject.toml
│   ├── src/weather_plugin/
│   │   ├── __init__.py
│   │   └── plugin.py
│   └── tests/
└── time-plugin/
    ├── pyproject.toml
    ├── src/time_plugin/
    │   ├── __init__.py
    │   └── plugin.py
    └── tests/
```

### 4. Development Workflow

**Plugin Development Cycle:**
```bash
# 1. Make changes
vim src/my_plugin/plugin.py

# 2. Reinstall if structure changed
pip install -e .

# 3. Test immediately
agentup agent serve --reload

# 4. Run tests
pytest tests/

# 5. Validate integration
agentup plugin validate my_plugin
```

**Agent Development Cycle:**
```bash
# 1. Update configuration
vim agent_config.yaml

# 2. Validate changes
agentup agent validate

# 3. Test locally
agentup agent serve --reload

# 4. Generate deployment
agentup agent deploy --type docker
```

### 5. Testing Strategies

**Local Plugin Testing:**
```bash
# Create minimal test agent
agentup agent create test-minimal --template minimal
cd test-minimal

# Add your plugin
echo "skills: [{skill_id: your_plugin}]" >> agent_config.yaml

# Test specific scenarios
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "message/send", "params": {...}}'
```

**Integration Testing:**
```bash
# Test plugin across different agent templates
for template in minimal standard full; do
  agentup agent create test-$template --template $template
  cd test-$template
  # Add plugin configuration
  # Test scenarios
  cd ..
done
```

### 6. Documentation and Distribution

**Plugin Documentation:**
```markdown
# Plugin README Template

## Installation
```bash
pip install your-plugin
```

## Configuration
```yaml
skills:
  - skill_id: your_plugin
    config:
      api_key: ${YOUR_API_KEY}
```

## Environment Variables
- `YOUR_API_KEY`: Required API key for service
- `YOUR_PLUGIN_DEBUG`: Enable debug logging

## Examples
[Include common usage examples]
```

This developer guide provides comprehensive, trouble-free development environments for all AgentUp development scenarios. Follow the patterns for your specific use case to avoid common pitfalls and maintain productive development workflows.