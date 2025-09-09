# Plugin CLI Reference

This reference covers all AgentUp plugin CLI commands with complete usage examples and options for the new decorator-based plugin system with trusted publishing support.

## Overview

The AgentUp CLI provides comprehensive plugin management through the `agentup plugin` command group:

```bash
agentup plugin --help
```

The new CLI includes advanced security features:
- **Trusted Publishing Verification**: Cryptographic verification of plugin authenticity
- **Publisher Trust Management**: Manage trusted plugin publishers
- **Security Installation Prompts**: Interactive safety checks for plugin installation
- **Plugin Discovery**: Automatic detection of decorator-based plugins

## Important: Working Directory Context

**Plugin Creation Commands** (`agentup plugin init`):
- Can be run from **any directory** on your system
- Creates a new plugin project directory
- Does **NOT** require an existing agent project

**Plugin Management Commands** (install, list, verify, etc.):
- Can be run from **any directory**
- Operate on system-wide plugin installations
- Use PyPI and trusted publishing for distribution

```bash
# Plugin creation - run from anywhere
cd ~/my-projects/
agentup plugin init weather-plugin

# Plugin management - run from anywhere  
agentup plugin install weather-plugin --require-trusted
agentup plugin list --trust-level community
```

## Commands

### `agentup plugin install`

Install an AgentUp plugin with security verification and trusted publishing support.

#### Usage

