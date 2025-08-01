# AgentUp Decorator-Based Plugin System Implementation

## Executive Summary

This document comprehensively details the implementation of a new decorator-based plugin system for AgentUp, replacing the previous Pluggy-based hook system. The new system provides a more intuitive, secure, and maintainable approach to plugin development while maintaining full backward compatibility with PyPI distribution.

## Table of Contents

1. [Background and Rationale](#background-and-rationale)
2. [Design Philosophy](#design-philosophy)
3. [Implementation Overview](#implementation-overview)
4. [Files Modified and Added](#files-modified-and-added)
5. [Key Components](#key-components)
6. [Security Enhancements](#security-enhancements)
7. [Migration Guide](#migration-guide)
8. [Technical Details](#technical-details)

## Background and Rationale

### Problem Statement

The original Pluggy-based plugin system presented several challenges:

1. **Complexity**: Developers had to understand 11 different hooks (`register_capability`, `can_handle_task`, `execute_capability`, etc.)
2. **Unclear Declaration**: Plugin attributes and capabilities were declared across multiple methods, making it difficult to understand plugin structure
3. **Security Concerns**: Any Python application could inject into AgentUp's plugin namespace
4. **Developer Experience**: The hook-based approach was not intuitive for new developers

### Solution: Decorator-Based System

The new system replaces Pluggy hooks with a simple `@capability` decorator that:
- Automatically generates all necessary plugin metadata
- Provides clear, single-location capability declaration
- Maintains PyPI distribution compatibility
- Adds comprehensive security through trusted publishing verification

## Design Philosophy

### Core Principles

1. **Simplicity First**: One decorator replaces 11 hooks
2. **Security by Default**: Plugins must be explicitly allowed and can be cryptographically verified
3. **Developer Friendly**: Clear, intuitive API that follows Python conventions
4. **Backward Compatible**: Maintains PyPI distribution and installation mechanisms
5. **Type-Safe**: Full typing support with Pydantic models

### Key Design Decisions

- **No Backward Compatibility with Pluggy**: Clean break to avoid complexity (per user request)
- **Entry Point Discovery**: Continue using Python entry points for plugin discovery
- **Decorator Metadata**: All capability information stored as function attributes
- **Direct Method Dispatch**: Replace hook indirection with direct method calls

## Implementation Overview

### Before (Pluggy-based)
```python
class ExamplePlugin:
    @hookimpl
    def register_capability(self):
        return CapabilityDefinition(...)
    
    @hookimpl
    def can_handle_task(self, capability_id, task):
        if capability_id == "example":
            return True
        return False
    
    @hookimpl
    def execute_capability(self, capability_id, task):
        if capability_id == "example":
            return "Result"
    
    # ... 8 more hooks
```

### After (Decorator-based)
```python
class ExamplePlugin(Plugin):
    @capability(
        "example",
        name="Example Capability",
        description="A simple example",
        scopes=["api:read"],
        ai_function=True
    )
    async def handle_example(self, context: CapabilityContext) -> str:
        return "Result"
```

## Files Modified and Added

### New Core Files

#### 1. `/src/agent/plugins/base.py`
- **Purpose**: Base Plugin class with automatic capability discovery
- **Key Features**:
  - `_discover_capabilities()`: Automatically finds `@capability` decorated methods
  - `execute_capability()`: Unified execution interface
  - Lifecycle hooks (optional): `on_install()`, `on_uninstall()`, etc.
  - Service and configuration management

#### 2. `/src/agent/plugins/decorators.py`
- **Purpose**: Core decorator implementation
- **Key Components**:
  - `@capability` decorator: Main decorator for marking plugin methods
  - `@ai_function` decorator: Convenience decorator for AI-callable functions
  - `CapabilityMetadata` dataclass: Stores all capability information
  - Validation functions for metadata

#### 3. `/src/agent/plugins/new_manager.py`
- **Purpose**: Replaces Pluggy's PluginManager
- **Key Features**:
  - `PluginRegistry`: Central registry for all plugins
  - Entry point discovery without Pluggy
  - Direct plugin instantiation and management
  - Security allowlist enforcement

#### 4. `/src/agent/plugins/new_integration.py`
- **Purpose**: Integration layer with existing AgentUp systems
- **Key Functions**:
  - `integrate_plugins_with_capabilities()`: Connects plugins to capability system
  - `enable_plugin_system()`: Startup initialization
  - Wrapper creation for Task/CapabilityContext conversion

### Security Enhancement Files

#### 5. `/src/agent/plugins/trusted_publishing.py`
- **Purpose**: PyPI trusted publishing verification
- **Features**:
  - OIDC token verification from GitHub Actions
  - Attestation validation
  - Publisher trust level management
  - Caching for performance

#### 6. `/src/agent/plugins/trusted_registry.py`
- **Purpose**: Enhanced plugin registry with trust verification
- **Features**:
  - Automatic trust verification on plugin discovery
  - Trust-based filtering
  - Publisher management API

#### 7. `/src/agent/plugins/trust_manager.py`
- **Purpose**: Comprehensive publisher trust management
- **Features**:
  - Publisher reputation tracking
  - Trust policy enforcement
  - Revocation management
  - Historical event tracking

#### 8. `/src/agent/plugins/security.py`
- **Purpose**: Basic security controls
- **Features**:
  - Plugin allowlisting
  - Package validation
  - File integrity checking

### Modified Existing Files

#### 9. `/src/agent/cli/commands/plugin.py` (Updated)
- **Changes**: Updated to use new PluginRegistry
- **Key Updates**:
  - Fixed entry point generation
  - Added package field handling
  - Updated to use decorator system

#### 10. `/src/agent/config/model.py` (Updated)
- **Changes**: Added `package` field to PluginConfig
- **Purpose**: Support explicit package name specification

#### 11. `/src/agent/services/plugins.py` (Updated)
- **Changes**: Updated to use new PluginRegistry instead of legacy system
- **Key Updates**:
  - Replaced `enable_plugin_system()` with new registry
  - Created capability wrappers for Task interface
  - Added proper CapabilityMetadata integration

#### 12. `/src/agent/api/routes.py` (Updated)
- **Changes**: Updated to pull plugin info from new system
- **Key Updates**:
  - Try new registry first, fallback to config
  - Fixed AgentSkill validation errors

#### 13. `/src/agent/templates/plugins/pyproject.toml.j2` (Updated)
- **Changes**: 
  - Fixed entry point from `agentup.capabilities` to `agentup.plugins`
  - Removed pluggy dependency

#### 14. `/src/agent/templates/plugins/plugin.py.j2` (Updated)
- **Changes**: Updated to use decorator-based approach
- **Key Updates**:
  - Import from new base class
  - Use `@capability` decorator
  - Remove Pluggy hookimpl

### Documentation Updates

All documentation in `/docs/plugin-development/` was updated to reflect the new system:
- Removed references to Pluggy hooks
- Added decorator examples
- Updated security documentation
- Added trusted publishing guide

## Key Components

### 1. The @capability Decorator

```python
@capability(
    id: str,                    # Unique capability identifier
    name: str = None,          # Human-readable name
    description: str = None,   # Capability description
    scopes: list[str] = None,  # Required permissions
    ai_function: bool = False, # Can be called by AI
    ai_parameters: dict = None,# JSON schema for AI
    tags: list[str] = None,    # Discovery tags
    priority: int = 50,        # Routing priority
    # ... more options
)
```

### 2. Plugin Base Class

The `Plugin` base class provides:
- Automatic capability discovery
- Service configuration
- State management
- Lifecycle hooks
- Health monitoring

### 3. PluginRegistry

Replaces Pluggy's PluginManager with:
- Direct plugin loading via entry points
- Security allowlist enforcement
- Capability registration
- Plugin lifecycle management

### 4. Capability Execution Flow

```
User Request → PluginService → PluginRegistry → Plugin.execute_capability() → @capability method
```

## Security Enhancements

### 1. Namespace Protection

- **Allowlist System**: Only explicitly configured plugins are loaded
- **Package Verification**: Ensures package names match expectations
- **Entry Point Validation**: Verifies plugins come from expected packages

### 2. Trusted Publishing

- **OIDC Verification**: Validates GitHub Actions attestations
- **Publisher Trust Levels**: Official, Community, Unknown
- **Cryptographic Attestations**: Verifies build provenance

### 3. Trust Management

- **Publisher Registration**: Manage trusted publishers
- **Reputation System**: Track publisher behavior
- **Revocation Support**: Remove trust for compromised publishers

## Migration Guide

### For Plugin Developers

1. **Update Base Class**:
   ```python
   # Old
   class MyPlugin:
       
   # New
   from agent.plugins.base import Plugin
   class MyPlugin(Plugin):
   ```

2. **Replace Hooks with Decorators**:
   ```python
   # Old: Multiple hooks
   @hookimpl
   def register_capability(self):
       return CapabilityDefinition(...)
   
   # New: Single decorator
   @capability("my_cap", scopes=["api:read"])
   async def my_capability(self, context):
       return "result"
   ```

3. **Update Entry Points**:
   ```toml
   # pyproject.toml
   [project.entry-points."agentup.plugins"]
   my_plugin = "my_plugin.plugin:MyPlugin"
   ```

### For AgentUp Users

1. **Configuration remains the same**:
   ```yaml
   plugins:
     - plugin_id: my_plugin
       capabilities:
         - capability_id: my_cap
           required_scopes: ["api:read"]
   ```

2. **New security options**:
   ```yaml
   trusted_publishing:
     require_trusted_publishing: true
     minimum_trust_level: community
   ```

## Technical Details

### Entry Point Discovery

The system continues to use Python entry points but without Pluggy:

```python
# PluginRegistry._load_entry_point_plugins()
entry_points = importlib.metadata.entry_points()
plugin_entries = entry_points.select(group="agentup.plugins")

for entry_point in plugin_entries:
    plugin_class = entry_point.load()
    plugin_instance = plugin_class()
    self._register_plugin(entry_point.name, plugin_instance)
```

### Capability Auto-Discovery

The Plugin base class automatically finds decorated methods:

```python
def _discover_capabilities(self):
    for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
        capabilities = get_capability_metadata(method)
        for capability_meta in capabilities:
            self._capabilities[capability_meta.id] = capability_meta
```

### Task Interface Adaptation

The system adapts between the old Task interface and new CapabilityContext:

```python
def create_capability_wrapper(plugin_inst, cap_id):
    async def capability_wrapper(task) -> str:
        # Convert Task to CapabilityContext
        context = CapabilityContext(
            task=task,
            config={},
            services={},
            state={}
        )
        # Execute plugin method
        result = await plugin_inst.execute_capability(cap_id, context)
        return result.content
    return capability_wrapper
```

### Security Allowlist Logic

```python
# Fixed allowlist handling with package field
plugin_config = config.get("plugins", [])
for plugin in plugin_config:
    package = plugin.get("package")
    if package is None:
        package = f"agentup-{plugin_id}-plugin"
    
    self.allowed_plugins[plugin_id] = {
        "package": package,
        "verified": plugin.get("verified", False)
    }
```

## Benefits Achieved

1. **Simplified Development**: One decorator instead of 11 hooks
2. **Better Security**: Namespace protection and trusted publishing
3. **Improved Discovery**: Clear capability declaration in one place
4. **Type Safety**: Full typing with Pydantic models
5. **Performance**: Direct method dispatch instead of hook indirection
6. **Maintainability**: Cleaner codebase without Pluggy complexity

## Future Enhancements

1. **Runtime Capability Modification**: Allow plugins to add/remove capabilities dynamically
2. **Advanced Trust Policies**: More sophisticated trust evaluation
3. **Plugin Marketplace**: Integration with a curated plugin registry
4. **Automated Security Scanning**: Integration with security tools
5. **Performance Monitoring**: Built-in capability performance tracking

## Conclusion

The new decorator-based plugin system successfully addresses all the pain points of the Pluggy-based system while adding significant security enhancements. The implementation maintains full backward compatibility with PyPI distribution while providing a much more intuitive developer experience.

The system is now:
- **Easier to understand**: Clear, declarative syntax
- **More secure**: Multiple layers of protection
- **More maintainable**: Less complexity, better organization
- **More powerful**: Richer capability metadata and features

This represents a significant improvement in AgentUp's plugin architecture, setting a strong foundation for future growth and community contributions.