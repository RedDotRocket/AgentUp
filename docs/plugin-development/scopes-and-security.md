# Plugin Security and Scopes Guide

!!! warning
    Development is moving fast, and this document may not reflect the latest changes. Once updated, we will remove this warning.

This guide provides comprehensive information for plugin maintainers on implementing security, authentication
scopes, and authorization in AgentUp plugins.

> **Note**: The security system in AgentUp is currently under development. Some of the security features described
> in this document represent planned functionality and may not be fully implemented in the current version.
> The plugin system currently focuses on basic capability registration and execution.

## Overview

AgentUp uses scope-based authentication and context-aware middleware. Plugins must define their
security requirements and implement proper authorization checks to ensure secure operation.

## Table of Contents

1. [Authentication Scopes](#authentication-scopes)
2. [Security Context](#security-context)
3. [Implementing Security in Plugins](#implementing-security-in-plugins)
4. [Scope Hierarchy](#scope-hierarchy)
5. [Best Practices](#best-practices)
6. [Examples](#examples)
7. [Migration Guide](#migration-guide)

---

## Authentication Scopes

### What are Scopes?

Scopes are permission strings that define what operations a user is authorized to perform. They
follow a hierarchical structure and support inheritance.

### Scope Naming Convention

```
<domain>:<action>[:<resource>]
```

**Examples:**
- `files:read` - Permission to read files
- `files:write` - Permission to write files
- `files:sensitive` - Permission to access sensitive files
- `system:read` - Permission to read system information
- `api:external` - Permission to call external APIs
- `admin` - Administrative access (inherits all permissions)

### Standard Scope Domains

| Domain | Description | Example Scopes |
|--------|-------------|----------------|
| `files` | File system operations | `files:read`, `files:write`, `files:sensitive` |
| `system` | System information and control | `system:read`, `system:write`, `system:admin` |
| `network` | Network operations | `network:access`, `network:admin` |
| `api` | External API access | `api:external`, `api:restricted` |
| `data` | Data processing operations | `data:read`, `data:process`, `data:export` |
| `ai` | AI model operations | `ai:execute`, `ai:train`, `ai:admin` |
| `admin` | Administrative functions | `admin` (grants all permissions) |

---

## Plugin Classification

### Plugin Characteristics

```python
class PluginCharacteristics:
    plugin_type: PluginType
    network_dependent: bool = False
    cacheable: bool = True
    cache_ttl: Optional[int] = None
    retry_suitable: bool = False
    rate_limit_required: bool = True
    auth_scopes: List[str] = []
    performance_critical: bool = False
```

---

## Security Context

### Capability Context

The `CapabilityContext` provides plugins with comprehensive security information:

```python
class CapabilityContext:
    # Core fields
    task: Task
    config: dict[str, Any]
    services: dict[str, Any]
    state: dict[str, Any]
    metadata: dict[str, Any]

    # Note: Security features like auth, user_scopes, etc. are available
    # through the AgentUp security system and middleware
```

### Using Security Context

```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    # Check basic authentication
    if not context.auth:
        raise UnauthorizedError("Authentication required")

    # Check specific scope
    context.require_scope("files:read")

    # Access user information
    user_id = context.get_user_id()
    user_scopes = context.user_scopes

    # Conditional logic based on permissions
    if context.has_scope("files:sensitive"):
        # Allow access to sensitive files
        pass
    else:
        # Restrict to public files only
        pass

    return CapabilityResult(
        content=f"Operation completed for user: {user_id}",
        success=True
    )
```

---

## Implementing Security in Plugins

### Available and Planned Hook Methods

> **Implementation Status**: The methods below show the planned security architecture. Currently, only basic plugin registration and execution hooks are implemented. Advanced security features are planned for future releases.

#### Currently Available Hooks

These hooks are currently implemented and available for use:

```python
@hookimpl
def register_capability(self) -> PluginDefinition:
    """Register the capability with AgentUp (AVAILABLE)."""
    return PluginDefinition(
        id="my_capability",
        name="My Capability",
        version="1.0.0",
        description="My capability description",
        capabilities=[CapabilityType.TEXT],
        required_scopes=["api:read"],  # Basic scope definition
    )

@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    """Execute the capability (AVAILABLE)."""
    # Basic security can be implemented here manually
    return CapabilityResult(content="Result", success=True)

@hookimpl
def can_handle_task(self, context: CapabilityContext) -> bool | float:
    """Check if capability can handle task (AVAILABLE)."""
    return 0.8

@hookimpl
def get_ai_functions(self) -> list[AIFunction]:
    """Get AI functions for LLM integration (AVAILABLE)."""
    return []
```

#### Planned Security Hooks

The following hooks represent the planned security architecture:

#### 1. Plugin Characteristics (Planned)

```python
@hookimpl
def get_plugin_characteristics(self) -> PluginCharacteristics:
    """Define plugin operational characteristics."""
    return PluginCharacteristics(
        plugin_type=PluginType.LOCAL,  # or NETWORK, HYBRID, AI_FUNCTION, CORE
        network_dependent=False,
        cacheable=True,
        cache_ttl=300,
        retry_suitable=False,
        rate_limit_required=False,
        auth_scopes=["your_domain:read"],
        performance_critical=False
    )
```

#### 2. Required Scopes (Planned)

```python
@hookimpl
def get_required_scopes(self, capability_id: str) -> list[str]:
    """Define required scopes per capability."""
    scope_map = {
        "read_file": ["files:read"],
        "write_file": ["files:write"],
        "delete_file": ["files:write", "files:admin"],
        "read_sensitive": ["files:read", "files:sensitive"],
    }
    return scope_map.get(capability_id, ["default:access"])
```

#### 3. Custom Authorization (Planned)

```python
@hookimpl
def validate_access(self, context: CapabilityContext) -> bool:
    """Custom authorization logic beyond scope checking."""

    # Example: Time-based access control
    import datetime
    current_hour = datetime.datetime.now().hour
    if 22 <= current_hour or current_hour <= 6:  # 10 PM to 6 AM
        if not context.has_scope("system:24hour"):
            return False

    # Example: User attribute-based access
    if context.auth.metadata.get("user_type") == "restricted":
        restricted_capabilities = ["basic_read", "basic_write"]
        return context.metadata.get("capability_id") in restricted_capabilities

    # Example: Rate limiting based on user tier
    user_tier = context.auth.metadata.get("tier", "basic")
    if user_tier == "basic" and context.metadata.get("operation_complexity") == "high":
        return False

    return True
```

#### 4. Middleware Preferences (Planned)

```python
@hookimpl
def get_middleware_preferences(self, capability_id: str) -> dict[str, Any]:
    """Define preferred middleware configuration."""

    # Different preferences per capability
    if capability_id == "cpu_info":
        return {
            "cached": {
                "enabled": True,
                "ttl": 60,  # CPU info changes frequently
                "key_strategy": "global"  # Same for all users
            },
            "rate_limited": {
                "enabled": False,
                "reason": "Local system call, very fast"
            }
        }

    elif capability_id == "external_api_call":
        return {
            "cached": {
                "enabled": True,
                "ttl": 1800,  # 30 minutes
                "key_strategy": "user_aware"  # Different per user
            },
            "rate_limited": {
                "enabled": True,
                "requests_per_minute": 20,
                "reason": "Respect external API limits"
            },
            "retryable": {
                "enabled": True,
                "max_attempts": 3,
                "backoff_factor": 2.0
            }
        }

    return {}  # Use defaults
```

### Current Security Implementation Approach

Since the advanced security hooks are not yet implemented, plugins can implement basic security manually in their `execute_capability` method:

```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    """Execute capability with basic security checks."""

    try:
        # Basic validation using available context fields
        # Note: Advanced auth fields may not be available yet

        # 1. Check if this is a sensitive operation
        operation = context.metadata.get("operation", "")
        if operation in ["admin", "delete", "sensitive"]:
            # Implement your own auth checks here
            # This is plugin-specific until framework auth is available
            if not self._check_admin_permission(context):
                return CapabilityResult(
                    content="Access denied: insufficient permissions",
                    success=False,
                    error="PERMISSION_DENIED"
                )

        # 2. Execute the actual operation
        result = self._execute_operation(context)

        # 3. Add metadata for audit purposes
        result.metadata.update({
            "executed_at": datetime.utcnow().isoformat(),
            "operation": operation,
        })

        return result

    except Exception as e:
        return CapabilityResult(
            content=f"Operation failed: {str(e)}",
            success=False,
            error=str(e)
        )

def _check_admin_permission(self, context: CapabilityContext) -> bool:
    """Plugin-specific permission check until framework auth is available."""
    # Implement your security logic here
    # This could check API keys, user roles, etc.
    return True  # Placeholder

def _execute_operation(self, context: CapabilityContext) -> CapabilityResult:
    """Execute the actual capability operation."""
    return CapabilityResult(content="Operation completed", success=True)

def _log_access(self, context: CapabilityContext):
    """Log successful access for audit trail."""
    logger.info(
        "Capability access granted",
        user_id=context.get_user_id(),
        capability_id=context.metadata.get("capability_id"),
        scopes=context.user_scopes,
        request_id=context.request_id
    )

def _log_security_violation(self, context: CapabilityContext, error: str):
    """Log security violations for monitoring."""
    logger.warning(
        "Security violation detected",
        user_id=context.get_user_id(),
        capability_id=context.metadata.get("capability_id"),
        error=error,
        request_id=context.request_id
    )
```

---

## Scope Hierarchy

### Hierarchical Permissions

Scopes support inheritance where higher-level scopes automatically grant lower-level permissions:

```python
scope_hierarchy = {
    "admin": ["*"],  # Admin has all permissions
    "files:admin": ["files:write", "files:read", "files:sensitive"],
    "files:write": ["files:read"],
    "system:admin": ["system:write", "system:read"],
    "system:write": ["system:read"],
    "api:admin": ["api:external", "api:restricted"],
}
```

### Scope Validation

```python
def validate_scope_hierarchy(user_scopes: list[str], required_scope: str) -> bool:
    """Check if user has required scope including hierarchy."""

    # Direct scope match
    if required_scope in user_scopes:
        return True

    # Admin override
    if "admin" in user_scopes:
        return True

    # Check hierarchy
    for user_scope in user_scopes:
        if user_scope in scope_hierarchy:
            inherited_scopes = scope_hierarchy[user_scope]
            if required_scope in inherited_scopes or "*" in inherited_scopes:
                return True

    return False
```

### Custom Scope Hierarchies

Plugins can define their own scope hierarchies:

```python
@hookimpl
def get_scope_hierarchy(self) -> dict[str, list[str]]:
    """Define custom scope hierarchy for this plugin."""
    return {
        "myapp:admin": ["myapp:write", "myapp:read", "myapp:config"],
        "myapp:write": ["myapp:read"],
        "myapp:poweruser": ["myapp:advanced", "myapp:read"],
    }
```

---

## Best Practices

### 1. Principle of Least Privilege

Always request the minimum scopes necessary for your plugin to function:

```python
# ✓ Good: Specific scopes
@hookimpl
def get_required_scopes(self, capability_id: str) -> list[str]:
    return {
        "read_config": ["config:read"],
        "update_config": ["config:write"],
        "backup_config": ["config:read", "files:write"]
    }.get(capability_id, [])

# ✗ Bad: Overly broad scopes
@hookimpl
def get_required_scopes(self, capability_id: str) -> list[str]:
    return ["admin"]  # Too broad for most operations
```

### 2. Scope Granularity

Design scopes that are neither too broad nor too narrow:

```python
# ✓ Good: Appropriate granularity
"files:read"      # Read any file
"files:write"     # Write any file
"files:sensitive" # Access sensitive files

# ✗ Too broad
"files:all"       # Unclear what this includes

# ✗ Too narrow
"files:read:config"        # Too specific
"files:read:logs"          # Creates too many scopes
"files:read:user_data"     # Hard to manage
```

### 3. Security Context Usage

Always validate security context before performing operations:

```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    # ✓ Good: Comprehensive security checks
    if not context.auth:
        raise UnauthorizedError("Authentication required")

    context.require_scope("files:read")

    if sensitive_operation:
        context.require_scope("files:sensitive")

    # ✗ Bad: No security validation
    # Just execute without checking permissions
```

### 4. Error Handling

Provide clear, secure error messages:

```python
try:
    context.require_scope("files:admin")
    # ... perform operation
except ForbiddenError:
    # ✓ Good: Clear but not revealing
    return CapabilityResult(
        content="Permission denied: insufficient privileges",
        success=False,
        error="PERMISSION_DENIED"
    )

# ✗ Bad: Reveals internal information
except ForbiddenError:
    return CapabilityResult(
        content="Access denied: user lacks files:admin scope for /etc/passwd",
        success=False
    )
```

### 5. Audit Logging

Implement comprehensive audit logging:

```python
def _log_operation(self, context: EnhancedCapabilityContext, operation: str, result: str):
    """Log operations for audit trail."""
    logger.info(
        "Plugin operation completed",
        extra={
            "user_id": context.get_user_id(),
            "plugin_name": self.__class__.__name__,
            "operation": operation,
            "result": result,
            "scopes": context.user_scopes,
            "request_id": context.request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

---

## Examples

### Example 1: Current File System Plugin Implementation

```python
class FileSystemPlugin:
    """Plugin for file system operations with current security approach."""

    @hookimpl
    def register_capability(self) -> PluginDefinition:
        """Register file system capability."""
        return PluginDefinition(
            id="file_system",
            name="File System Operations",
            version="1.0.0",
            description="Read and write files with security checks",
            capabilities=[CapabilityType.TEXT],
            required_scopes=["files:read", "files:write"],  # Basic scope definition
        )

    @hookimpl
    def can_handle_task(self, context: CapabilityContext) -> float:
        """Check if this capability can handle file operations."""
        # Simple keyword-based routing for now
        if hasattr(context.task, 'history') and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, 'parts') and last_msg.parts:
                content = last_msg.parts[0].text if hasattr(last_msg.parts[0], 'text') else ""
                if any(word in content.lower() for word in ['file', 'read', 'write', 'save']):
                    return 0.8
        return 0.0

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute file operations with current security approach."""
        try:
            # Basic security checks using available context
            operation = context.metadata.get("operation", "")
            file_path = context.metadata.get("file_path", "")

            # Manual security validation since advanced auth hooks not available
            if not self._validate_file_access(file_path, operation):
                return CapabilityResult(
                    content="Access denied: insufficient file permissions",
                    success=False,
                    error="PERMISSION_DENIED"
                )

            if operation == "read_file":
                return self._read_file(context, file_path)
            elif operation == "write_file":
                return self._write_file(context, file_path)
            else:
                return CapabilityResult(
                    content="Unknown file operation",
                    success=False,
                    error="INVALID_OPERATION"
                )

        except Exception as e:
            return CapabilityResult(
                content=f"File operation failed: {str(e)}",
                success=False,
                error=str(e)
            )

    def _validate_file_access(self, file_path: str, operation: str) -> bool:
        """Manual file access validation."""
        # Restrict access to system files
        if file_path.startswith(("/etc/", "/sys/", "/proc/")):
            return False  # Would check admin permissions when available

        # Restrict access to sensitive directories
        sensitive_dirs = ["/home/", "/Users/", "/.ssh/"]
        if any(file_path.startswith(d) for d in sensitive_dirs):
            return False  # Would check sensitive file permissions when available

        return True

    def _read_file(self, context: CapabilityContext, file_path: str) -> CapabilityResult:
        """Read file with basic error handling."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            return CapabilityResult(
                content=content,
                success=True,
                metadata={
                    "file_path": file_path,
                    "operation": "read_file",
                    "size": len(content),
                    "executed_at": datetime.utcnow().isoformat()
                }
            )
        except FileNotFoundError:
            return CapabilityResult(
                content="File not found",
                success=False,
                error="FILE_NOT_FOUND"
            )
        except PermissionError:
            return CapabilityResult(
                content="Permission denied",
                success=False,
                error="PERMISSION_DENIED"
            )

    def _write_file(self, context: CapabilityContext, file_path: str) -> CapabilityResult:
        """Write file with basic error handling."""
        content_to_write = context.metadata.get("content", "")
        try:
            with open(file_path, 'w') as f:
                f.write(content_to_write)

            return CapabilityResult(
                content=f"Successfully wrote {len(content_to_write)} characters to {file_path}",
                success=True,
                metadata={
                    "file_path": file_path,
                    "operation": "write_file",
                    "bytes_written": len(content_to_write),
                    "executed_at": datetime.utcnow().isoformat()
                }
            )
        except PermissionError:
            return CapabilityResult(
                content="Permission denied",
                success=False,
                error="PERMISSION_DENIED"
            )
```

### Example 2: Current External API Plugin Implementation

```python
class WeatherAPIPlugin:
    """Plugin for weather API with current implementation approach."""

    @hookimpl
    def register_capability(self) -> PluginDefinition:
        """Register weather API capability."""
        return PluginDefinition(
            id="weather_api",
            name="Weather API",
            version="1.0.0",
            description="Get weather information from external APIs",
            capabilities=[CapabilityType.TEXT, CapabilityType.AI_FUNCTION],
            required_scopes=["api:external", "weather:read"],
        )

    @hookimpl
    def can_handle_task(self, context: CapabilityContext) -> float:
        """Check if this capability can handle weather requests."""
        if hasattr(context.task, 'history') and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, 'parts') and last_msg.parts:
                content = last_msg.parts[0].text if hasattr(last_msg.parts[0], 'text') else ""
                if any(word in content.lower() for word in ['weather', 'temperature', 'forecast', 'rain']):
                    return 0.9
        return 0.0

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute weather API operations with current security approach."""
        try:
            operation = context.metadata.get("operation", "get_weather")
            location = context.metadata.get("location", "")

            # Basic validation
            if not location:
                return CapabilityResult(
                    content="Location is required for weather queries",
                    success=False,
                    error="MISSING_LOCATION"
                )

            # Manual rate limiting check (would be framework-handled in future)
            if not self._check_rate_limit():
                return CapabilityResult(
                    content="Rate limit exceeded. Please try again later.",
                    success=False,
                    error="RATE_LIMIT_EXCEEDED"
                )

            # Execute weather API call
            weather_data = self._get_weather_data(location)

            return CapabilityResult(
                content=f"Weather in {location}: {weather_data}",
                success=True,
                metadata={
                    "operation": operation,
                    "location": location,
                    "executed_at": datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            return CapabilityResult(
                content=f"Weather API error: {str(e)}",
                success=False,
                error=str(e)
            )

    def _check_rate_limit(self) -> bool:
        """Basic rate limiting check."""
        # Plugin-specific rate limiting until framework support
        return True  # Placeholder

    def _get_weather_data(self, location: str) -> str:
        """Get weather data from external API."""
        # Actual API implementation would go here
        return f"Sunny, 22°C"  # Placeholder
```

---

## Migration Guide

### Migrating from Legacy Plugins

#### Step 1: Add Security Hooks

Add the required security hook methods to your existing plugin:

```python
# Add to existing plugin class
@hookimpl
def get_plugin_characteristics(self) -> PluginCharacteristics:
    # Define characteristics based on your plugin's behavior
    return PluginCharacteristics(
        plugin_type=PluginType.LOCAL,  # or appropriate type
        # ... other characteristics
    )

@hookimpl
def get_required_scopes(self, capability_id: str) -> list[str]:
    # Define minimum required scopes
    return ["default:access"]  # Start minimal, refine later
```

#### Step 2: Update Capability Execution

Update your execute method to use the enhanced context:

```python
# Before (legacy)
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    # No security validation
    return self._do_operation(context)

# After (enhanced)
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    # Add security validation
    if not context.auth:
        raise UnauthorizedError("Authentication required")

    # Your existing operation
    return self._do_operation(context)
```

#### Step 3: Gradual Security Enhancement

Start with minimal security and gradually enhance:

```python
# Phase 1: Basic authentication check
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    if not context.auth:
        raise UnauthorizedError("Authentication required")
    return self._do_operation(context)

# Phase 2: Add scope checking
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    if not context.auth:
        raise UnauthorizedError("Authentication required")
    context.require_scope("your_domain:read")
    return self._do_operation(context)

# Phase 3: Add custom authorization
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    if not context.auth:
        raise UnauthorizedError("Authentication required")
    context.require_scope("your_domain:read")
    if not self.validate_access(context):
        raise ForbiddenError("Access denied")
    return self._do_operation(context)
```

#### Step 4: Test and Refine

Test your plugin with different users and scope combinations to ensure proper security enforcement.

---

## Troubleshooting

### Common Issues

#### 1. "Authentication required" errors
- Ensure your plugin properly handles the enhanced context
- Check that authentication middleware is properly configured

#### 2. "Permission denied" errors
- Verify required scopes are correctly defined
- Check scope hierarchy configuration
- Ensure users have appropriate scopes assigned

#### 3. Middleware not applied
- Check plugin characteristics are properly defined
- Verify middleware preferences are correctly specified
- Ensure plugin classification is accurate

### Debugging Security Issues

Enable debug logging for security operations:

```python
import logging
logging.getLogger("agent.security").setLevel(logging.DEBUG)
logging.getLogger("agent.plugins").setLevel(logging.DEBUG)
```

Check the request context:

```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    logger.debug(f"User: {context.get_user_id()}")
    logger.debug(f"Scopes: {context.user_scopes}")
    logger.debug(f"Required scopes: {self.get_required_scopes(context.metadata.get('capability_id'))}")
    # ... rest of implementation
```

---

## Plugin Visibility Control

### Overview

AgentUp supports plugin visibility control through the A2A Authenticated Extended Card system. This allows you to control which plugins are advertised to public versus authenticated clients.

### Visibility Levels

Configure plugin visibility in your agent configuration:

```yaml
plugins:
  # Public plugins - visible to everyone
  - plugin_id: "general_help"
    name: "General Help"
    description: "Basic assistance"
    visibility: "public"  # default

  # Extended plugins - only visible to authenticated clients
  - plugin_id: "admin_tools"
    name: "Admin Tools"
    description: "Administrative functions"
    visibility: "extended"
```

### Behavior

| Visibility | Public Agent Card | Extended Agent Card | Execution |
|------------|-------------------|--------------------|-----------|
| `"public"` | ✓ Visible | ✓ Visible | ✓ Available |
| `"extended"` | ✗ Hidden | ✓ Visible | ✓ Available |

**Important**: Visibility only controls Agent Card advertisement, not plugin execution. All configured plugins are available for execution regardless of visibility setting.

### Use Cases

**Enterprise Deployments:**
```yaml
plugins:
  # Public information
  - plugin_id: "company_info"
    name: "Company Information"
    description: "Basic company details"
    visibility: "public"

  # Customer features
  - plugin_id: "order_status"
    name: "Order Status"
    description: "Check order status"
    visibility: "extended"
    required_scopes: ["customer:read"]

  # Admin features
  - plugin_id: "user_management"
    name: "User Management"
    description: "Manage users"
    visibility: "extended"
    required_scopes: ["admin:users"]
```

**Development vs Production:**
```yaml
plugins:
  # Always visible
  - plugin_id: "core_features"
    name: "Core Features"
    visibility: "public"

  # Debug tools - hidden from public
  - plugin_id: "debug_tools"
    name: "Debug Tools"
    description: "Development debugging tools"
    visibility: "extended"
    required_scopes: ["debug:access"]
```

### Security Considerations

1. **Discovery Control**: Extended plugins are hidden from public Agent Card discovery
2. **Execution Security**: Use `required_scopes` to control actual plugin execution
3. **Combined Approach**: Use both visibility and scopes for comprehensive control

```yaml
plugins:
  - plugin_id: "sensitive_data"
    name: "Sensitive Data Access"
    description: "Access confidential information"
    visibility: "extended"        # Hidden from public discovery
    required_scopes: ["data:sensitive"]  # Execution requires scope
```

### A2A Protocol Integration

The visibility system integrates with the A2A protocol:

- **Public Agent Card** (`/.well-known/agent.json`): Shows only public plugins
- **Extended Agent Card** (`/agent/authenticatedExtendedCard`): Shows all plugins
- **supportsAuthenticatedExtendedCard**: Automatically set based on extended plugin presence

For complete details, see the [A2A Extended Card documentation](../middleware/a2a-protocol.md#authenticated-extended-card).

---

## Current State and Future Roadmap

### What's Available Now

- **Basic Plugin Registration**: Use `register_capability()` to define capabilities with basic scope requirements
- **Capability Execution**: Implement security checks manually in `execute_capability()`
- **Task Routing**: Use `can_handle_task()` for simple keyword-based routing
- **AI Functions**: Integrate with LLMs through `get_ai_functions()`

### Planned Security Features

The following features are planned for future releases:

- **Advanced Authentication**: Comprehensive auth context with user information and token validation
- **Automatic Scope Validation**: Framework-level scope checking based on `required_scopes`
- **Plugin Characteristics**: Detailed plugin metadata for middleware selection
- **Middleware Integration**: Automatic rate limiting, caching, and retry logic
- **Custom Authorization Hooks**: Plugin-specific access control beyond scopes
- **Audit Logging**: Built-in security event logging and monitoring

### Migration Path

When advanced security features become available:

1. **Current plugins will continue to work** - no breaking changes
2. **Add security hooks gradually** - implement new hooks as they become available
3. **Remove manual security code** - replace plugin-specific auth with framework features
4. **Enhanced configuration** - use declarative security configuration

## Best Practices for Current Implementation

1. **Implement basic validation** in `execute_capability()`
2. **Use `required_scopes` in `PluginDefinition`** to document intended permissions
3. **Return clear error messages** for security violations
4. **Log security events** for audit purposes
5. **Validate input parameters** thoroughly
6. **Follow principle of least privilege** in your security checks

## Conclusion

While AgentUp's advanced security system is under development, plugin maintainers can still implement secure plugins using the current hooks and manual security validation. The planned security features will provide a more comprehensive and automated approach to plugin security.

For additional support or questions, refer to the main AgentUp documentation or reach out to the development team.

---
