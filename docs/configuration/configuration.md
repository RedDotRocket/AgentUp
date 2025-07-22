# AgentUp Plugin Configuration Reference

This document provides a comprehensive reference for all implemented plugin configuration options in AgentUp. Each configuration option has been verified through code inspection to ensure accuracy.

## Overview

AgentUp uses a plugin-based architecture where plugins are configured in the `plugins:` section of `agentup.yml`. Plugins provide capabilities that can be invoked either through AI routing (LLM selects appropriate functions) or direct routing (keywords/patterns trigger specific plugins).

## Plugin Configuration Structure

```yaml
plugins:
  - plugin_id: "my_plugin"           # Required: Unique plugin identifier
    name: "My Plugin"                # Plugin display name
    description: "Plugin description" # Plugin description
    enabled: true                    # Whether plugin is enabled (default: true)

    # Routing configuration (implicit)
    keywords: ["hello", "greet"]     # Keywords for direct routing
    patterns: ["^say .*"]            # Regex patterns for direct routing
    priority: 100                    # Priority for conflict resolution (default: 100)

    # Middleware override (optional)
    middleware_override:
      - name: "cached"
        params:
          ttl: 600

    # Plugin capabilities
    capabilities:
      - capability_id: "hello"
        required_scopes: ["api:read"]
        enabled: true

    # Plugin-specific configuration
    config:
      custom_setting: "value"
```

## Complete Configuration Reference

### Required Configuration Keys

#### plugin_id (Required)

Unique identifier for the plugin.

**Type:** `string`
**Example:** `"system_tools"`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Line:** 461
- **Code:**
```python
plugin_id = plugin_data["plugin_id"]
```

---

### Basic Plugin Information

#### name

Human-readable display name for the plugin.

**Type:** `string`
**Default:** Value of `plugin_id` if not specified
**Example:** `"System Tools"`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Line:** 470
- **Code:**
```python
"name": plugin_data.get("name", plugin_id),
```

#### description

Description of what the plugin does.

**Type:** `string`
**Default:** Empty string
**Example:** `"Provides system-level operations like file management"`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Line:** 471
- **Code:**
```python
"description": plugin_data.get("description", ""),
```

#### enabled

Controls whether the plugin is active and available for use.

**Type:** `boolean`
**Default:** `true`
**Example:** `false`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Lines:** 459-460
- **Code:**
```python
if plugin_data.get("enabled", True):
    plugin_id = plugin_data["plugin_id"]
```

---

### Routing Configuration

AgentUp uses an **implicit routing system** - there is no `routing_mode` per plugin. Instead, routing is determined by the presence of routing configurations:

- **Direct Routing:** Available if `keywords` or `patterns` are defined
- **AI Routing:** Always available for all enabled plugins

#### keywords

Array of keywords that trigger direct routing to this plugin when found in user input.

**Type:** `array[string]`
**Default:** `[]`
**Example:** `["file", "directory", "ls", "cat"]`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Lines:** 462, 493-500
- **Code:**
```python
keywords = plugin_data.get("keywords", [])
# ...
# Check keywords
for keyword in keywords:
    if keyword.lower() in user_input.lower():
        logger.debug(f"Matched keyword '{keyword}' for plugin '{plugin_id}'")
        direct_matches.append((plugin_id, plugin_config["priority"]))
        break
```

#### patterns

Array of regex patterns that trigger direct routing to this plugin when matched against user input.

**Type:** `array[string]`
**Default:** `[]`
**Example:** `["^create file .*", "^delete .*"]`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Lines:** 463, 501-508
- **Code:**
```python
patterns = plugin_data.get("patterns", [])
# ...
# Check patterns if no keyword match found for this plugin
if (plugin_id, plugin_config["priority"]) not in direct_matches:
    for pattern in patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            logger.debug(f"Matched pattern '{pattern}' for plugin '{plugin_id}'")
            direct_matches.append((plugin_id, plugin_config["priority"]))
            break
```

#### priority

Numeric priority for resolving conflicts when multiple plugins match the same input. Higher values = higher priority.

**Type:** `integer`
**Default:** `100`
**Example:** `200`

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Lines:** 472, 515-519
- **Code:**
```python
"priority": plugin_data.get("priority", 100),
# ...
if direct_matches:
    # Sort by priority (highest first) then by plugin_id for determinism
    direct_matches.sort(key=lambda x: (-x[1], x[0]))
    selected_plugin = direct_matches[0][0]
    logger.info(f"Direct routing to plugin '{selected_plugin}' (priority: {direct_matches[0][1]})")
```

---

### Middleware Configuration

#### middleware_override

Override global middleware configuration for this specific plugin. Each plugin can have its own middleware stack.

**Type:** `array[object]`
**Default:** Uses global middleware configuration
**Structure:**
```yaml
middleware_override:
  - name: "cached"        # Middleware name
    params:               # Parameters for middleware
      ttl: 600
  - name: "rate_limited"
    params:
      requests_per_minute: 120
```

**Supported Middleware Types:**
- `cached` - Response caching
- `rate_limited` - Rate limiting
- `retryable` - Retry logic
- `timed` - Execution timing

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/services/middleware.py`
- **Lines:** 65-74
- **Code:**
```python
def get_middleware_for_plugin(self, plugin_id: str) -> list[dict[str, Any]]:
    """Get middleware configuration for a specific plugin."""
    # Check for plugin-specific override
    plugins = self.config.get("plugins", [])
    for plugin in plugins:
        if plugin.get("plugin_id") == plugin_id:
            if "middleware_override" in plugin:
                self.logger.debug(f"Using middleware override for plugin {plugin_id}")
                return plugin["middleware_override"]

    # Return global config
    return self.get_global_config()
