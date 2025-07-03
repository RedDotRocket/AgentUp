# Plugin CLI Reference

This reference covers all AgentUp plugin CLI commands with complete usage examples and options.

## Overview

The AgentUp CLI provides comprehensive plugin management through the `agentup plugin` command group:

```bash
agentup plugin --help
```

## Important: Working Directory Context

**Plugin Creation Commands** (`agentup plugin create`):
- Can be run from **any directory** on your system
- Creates a new plugin project directory
- Does **NOT** require an existing agent project

**Plugin Management Commands** (list, reload, info, etc.):
- Should be run from within an **agent project directory**
- Operate on plugins available to that specific agent
- Require an `agent_config.yaml` file to exist

```bash
# Plugin creation - run from anywhere
cd ~/my-projects/
agentup plugin create weather-plugin

# Plugin management - run from agent project
cd ~/my-agent-project/
agentup plugin list
agentup plugin reload weather
```

## Commands

### `agentup plugin list`

List all loaded plugins and their skills.

#### Usage

```bash
agentup plugin list [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--verbose, -v` | Show detailed plugin information | `false` |
| `--format, -f` | Output format: `table`, `json`, `yaml` | `table` |

#### Examples

**Basic listing:**
```bash
agentup plugin list
```

Output:
```
┌─────────────────────────────── Loaded Plugins ───────────────────────────────┐
│ Plugin      │ Version │ Status │ Skills │
├─────────────┼─────────┼────────┼────────┤
│ weather     │ 1.0.0   │ loaded │ 1      │
│ calculator  │ 1.2.1   │ loaded │ 1      │
└─────────────┴─────────┴────────┴────────┘

┌─────────────────────────────── Available Skills ─────────────────────────────┐
│ Skill ID    │ Name        │ Plugin      │ Capabilities     │
├─────────────┼─────────────┼─────────────┼──────────────────┤
│ weather     │ Weather     │ weather     │ text, ai_function│
│ calculator  │ Calculator  │ calculator  │ text, ai_function│
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

**Verbose output:**
```bash
agentup plugin list --verbose
```

**JSON output:**
```bash
agentup plugin list --format json
```

Output:
```json
{
  "plugins": [
    {
      "name": "weather",
      "version": "1.0.0",
      "status": "loaded",
      "author": "Your Name",
      "description": "Weather information plugin"
    }
  ],
  "skills": [
    {
      "id": "weather",
      "name": "Weather",
      "version": "1.0.0",
      "plugin": "weather",
      "capabilities": ["text", "ai_function"]
    }
  ]
}
```

---

### `agentup plugin create`

Create a new plugin for development.

#### Usage

```bash
agentup plugin create [NAME] [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `NAME` | Plugin name | No (interactive prompt if not provided) |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--template, -t` | Plugin template: `basic`, `advanced`, `ai` | `basic` |
| `--output-dir, -o` | Output directory for plugin | `./[plugin-name]` |
| `--no-git` | Skip git initialization | `false` |

#### Examples

**Interactive creation:**
```bash
agentup plugin create
```

The CLI will prompt for:
- Plugin name
- Display name
- Description
- Author name
- Primary skill ID

**Quick creation with template:**
```bash
agentup plugin create weather-plugin --template ai
```

**Specify output directory:**
```bash
agentup plugin create my-plugin --output-dir ./plugins/my-plugin
```

**Skip git initialization:**
```bash
agentup plugin create simple-plugin --no-git
```

#### Generated Structure

```
plugin-name/
├── pyproject.toml          # Package configuration
├── README.md               # Documentation
├── .gitignore              # Git ignore patterns
├── src/
│   └── plugin_name/
│       ├── __init__.py
│       └── plugin.py       # Main plugin code
└── tests/
    └── test_plugin_name.py # Test suite
```

---

### `agentup plugin install`

Install a plugin from PyPI, Git, or local directory.

#### Usage

```bash
agentup plugin install PLUGIN_NAME [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PLUGIN_NAME` | Plugin name or path | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--source, -s` | Installation source: `pypi`, `git`, `local` | `pypi` |
| `--url, -u` | Git URL or local path (for git/local sources) | None |
| `--force, -f` | Force reinstall if already installed | `false` |

#### Examples

**Install from PyPI:**
```bash
agentup plugin install weather-plugin
```

**Install from Git repository:**
```bash
agentup plugin install my-plugin --source git --url https://github.com/user/my-plugin.git
```

**Install from local directory:**
```bash
agentup plugin install my-plugin --source local --url ./path/to/plugin
```

**Force reinstall:**
```bash
agentup plugin install weather-plugin --force
```

**Install specific version:**
```bash
agentup plugin install weather-plugin==1.2.0
```

---

### `agentup plugin uninstall`

Uninstall a plugin.

#### Usage

```bash
agentup plugin uninstall PLUGIN_NAME
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PLUGIN_NAME` | Plugin name to uninstall | Yes |

#### Examples

**Uninstall plugin:**
```bash
agentup plugin uninstall weather-plugin
```

The CLI will prompt for confirmation unless you use a package manager directly.

---

### `agentup plugin reload`

Reload a plugin during development.

#### Usage

```bash
agentup plugin reload PLUGIN_NAME
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PLUGIN_NAME` | Plugin name to reload | Yes |

#### Examples

**Reload plugin:**
```bash
agentup plugin reload weather-plugin
```

**Note:** Only works for local development plugins. Entry point plugins cannot be reloaded and require agent restart.

---

### `agentup plugin info`

Show detailed information about a plugin skill.

#### Usage

```bash
agentup plugin info SKILL_ID
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `SKILL_ID` | Skill ID to show information for | Yes |

#### Examples

**Show skill information:**
```bash
agentup plugin info weather
```

Output:
```
┌─────────────────────────────── Weather ───────────────────────────────────┐
│                                                                            │
│  Skill ID: weather                                                         │
│  Name: Weather Information                                                 │
│  Version: 1.0.0                                                           │
│  Description: Provides weather information and forecasts                  │
│  Plugin: weather_plugin                                                   │
│  Capabilities: text, ai_function                                          │
│  Tags: weather, api, forecast                                             │
│  Priority: 50                                                             │
│  Input Mode: text                                                         │
│  Output Mode: text                                                        │
│                                                                            │
│  Plugin Information:                                                       │
│  Status: loaded                                                           │
│  Author: Your Name                                                        │
│  Source: entry_point                                                      │
│                                                                            │
│  Configuration Schema:                                                     │
│  {                                                                         │
│    "type": "object",                                                       │
│    "properties": {                                                         │
│      "api_key": {                                                          │
│        "type": "string",                                                   │
│        "description": "OpenWeatherMap API key"                            │
│      }                                                                     │
│    },                                                                      │
│    "required": ["api_key"]                                                │
│  }                                                                         │
│                                                                            │
│  AI Functions:                                                             │
│    • get_weather: Get current weather for a location                      │
│    • get_forecast: Get weather forecast for a location                    │
│                                                                            │
│  Health Status:                                                            │
│    • status: healthy                                                       │
│    • api_configured: true                                                  │
│    • version: 1.0.0                                                       │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### `agentup plugin validate`

Validate all loaded plugins and their configurations.

#### Usage

```bash
agentup plugin validate
```

#### Examples

**Validate all plugins:**
```bash
agentup plugin validate
```

Output:
```
Validating plugins...

┌─────────────────────────── Plugin Validation Results ────────────────────────────┐
│ Skill       │ Plugin      │ Status      │ Issues                                   │
├─────────────┼─────────────┼─────────────┼──────────────────────────────────────────┤
│ weather     │ weather     │ ✓ Valid     │                                          │
│ calculator  │ calculator  │ ✓ Valid     │                                          │
│ broken_skill│ broken      │ ✗ Invalid   │ Missing required config: api_key        │
└─────────────┴─────────────┴─────────────┴──────────────────────────────────────────┘

❌ Some plugins have validation errors.
Please check your agent_config.yaml and fix the issues.
```

---

## Development Workflow Commands

### Creating and Testing Plugins

**1. Create a new plugin:**
```bash
agentup plugin create my-awesome-plugin --template ai
cd my-awesome-plugin
```

**2. Install in development mode:**
```bash
pip install -e .
```

**3. Verify installation:**
```bash
agentup plugin list
```

**4. Test the plugin:**
```bash
pytest tests/ -v
```

**5. Reload during development:**
```bash
agentup plugin reload my_awesome_plugin
```

### Publishing Workflow

**1. Validate plugin:**
```bash
agentup plugin validate
```

**2. Run tests:**
```bash
pytest tests/ -v
```

**3. Build package:**
```bash
python -m build
```

**4. Publish to PyPI:**
```bash
python -m twine upload dist/*
```

## Global Options

All plugin commands support these global options:

| Option | Description |
|--------|-------------|
| `--help` | Show command help |
| `--verbose` | Enable verbose output |
| `--quiet` | Suppress non-error output |

## Configuration Files

### Plugin Configuration in `agent_config.yaml`

```yaml
# Global plugin settings
plugins:
  enabled: true
  
# Individual skill configurations
skills:
  - skill_id: weather
    config:
      api_key: "your-api-key"
      default_units: "imperial"
  
  - skill_id: calculator
    config:
      precision: 4
```

### Plugin Metadata in `pyproject.toml`

```toml
[project]
name = "my-plugin"
version = "1.0.0"
description = "My awesome AgentUp plugin"

[project.entry-points."agentup.skills"]
my_skill = "my_plugin.plugin:Plugin"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTUP_PLUGIN_DEBUG` | Enable plugin debug logging | `false` |
| `AGENTUP_PLUGIN_CACHE_DIR` | Plugin cache directory | `~/.agentup/cache` |
| `AGENTUP_PLUGIN_TIMEOUT` | Plugin operation timeout (seconds) | `30` |

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | General error |
| `2` | Plugin not found |
| `3` | Validation failed |
| `4` | Installation failed |
| `5` | Configuration error |

## Common Issues and Solutions

### Plugin Not Loading

**Issue:** Plugin doesn't appear in `agentup plugin list`

**Solutions:**
1. Check entry point configuration in `pyproject.toml`
2. Verify plugin is installed: `pip list | grep plugin-name`
3. Restart agent if using entry points
4. Check for import errors: `python -c "import your_plugin"`

### Validation Errors

**Issue:** Plugin fails validation

**Solutions:**
1. Check `agent_config.yaml` for required configuration
2. Verify configuration schema in plugin code
3. Review plugin logs for detailed error messages

### AI Functions Not Available

**Issue:** AI functions don't appear in LLM function calling

**Solutions:**
1. Ensure plugin implements `get_ai_functions()` hook
2. Verify function schemas are valid OpenAI format
3. Check that agent has AI capabilities enabled
4. Confirm plugin capabilities include `ai_function`

### Performance Issues

**Issue:** Plugin operations are slow

**Solutions:**
1. Enable caching in plugin configuration
2. Use async/await properly in plugin code
3. Implement request batching for external APIs
4. Profile plugin execution with debug logging

This CLI reference provides everything you need to effectively manage AgentUp plugins from the command line.