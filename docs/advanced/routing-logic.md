# AgentUp Routing Logic Analysis

This document provides a comprehensive analysis of the routing system in AgentUp, revealing significant discrepancies between the designed configuration system and the actual implementation.

## Executive Summary

**CRITICAL FINDING:** The root-level routing configuration system is **partially broken**. While configuration models exist and validation passes, the executor **ignores most routing configurations** and uses hardcoded behavior instead.

## Configuration Models vs. Implementation

### Expected Root-Level Routing Configuration

Based on the configuration models, AgentUp should support:

```yaml
routing:
  default_mode: "ai"           # Global default: "ai" or "direct"
  fallback_plugin: "echo"      # Plugin to use when no match found
  fallback_enabled: true       # Enable fallback behavior
```

**Model Definition:**
- **File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/config/models.py:66-71`
```python
class RoutingConfig(BaseModel):
    """Global routing configuration."""
    
    default_mode: str = "ai"  # "ai" or "direct"
    fallback_plugin: str | None = None  # Fallback plugin when no match
    fallback_enabled: bool = True  # Allow AI→Direct fallback
```

### Expected Per-Plugin Routing Configuration

Based on validation code and generator output, plugins should support:

```yaml
plugins:
  - plugin_id: "my_plugin"
    routing_mode: "direct"     # "ai" or "direct"
    keywords: ["file", "dir"]  # Keywords for direct routing
    patterns: ["^create .*"]   # Regex patterns for direct routing
    priority: 100              # Conflict resolution priority
```

## What Actually Works vs. What's Broken

| Configuration | Model Support | Validation | Generator | Executor | Status |
|---|---|---|---|---|---|
| `routing.default_mode` | ✅ | ✅ | ✅ | ❌ | **BROKEN** |
| `routing.fallback_plugin` | ✅ | ❌ | ❌ | ❌ | **BROKEN** |
| `routing.fallback_enabled` | ✅ | ❌ | ❌ | ❌ | **BROKEN** |
| `plugins[].routing_mode` | ❌ | ✅ | ✅ | ❌ | **BROKEN** |
| `plugins[].keywords` | ❌ | ✅ | ✅ | ✅ | **WORKS** |
| `plugins[].patterns` | ❌ | ✅ | ✅ | ✅ | **WORKS** |
| `plugins[].priority` | ❌ | ❌ | ✅ | ✅ | **WORKS** |

## Actual Implementation: Implicit Routing

The executor completely ignores routing configuration and uses **implicit routing logic**:

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:447-454`
```python
def __init__(self, agent: BaseAgent | AgentCard):
    # ...
    config = load_config()
    # Parse routing configuration (implicit routing based on keywords/patterns)
    self.fallback_plugin = "echo"  # ← HARDCODED!
    self.fallback_enabled = True   # ← HARDCODED!
```

### Implicit Routing Logic

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:464-474`
```python
keywords = plugin_data.get("keywords", [])
patterns = plugin_data.get("patterns", [])
# Implicit routing: if keywords or patterns exist, direct routing is available
has_direct_routing = bool(keywords or patterns)
self.plugins[plugin_id] = {
    "has_direct_routing": has_direct_routing,
    "keywords": keywords,
    "patterns": patterns,
    "priority": plugin_data.get("priority", 100),
}
```

## How Routing Actually Works (Current Implementation)

### 1. Plugin Registration

Each plugin is registered with implicit routing capabilities:

```python
# If plugin has keywords or patterns → direct routing available
# If plugin has no keywords/patterns → only AI routing available
has_direct_routing = bool(keywords or patterns)
```

### 2. Routing Decision Process

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:439-448**
```python
def _determine_plugin_and_routing(self, user_input: str) -> tuple[str, str]:
    """Determine which plugin and routing mode to use for the user input.
    New implicit routing logic:
    1. Check for direct routing matches (keywords/patterns) with priority
    2. If no direct match found, use AI routing
    3. If multiple direct matches, use highest priority plugin
    """
```

### 3. Keyword Matching

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:493-500**
```python
# Check keywords
for keyword in keywords:
    if keyword.lower() in user_input.lower():
        logger.debug(f"Matched keyword '{keyword}' for plugin '{plugin_id}'")
        direct_matches.append((plugin_id, plugin_config["priority"]))
        break
```

### 4. Pattern Matching

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:501-508**
```python
# Check patterns if no keyword match found for this plugin
if (plugin_id, plugin_config["priority"]) not in direct_matches:
    for pattern in patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            logger.debug(f"Matched pattern '{pattern}' for plugin '{plugin_id}'")
            direct_matches.append((plugin_id, plugin_config["priority"]))
            break
