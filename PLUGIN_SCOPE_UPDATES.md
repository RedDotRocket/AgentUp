# Plugin Updates for SCOPE_DESIGN.md Implementation

This document summarizes the updates made to existing plugins to support the new scope-based security design specified in SCOPE_DESIGN.md.

## Summary of Changes

All plugins have been updated to follow the new **declarative plugin** pattern where:
- ✅ **Plugins DECLARE what scopes their capabilities need**
- ✅ **Plugins DO NOT enforce scopes themselves** 
- ✅ **Framework enforces what plugins declare**

## Updated Plugins

### 1. sys_tools Plugin (`/plugins/sys_tools/`)

**File**: `src/sys_tools/plugin.py`

**Capabilities Updated with Scopes**:
- `file_read` → requires `["files:read"]`
- `file_write` → requires `["files:write"]`
- `file_exists` → requires `["files:read"]`
- `file_info` → requires `["files:read"]`
- `list_directory` → requires `["files:read"]`
- `create_directory` → requires `["files:write"]`
- `delete_file` → requires `["files:admin"]`
- `system_info` → requires `["system:read"]`
- `working_directory` → requires `["system:read"]`
- `execute_command` → requires `["system:admin"]`
- `file_hash` → requires `["files:read"]`

**Changes Made**:
- Added `required_scopes` field to each capability in `CAPABILITIES_CONFIG`
- Updated `_create_capability_info()` to include `required_scopes` parameter
- Updated `register_capability()` to return `list[CapabilityInfo]`

### 2. scopecheck Plugin (`/plugins/scopecheck/`)

**File**: `src/scopecheck/plugin.py`

**Capabilities Updated with Scopes**:
- `scopecheck` → requires `["debug:scope"]`

**Changes Made**:
- Added `required_scopes: ["debug:scope"]` to CapabilityInfo
- Updated `register_capability()` to return `list[CapabilityInfo]`
- Added `plugin_name="scopecheck"` field

### 3. brave Plugin (`/plugins/brave/`)

**File**: `src/brave/plugin.py`

**Capabilities Updated with Scopes**:
- `web_search` → requires `["web:search"]`

**Changes Made**:
- Added `required_scopes: ["web:search"]` to CapabilityInfo
- Updated `register_capability()` to return `list[CapabilityInfo]`
- Added `plugin_name="brave"` field

### 4. image_vision Plugin (`/plugins/image_vision/`)

**File**: `src/image_vision/plugin.py`

**Capabilities Updated with Scopes**:
- `analyze_image` → requires `["image:read"]`
- `transform_image` → requires `["image:write"]`

**Changes Made**:
- Added `required_scopes` field to each capability in `CAPABILITIES_CONFIG`
- Updated `_create_capability_info()` to include `required_scopes` parameter
- Plugin already returned `list[CapabilityInfo]`

## Framework Integration

The AgentUp framework now includes:

### New Registration Functions
- `register_plugin_capability(plugin_config)` - Framework scope enforcement wrapper
- `register_mcp_tool_as_capability(tool_name, mcp_client, tool_scopes)` - MCP tools as capabilities

### Scope Enforcement
- Framework automatically wraps all plugin capabilities with scope checking
- Comprehensive audit logging for all capability access
- Generic error messages to prevent scope information leakage
- AI tool filtering based on user scopes

### Configuration Support
- Per-capability scope requirements in agent_config.yaml
- MCP tool scope enforcement via `tool_scopes` configuration
- Complete scope hierarchy with parent-child relationships

## Example Configuration

See `agent_config_scope_example.yaml` for a complete example showing:
- Individual capability scope requirements
- MCP tool scope enforcement
- Hierarchical scope definitions
- Multiple user roles with different scope levels

## Security Benefits

1. **Framework Enforcement**: Plugins cannot bypass security checks
2. **Declarative Security**: All scope requirements visible in configuration
3. **Granular Permissions**: Individual capabilities can have different scope requirements
4. **Audit Trail**: All capability access logged with user context
5. **AI Transparency**: AI only sees tools the user can actually use
6. **MCP Integration**: External tools follow same security model

## Backward Compatibility

- Plugins without `required_scopes` will have no scope requirements (open access)
- Existing plugin interfaces remain compatible
- Legacy configuration formats continue to work

## Next Steps

1. **Test the updated plugins** with the new scope enforcement
2. **Update plugin documentation** to explain scope requirements
3. **Create additional example configurations** for different use cases
4. **Consider adding scope validation** to plugin development tools

The implementation fully aligns with SCOPE_DESIGN.md and provides a comprehensive, config-driven security system while maintaining plugin simplicity and clear separation of concerns.