```bash
agentup plugin install PACKAGE_NAME [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PACKAGE_NAME` | PyPI package name to install | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--version, -v` | Specific version to install | Latest |
| `--force, -f` | Skip safety prompts | `false` |
| `--dry-run, -n` | Verify only, don't install | `false` |
| `--trust-level` | Minimum required trust level: `unknown`, `community`, `official` | `community` |
| `--require-trusted` | Require trusted publishing | `false` |

#### Examples

**Install latest version:**
```bash
agentup plugin install weather-plugin
```

**Install specific version:**
```bash
agentup plugin install weather-plugin --version 2.1.0
```

**Require trusted publishing:**
```bash
agentup plugin install weather-plugin --require-trusted
```

**Set minimum trust level:**
```bash
agentup plugin install weather-plugin --trust-level official
```

**Dry run (verification only):**
```bash
agentup plugin install weather-plugin --dry-run
```

#### Installation Process

The install command performs these security checks:

1. **Publisher Verification**: Validates plugin publisher identity
2. **Trust Level Assessment**: Evaluates plugin trust level  
3. **Security Scanning**: Checks for known vulnerabilities
4. **Interactive Approval**: Prompts user for confirmation (unless `--force`)
5. **Post-Installation Verification**: Confirms successful installation

---

### `agentup plugin uninstall`

Uninstall an AgentUp plugin.

#### Usage

```bash
agentup plugin uninstall PACKAGE_NAME [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PACKAGE_NAME` | Package name to uninstall | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--force, -f` | Skip confirmation prompt | `false` |

#### Examples

**Uninstall with confirmation:**
```bash
agentup plugin uninstall weather-plugin
```

**Force uninstall:**
```bash
agentup plugin uninstall weather-plugin --force
```

---

### `agentup plugin list`

List installed AgentUp plugins with trust information.

#### Usage

```bash
agentup plugin list [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--trust-level` | Filter by trust level: `all`, `unknown`, `community`, `official` | `all` |
| `--format` | Output format: `table`, `json`, `yaml` | `table` |

#### Examples

**List all plugins:**
```bash
agentup plugin list
```

Output:
```
📦 Installed AgentUp Plugins (3)
================================================================================
Name                           Version    Trust        Publisher           
--------------------------------------------------------------------------------
weather-plugin                 2.1.0      ✅ official   agentup-official    
time-plugin                    1.0.0      🟡 community  john-developer      
legacy-plugin                  0.9.0      ⚪ unknown    unknown             
--------------------------------------------------------------------------------
Summary: ✅ 1 official, 🟡 1 community, ⚪ 1 unknown
```

**Filter by trust level:**
```bash
agentup plugin list --trust-level official
```

**JSON output:**
```bash
agentup plugin list --format json
```

Output:
```json
[
  {
    "package_name": "weather-plugin",
    "version": "2.1.0",
    "trust_level": "official", 
    "trusted_publishing": true,
    "publisher": "agentup-official",
    "summary": "Comprehensive weather information plugin"
  }
]
```

---

### `agentup plugin search`

Search for AgentUp plugins on PyPI.

#### Usage

```bash
agentup plugin search QUERY [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `QUERY` | Search query | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max-results, -n` | Maximum number of results | `10` |

#### Examples

**Search for weather plugins:**
```bash
agentup plugin search weather
```

Output:
```
🔍 Found 5 plugins:
  • weather-plugin v2.1.0
    Comprehensive weather information and forecasts
    Author: AgentUp Official

  • simple-weather v1.0.0
    Basic weather information plugin
    Author: Community Developer
```

---

### `agentup plugin verify`

Verify plugin authenticity via trusted publishing.

#### Usage

```bash
agentup plugin verify PACKAGE_NAME [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PACKAGE_NAME` | Package name to verify | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--version, -v` | Specific version to verify | Latest |
| `--verbose` | Show detailed verification info | `false` |

#### Examples

**Verify plugin:**
```bash
agentup plugin verify weather-plugin
```

Output:
```
==================================================
📋 Verification Report: weather-plugin
==================================================
✅ Trusted Publishing: Yes
   Publisher: agentup-official
   Repository: github.com/agentup/weather-plugin
   Trust Level: official
   Workflow: publish.yml
```

**Verbose verification:**
```bash
agentup plugin verify weather-plugin --verbose
```

---

### `agentup plugin upgrade`

Upgrade an AgentUp plugin to the latest version.

#### Usage

```bash
agentup plugin upgrade PACKAGE_NAME [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PACKAGE_NAME` | Package name to upgrade | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--force, -f` | Skip safety prompts | `false` |

#### Examples

**Upgrade plugin:**
```bash
agentup plugin upgrade weather-plugin
```

---

### `agentup plugin status`

Show plugin system status and trust summary.

#### Usage

```bash
agentup plugin status [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format: `table`, `json` | `table` |

#### Examples

**Show status:**
```bash
agentup plugin status
```

Output:
```
🔒 AgentUp Plugin System Status
========================================
Total Plugins: 5
Total Capabilities: 12

🛡️  Trusted Publishing:
   Enabled: true
   Required: false
   Min Trust Level: community

📊 Trust Summary:
   Trusted Published: 3
   Official: 1
   Community: 2
   Unknown: 2

👥 Publishers:
   agentup-official: 1 plugins
   john-developer: 2 plugins
```

---

### `agentup plugin init`

Create a new plugin for development using the modern decorator system.

#### Usage

```bash
agentup plugin init [NAME] [OPTIONS]
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
agentup plugin init
```

The CLI will prompt for:
- Plugin name
- Display name  
- Description
- Author name
- Capabilities to include

**Quick creation with template:**
```bash
agentup plugin init weather-plugin --template ai
```

**Specify output directory:**
```bash
agentup plugin init my-plugin --output-dir ./plugins/my-plugin
```

#### Generated Structure

```
plugin-name/
├── .gitignore
├── pyproject.toml          # Package configuration with trusted publishing
├── README.md               # Documentation
├── src/
│   └── plugin_name/
│       ├── __init__.py
│       └── plugin.py       # Main plugin with @capability decorators
├── static/
│   └── logo.png           # Plugin logo
├── tests/
│   └── test_plugin_name.py # Test suite
└── .github/
    └── workflows/
        └── publish.yml     # Trusted publishing workflow
```

---

## Trust Management Commands

### `agentup plugin trust list`

List trusted publishers.

#### Usage

```bash
agentup plugin trust list [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format: `table`, `json` | `table` |

#### Examples

**List publishers:**
```bash
agentup plugin trust list
```

Output:
```
👥 Trusted Publishers
==================================================

📋 agentup-official
   Trust Level: official
   Description: Official AgentUp plugins
   Repositories:
     • github.com/agentup/*

📋 awesome-contributor  
   Trust Level: community
   Description: Weather plugin specialist
   Repositories:
     • github.com/awesome-contributor/weather-plugin
```

---

### `agentup plugin trust add`

Add a trusted publisher.

#### Usage

```bash
agentup plugin trust add PUBLISHER_ID REPOSITORIES... [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PUBLISHER_ID` | Unique publisher identifier | Yes |
| `REPOSITORIES` | Repository patterns (space-separated) | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--trust-level` | Trust level: `community`, `official` | `community` |
| `--description, -d` | Publisher description | Auto-generated |

#### Examples

**Add community publisher:**
```bash
agentup plugin trust add awesome-contributor \
  github.com/awesome-contributor/weather-plugin \
  --trust-level community \
  --description "Weather plugin specialist"
```

---

### `agentup plugin trust remove`

Remove a trusted publisher.

#### Usage

```bash
agentup plugin trust remove PUBLISHER_ID [OPTIONS]
```

#### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `PUBLISHER_ID` | Publisher ID to remove | Yes |

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--force, -f` | Skip confirmation prompt | `false` |

#### Examples

**Remove publisher:**
```bash
agentup plugin trust remove awesome-contributor
```

---

### `agentup plugin refresh`

Refresh plugin trust verification.

#### Usage

```bash
agentup plugin refresh [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--plugin-id` | Refresh specific plugin (all if not specified) | All |

#### Examples

**Refresh all plugins:**
```bash
agentup plugin refresh
```

**Refresh specific plugin:**
```bash
agentup plugin refresh --plugin-id weather-plugin
```

---

## Development Workflow

### Creating and Testing Plugins

**1. Create a new plugin:**
```bash
agentup plugin init my-awesome-plugin --template ai
cd my-awesome-plugin
```

**2. Install in development mode:**
```bash
uv add -e .     # or pip install -e .
```

**3. Verify installation:**
```bash
agentup plugin list
```

**4. Test the plugin:**
```bash
uv run pytest tests/ -v
```

**5. Create capabilities using decorators:**
```python
@capability(
    id="my_capability",
    name="My Capability", 
    description="Does something useful",
    scopes=["my:read"],
    ai_function=True
)
async def my_capability(self, param: str = "default", **kwargs):
    return {"success": True, "content": f"Processed: {param}"}
```

### Publishing Workflow with Trusted Publishing

**1. Set up trusted publishing on PyPI:**
- Visit https://pypi.org/manage/account/publishing/
- Add your GitHub repository as a trusted publisher

**2. Configure your plugin:**
```toml
# pyproject.toml
[tool.agentup.trusted-publishing]
publisher = "your-github-username"
repository = "your-username/plugin-repo"
workflow = "publish.yml"
trust_level = "community"
```

**3. Build and publish:**
```bash
git add .
git commit -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags
# GitHub Actions automatically publishes with trusted publishing
```

**4. Verify published plugin:**
```bash
agentup plugin verify your-plugin-name
```

## Configuration Files

### Agent Configuration

```yaml
# agentup.yml
plugins:
  - plugin_id: weather_plugin
    name: Weather Plugin
    description: Provides weather information
    enabled: true
    capabilities:
      - capability_id: get_weather
        enabled: true
        required_scopes: ["weather:read", "api:external"]

# Trust settings
plugin_installation:
  require_trusted_publishing: true
  minimum_trust_level: "community"
  interactive_prompts: true
```

### Plugin Metadata

```toml
# pyproject.toml
[project.entry-points."agentup.plugins"]
weather_plugin = "weather_plugin.plugin:WeatherPlugin"

[tool.agentup.trusted-publishing]
publisher = "your-github-username"
repository = "your-username/weather-plugin"
workflow = "publish.yml"
trust_level = "community"

[tool.agentup.plugin]
capabilities = ["weather:current", "weather:forecast"]
scopes = ["weather:read", "api:external"]
min_agentup_version = "2.0.0"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTUP_PLUGIN_DEBUG` | Enable plugin debug logging | `false` |
| `AGENTUP_PLUGIN_CACHE_DIR` | Plugin cache directory | `~/.agentup/cache` |
| `AGENTUP_PLUGIN_TIMEOUT` | Plugin operation timeout (seconds) | `30` |
| `AGENTUP_REQUIRE_TRUSTED` | Require trusted publishing globally | `false` |
| `AGENTUP_MIN_TRUST_LEVEL` | Minimum trust level globally | `community` |

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | General error |
| `2` | Plugin not found |
| `3` | Validation failed |
| `4` | Installation failed |
| `5` | Trust verification failed |
| `6` | Publisher not found |

## Common Issues and Solutions

### Plugin Not Loading

**Issue:** Plugin doesn't appear in `agentup plugin list`

**Solutions:**
1. Check entry point configuration in `pyproject.toml`
2. Verify plugin is installed: `uv pip list | grep plugin-name`
3. Check that plugin class inherits from `Plugin`
4. Verify `@capability` decorators are properly imported

### Trust Verification Failing

**Issue:** Plugin fails trust verification

**Solutions:**
1. Check publisher configuration in `pyproject.toml`
2. Verify GitHub repository settings for trusted publishing
3. Use `agentup plugin verify plugin-name --verbose` for details
4. Ensure PyPI trusted publisher is properly configured

### Capabilities Not Discovered

**Issue:** Plugin capabilities don't appear in agent

**Solutions:**
1. Ensure methods are decorated with `@capability`
2. Verify the plugin class calls `super().__init__()`
3. Check that capability IDs are unique
4. Import decorators: `from agent.plugins.decorators import capability`

### AI Functions Not Available

**Issue:** AI functions don't appear in LLM function calling

**Solutions:**
1. Set `ai_function=True` in the `@capability` decorator
2. Verify `ai_parameters` follows OpenAI function schema format
3. Ensure method signatures match the parameters schema
4. Check agent has AI provider configured

### Security/Scope Errors

**Issue:** Plugin fails with permission errors

**Solutions:**
1. Verify required scopes match capability declarations
2. Check agent configuration grants necessary permissions
3. Use `agentup plugin status` to see trust information
4. Ensure plugin is from trusted publisher if required

This comprehensive CLI reference covers all aspects of managing AgentUp plugins with the new decorator-based system and trusted publishing features.