```

### 5. Priority Resolution

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:515-519**
```python
if direct_matches:
    # Sort by priority (highest first) then by plugin_id for determinism
    direct_matches.sort(key=lambda x: (-x[1], x[0]))
    selected_plugin = direct_matches[0][0]
    logger.info(f"Direct routing to plugin '{selected_plugin}' (priority: {direct_matches[0][1]})")
```

### 6. AI Routing Fallback

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/core/executor.py:521-523**
```python
# No direct routing match found, use AI routing
logger.info("No direct routing match found, using AI routing")
return None, "ai"
```

## Configuration Examples That Work vs. Don't Work

### ✅ What Currently Works

```yaml
plugins:
  - plugin_id: "file_manager"
    keywords: ["file", "directory", "ls"]     # ← Works: triggers direct routing
    patterns: ["^create file .*"]             # ← Works: regex matching
    priority: 150                             # ← Works: conflict resolution
```

### ❌ What's Broken (Silently Ignored)

```yaml
routing:
  default_mode: "direct"        # ← IGNORED: executor uses implicit logic
  fallback_plugin: "my_plugin"  # ← IGNORED: hardcoded to "echo"
  fallback_enabled: false       # ← IGNORED: always enabled

plugins:
  - plugin_id: "my_plugin"
    routing_mode: "ai"          # ← IGNORED: routing determined by keywords/patterns
```

## Validation vs. Reality Gap

### Validation Code Supports Configurations That Don't Work

The validation system checks configurations that are completely ignored:

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/cli/commands/validate.py:213-222**
```python
# Check if any plugin requires AI routing
default_mode = routing.get("default_mode", "ai")  # ← This value is never used!
needs_ai = False

for plugin in plugins:
    plugin_routing_mode = plugin.get("routing_mode", default_mode)  # ← Never used!
    if plugin_routing_mode == "ai":
        needs_ai = True
        break
```

### Generator Creates Unused Configurations

**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/src/agent/generator.py:639-648**
```python
return [
    {
        "plugin_id": "echo",
        "routing_mode": "direct",  # ← Generated but ignored by executor!
        "keywords": ["echo", "test", "ping"],
        "priority": 100,
    }
]
```

## Real-World Configuration Files

### Example 1: AgentUp Framework Config
**File:** `/Users/lhinds/dev/agentup-workspace/AgentUp/agentup.yml:11-13`
```yaml
routing:
  default_mode: direct      # ← This setting has NO effect!
  fallback_enabled: false   # ← This setting has NO effect!
```

### Example 2: RAG Agent Config
**File:** `/Users/lhinds/dev/agentup-workspace/agents/rag_agent/agentup.yml:68-69`
```yaml
routing:
  default_mode: ai          # ← This setting has NO effect!
```

## Impact Analysis

### For Users
1. **Silent Configuration Failures**: Users can set routing configurations that appear valid but have no effect
2. **Unpredictable Behavior**: Expected routing behavior doesn't match actual behavior
3. **Limited Control**: Cannot configure fallback plugins or disable fallback behavior

### For Developers
1. **Misleading Documentation**: Configuration docs describe features that don't work
2. **Validation False Positives**: Validation passes for broken configurations
3. **Technical Debt**: Large gap between intended and actual implementation

## Recommendations

### Immediate Fixes Required

1. **Update Documentation**: Clearly state which routing configurations are ignored
2. **Fix Executor Implementation**: Either implement the configuration system or remove unused models
3. **Update Validation**: Remove validation for configurations that aren't implemented
4. **Generator Cleanup**: Remove generation of unused routing_mode configurations

### Long-term Solutions

1. **Implement Full Routing Configuration**: Make executor read and respect routing settings
2. **Deprecation Path**: Provide clear migration path for users expecting configuration-based routing
3. **Integration Tests**: Add tests that verify configuration behavior matches implementation

## Current Working Routing Logic (Summary)

The actual routing system works as follows:

1. **Plugin has keywords/patterns** → Can use direct routing
2. **User input matches keyword** → Route directly to plugin (by priority)
3. **User input matches pattern** → Route directly to plugin (by priority)
4. **No matches found** → Use AI routing (LLM selects function)
5. **Direct routing fails** → Fallback to hardcoded "echo" plugin

**Key Point:** This is purely implicit routing based on content analysis, not explicit configuration-based routing as designed.