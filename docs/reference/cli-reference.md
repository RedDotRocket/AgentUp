# CLI Reference

Complete reference for all AgentUp command-line interface commands.

## Global Options

Available for all commands:

```bash
agentup [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--version` | Show AgentUp version | |
| `--help` | Show help message | |
| `--config-dir DIR` | Configuration directory | `~/.agentup` |
| `--log-level LEVEL` | Set log level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `--no-color` | Disable colored output | |
| `--quiet` | Suppress non-error output | |
| `--verbose` | Enable verbose output | |

## Agent Commands

### `agentup agent create`

Create a new agent project.

```bash
agentup agent create [OPTIONS] NAME
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--template TEMPLATE` | Template to use (minimal, full) | `minimal` |
| `--output-dir DIR` | Output directory | Current directory |
| `--force` | Overwrite existing directory | |
| `--no-git` | Don't initialize git repository | |
| `--author AUTHOR` | Set agent author | |
| `--description DESC` | Set agent description | |

#### Examples

```bash
# Create minimal agent
agentup agent create my-agent

# Create full-featured agent
agentup agent create my-agent --template full

# Create with custom metadata
agentup agent create my-agent \
  --author "John Doe" \
  --description "My awesome agent"

# Create in specific directory
agentup agent create my-agent --output-dir /path/to/agents/
```

### `agentup agent serve`

Start the agent development server.

```bash
agentup agent serve [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config FILE` | Configuration file | `agent_config.yaml` |
| `--host HOST` | Bind address | `localhost` |
| `--port PORT` | Port number | `8000` |
| `--reload` | Enable auto-reload on file changes | |
| `--workers NUM` | Number of worker processes | `1` |
| `--log-config FILE` | Logging configuration file | |
| `--access-log` | Enable access logging | |

#### Examples

```bash
# Start with default settings
agentup agent serve

# Start on specific host/port
agentup agent serve --host 0.0.0.0 --port 9000

# Enable auto-reload for development
agentup agent serve --reload

# Use custom configuration
agentup agent serve --config custom_config.yaml
```

### `agentup agent validate`

Validate agent configuration.

```bash
agentup agent validate [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config FILE` | Configuration file to validate | `agent_config.yaml` |
| `--schema FILE` | JSON schema file for validation | |
| `--strict` | Enable strict validation | |
| `--output FORMAT` | Output format (text, json) | `text` |

#### Examples

```bash
# Validate default configuration
agentup agent validate

# Validate specific file
agentup agent validate --config prod_config.yaml

# Strict validation with JSON output
agentup agent validate --strict --output json
```

### `agentup agent deploy`

Deploy agent to production environment.

```bash
agentup agent deploy [OPTIONS] ENVIRONMENT
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config FILE` | Configuration file | `agent_config.yaml` |
| `--build` | Build before deployment | |
| `--dry-run` | Show what would be deployed | |
| `--force` | Force deployment without confirmation | |

#### Examples

```bash
# Deploy to production
agentup agent deploy production

# Dry run deployment
agentup agent deploy production --dry-run

# Force deployment with build
agentup agent deploy production --build --force
```

### `agentup agent status`

Check agent status and health.

```bash
agentup agent status [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--url URL` | Agent URL | `http://localhost:8000` |
| `--timeout SECONDS` | Request timeout | `10` |
| `--format FORMAT` | Output format (text, json) | `text` |

#### Examples

```bash
# Check local agent status
agentup agent status

# Check remote agent
agentup agent status --url https://my-agent.example.com

# JSON output
agentup agent status --format json
```

## Plugin Commands

### `agentup plugin create`

Create a new plugin project.

```bash
agentup plugin create [OPTIONS] NAME
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--template TEMPLATE` | Plugin template | `direct` |
| `--output-dir DIR` | Output directory | Current directory |
| `--author AUTHOR` | Plugin author | |
| `--description DESC` | Plugin description | |
| `--capabilities LIST` | Comma-separated capability names | |

#### Examples

```bash
# Create basic plugin
agentup plugin create my-plugin

# Create with capabilities
agentup plugin create my-plugin \
  --capabilities "read_file,write_file,process_data"

# Create with metadata
agentup plugin create my-plugin \
  --author "Jane Doe" \
  --description "File processing plugin"
```

### `agentup plugin list`

List installed plugins.

```bash
agentup plugin list [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format FORMAT` | Output format (text, json, table) | `table` |
| `--show-capabilities` | Show plugin capabilities | |
| `--filter PATTERN` | Filter plugins by name pattern | |

#### Examples

```bash
# List all plugins
agentup plugin list

# Show with capabilities
agentup plugin list --show-capabilities

# Filter by name
agentup plugin list --filter "system*"

# JSON output
agentup plugin list --format json
```