```

---

### Plugin Capabilities

#### capabilities

Array of capabilities that this plugin provides. Each capability can have its own configuration.

**Type:** `array[object]`
**Default:** `[]`
**Structure:**
```yaml
capabilities:
  - capability_id: "read_file"
    required_scopes: ["files:read"]
    enabled: true
  - capability_id: "write_file"
    required_scopes: ["files:write"]
    enabled: true
```

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/config/models.py`
- **Lines:** 74-81, 90
- **Code:**
```python
class PluginCapability(BaseModel):
    """Model for plugin capability configuration."""

    capability_id: str
    required_scopes: list[str] = []
    enabled: bool = True

class PluginConfig(BaseModel):
    """Model for individual plugin configuration."""
    # ...
    capabilities: list[PluginCapability] = []
```

##### capability_id

Unique identifier for the capability within the plugin.

**Type:** `string`
**Example:** `"read_file"`

##### required_scopes

Array of security scopes required to access this capability.

**Type:** `array[string]`
**Default:** `[]`
**Example:** `["files:read", "api:access"]`

##### enabled

Whether this specific capability is enabled.

**Type:** `boolean`
**Default:** `true`
**Example:** `false`

---

### Plugin-Specific Configuration

#### config

Free-form configuration object for plugin-specific settings. The structure depends on the individual plugin's requirements.

**Type:** `object`
**Default:** `{}`
**Example:**
```yaml
config:
  api_endpoint: "https://api.example.com"
  timeout: 30
  retries: 3
  custom_headers:
    User-Agent: "AgentUp/1.0"
```

**Implementation Note:**
The `config` section is passed directly to the plugin and is not processed by the core AgentUp framework. Each plugin defines its own configuration schema.

---

## Routing System Details

### Implicit Routing Logic

AgentUp determines routing mode implicitly based on plugin configuration:

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Lines:** 464-467
- **Code:**
```python
# Implicit routing: if keywords or patterns exist, direct routing is available
has_direct_routing = bool(keywords or patterns)
self.plugins[plugin_id] = {
    "has_direct_routing": has_direct_routing,
```

### Routing Decision Process

1. **Check for direct routing matches** (keywords/patterns) with priority
2. **If no direct match found**, use AI routing
3. **If multiple direct matches**, use highest priority plugin

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py`
- **Lines:** 439-448
- **Code:**
```python
def _determine_plugin_and_routing(self, user_input: str) -> tuple[str, str]:
    """Determine which plugin and routing mode to use for the user input.
    New implicit routing logic:
    1. Check for direct routing matches (keywords/patterns) with priority
    2. If no direct match found, use AI routing
    3. If multiple direct matches, use highest priority plugin
    """
```

---

## Validation

AgentUp includes validation for plugin configurations:

**Implementation Reference:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/cli/commands/validate.py`
- **Lines:** 141-147
- **Code:**
```python
def validate_plugins_config(config: dict[str, Any]) -> list[str]:
    """Validate plugins configuration."""
    errors = []
    plugins = config.get("plugins", [])

    if not isinstance(plugins, list):
        errors.append("plugins must be a list")
        return errors
```

---

## Complete Example

Here's a complete example showing all implemented plugin configuration options:

```yaml
plugins:
  - plugin_id: "advanced_tool"
    name: "Advanced Tool Plugin"
    description: "A comprehensive plugin demonstrating all configuration options"
    enabled: true

    # Direct routing configuration
    keywords: ["tool", "utility", "helper"]
    patterns: ["^run tool .*", "execute .*"]
    priority: 150

    # Override global middleware
    middleware_override:
      - name: "cached"
        params:
          ttl: 300
      - name: "rate_limited"
        params:
          requests_per_minute: 100
      - name: "timed"
        params: {}

    # Plugin capabilities with security scopes
    capabilities:
      - capability_id: "execute_command"
        required_scopes: ["system:write", "admin"]
        enabled: true
      - capability_id: "read_status"
        required_scopes: ["system:read"]
        enabled: true
      - capability_id: "advanced_feature"
        required_scopes: ["admin"]
        enabled: false

    # Plugin-specific configuration
    config:
      timeout: 60
      max_retries: 3
      api_endpoint: "https://api.example.com/v1"
      headers:
        User-Agent: "AgentUp-Plugin/1.0"
      feature_flags:
        experimental_mode: false
        debug_logging: true
```

---

## Summary

### Implemented Keys (Confirmed by Code Inspection)

 **plugin_id** - Required unique identifier
 **name** - Display name (defaults to plugin_id)
 **description** - Plugin description (defaults to empty)
 **enabled** - Enable/disable plugin (defaults to true)
 **keywords** - Keywords for direct routing (defaults to [])
 **patterns** - Regex patterns for direct routing (defaults to [])
 **priority** - Conflict resolution priority (defaults to 100)
 **middleware_override** - Plugin-specific middleware stack
 **capabilities** - Array of plugin capabilities with scopes
 **config** - Free-form plugin-specific configuration

### Not Implemented

L **routing_mode** - This is NOT a per-plugin setting. Routing is determined implicitly based on keywords/patterns presence.

All configuration options listed above have been verified through code inspection with file paths, line numbers, and code snippets provided as proof of implementation.