### `agentup plugin install`

Install a plugin package.

```bash
agentup plugin install [OPTIONS] PACKAGE
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--upgrade` | Upgrade if already installed | |
| `--user` | Install for current user only | |
| `--force` | Force installation | |
| `--no-deps` | Don't install dependencies | |

#### Examples

```bash
# Install plugin
agentup plugin install agentup-web-tools

# Install and upgrade
agentup plugin install agentup-web-tools --upgrade

# Install from git
agentup plugin install git+https://github.com/user/plugin.git

# Install local plugin
agentup plugin install ./my-plugin/
```

### `agentup plugin uninstall`

Uninstall a plugin package.

```bash
agentup plugin uninstall [OPTIONS] PACKAGE
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Force uninstall without confirmation | |
| `--no-deps` | Don't remove dependencies | |

#### Examples

```bash
# Uninstall plugin
agentup plugin uninstall agentup-web-tools

# Force uninstall
agentup plugin uninstall agentup-web-tools --force
```

### `agentup plugin validate`

Validate plugin configuration and structure.

```bash
agentup plugin validate [OPTIONS] [PATH]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--strict` | Enable strict validation | |
| `--check-entry-points` | Validate entry points | |
| `--output FORMAT` | Output format (text, json) | `text` |

#### Examples

```bash
# Validate current plugin
agentup plugin validate

# Validate specific plugin
agentup plugin validate /path/to/plugin/

# Strict validation
agentup plugin validate --strict --check-entry-points
```

## System Commands

### `agentup system info`

Show system and environment information.

```bash
agentup system info [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format FORMAT` | Output format (text, json) | `text` |
| `--include-env` | Include environment variables | |

#### Examples

```bash
# Show system info
agentup system info

# JSON output with environment
agentup system info --format json --include-env
```

### `agentup system check`

Check system requirements and dependencies.

```bash
agentup system check [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--fix` | Attempt to fix issues | |
| `--strict` | Strict requirement checking | |

#### Examples

```bash
# Check system
agentup system check

# Check and fix issues
agentup system check --fix
```

## Configuration Commands

### `agentup config show`

Show configuration values.

```bash
agentup config show [OPTIONS] [KEY]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config FILE` | Configuration file | `agent_config.yaml` |
| `--resolve-env` | Resolve environment variables | |
| `--format FORMAT` | Output format (text, json, yaml) | `yaml` |

#### Examples

```bash
# Show all configuration
agentup config show

# Show specific key
agentup config show plugins

# Resolve environment variables
agentup config show --resolve-env
```

### `agentup config set`

Set configuration values.

```bash
agentup config set [OPTIONS] KEY VALUE
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config FILE` | Configuration file | `agent_config.yaml` |
| `--type TYPE` | Value type (string, int, bool, list) | `string` |

#### Examples

```bash
# Set string value
agentup config set name "My Agent"

# Set integer value
agentup config set server.port 9000 --type int

# Set boolean value
agentup config set state_management.enabled true --type bool
```

## Environment Variables

AgentUp CLI respects these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTUP_CONFIG_DIR` | Global configuration directory | `~/.agentup` |
| `AGENTUP_LOG_LEVEL` | Default log level | `INFO` |
| `AGENTUP_NO_COLOR` | Disable colored output | `false` |
| `AGENTUP_DEFAULT_TEMPLATE` | Default agent template | `minimal` |
| `AGENTUP_DEFAULT_PORT` | Default server port | `8000` |
| `AGENTUP_DEFAULT_HOST` | Default server host | `localhost` |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Plugin error |
| 4 | Network error |
| 5 | Permission error |
| 126 | Command not executable |
| 127 | Command not found |

## Shell Completion

Enable shell completion for bash, zsh, or fish:

```bash
# Bash
agentup --install-completion bash

# Zsh  
agentup --install-completion zsh

# Fish
agentup --install-completion fish

# Show completion script
agentup --show-completion bash
```

## Getting Help

Get help for any command:

```bash
# General help
agentup --help

# Command help
agentup agent --help
agentup plugin create --help

# Subcommand help
agentup agent serve --help
```

## Common Usage Patterns

### Development Workflow

```bash
# Create and start agent
agentup agent create my-agent
cd my-agent
agentup agent serve --reload

# Validate and deploy
agentup agent validate
agentup agent deploy production
```

### Plugin Development

```bash
# Create and test plugin
agentup plugin create my-plugin
cd my-plugin
agentup plugin validate
pip install -e .
agentup plugin list
```

### Debugging

```bash
# Check system and configuration
agentup system check
agentup config show --resolve-env
agentup agent validate --strict

# Check agent status
agentup agent status --format json
```
