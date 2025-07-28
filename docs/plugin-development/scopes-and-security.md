# Plugin Security and Scopes Guide

This guide provides comprehensive information for plugin maintainers on implementing security, authentication scopes, and authorization in AgentUp plugins.

## Overview

AgentUp uses scope-based authentication and context-aware middleware. Plugins must define their security requirements and implement proper authorization checks to ensure secure operation.

## Table of Contents

1. [Authentication Scopes](#authentication-scopes)
2. [Plugin Classification](#plugin-classification)
3. [Security Context](#security-context)
4. [Implementing Security in Plugins](#implementing-security-in-plugins)
5. [Scope Hierarchy](#scope-hierarchy)
6. [Best Practices](#best-practices)
7. [Examples](#examples)
8. [Migration Guide](#migration-guide)

---

## Authentication Scopes

### What are Scopes?

Scopes are permission strings that define what operations a user is authorized to perform. They follow a hierarchical structure and support inheritance.

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
@dataclass
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

### Classification Examples

#### Local System Plugin
```python
def get_plugin_characteristics(self) -> PluginCharacteristics:
    return PluginCharacteristics(
        plugin_type=PluginType.LOCAL,
        network_dependent=False,
        cacheable=True,
        cache_ttl=300,  # 5 minutes
        retry_suitable=False,  # Local operations don't fail network-wise
        rate_limit_required=False,  # Local operations are fast
        auth_scopes=["system:read"],
        performance_critical=False
    )
```

#### Network API Plugin
```python
def get_plugin_characteristics(self) -> PluginCharacteristics:
    return PluginCharacteristics(
        plugin_type=PluginType.NETWORK,
        network_dependent=True,
        cacheable=True,
        cache_ttl=600,  # 10 minutes
        retry_suitable=True,  # Network calls can fail
        rate_limit_required=True,  # Respect external API limits
        auth_scopes=["api:external"],
        performance_critical=False
    )
```

---

## Security Context

### Capability Context

The `CapabilityContext` provides plugins with comprehensive security information:

```python
@dataclass
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

### Required Hook Methods

#### 1. Plugin Characteristics

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

#### 2. Required Scopes

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

#### 3. Custom Authorization

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

#### 4. Middleware Preferences

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

### Enhanced Capability Execution

```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    """Execute capability with comprehensive security checks."""

    try:
        # 1. Validate authentication
        if not context.auth:
            raise UnauthorizedError("Authentication required")

        # 2. Check required scopes (automatically done by framework)
        # Additional scope checks can be done manually:
        capability_id = context.metadata.get("capability_id")
        if capability_id == "admin_operation":
            context.require_scope("admin")

        # 3. Custom authorization
        if not self.validate_access(context):
            raise ForbiddenError("Access denied by custom authorization")

        # 4. Audit logging
        self._log_access(context)

        # 5. Execute the actual operation
        result = self._execute_operation(context)

        # 6. Add security metadata to result
        result.metadata.update({
            "user_id": context.get_user_id(),
            "auth_type": context.auth.auth_type,
            "scopes_used": context.user_scopes,
            "request_id": context.request_id
        })

        return result

    except (UnauthorizedError, ForbiddenError) as e:
        # Log security violations
        self._log_security_violation(context, str(e))
        raise
    except Exception as e:
        # Log and handle other errors
        self._log_error(context, str(e))
        return CapabilityResult(
            content=f"Operation failed: {str(e)}",
            success=False,
            error=str(e)
        )

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

### Example 1: File System Plugin

```python
class FileSystemPlugin:
    """Plugin for file system operations with proper security."""

    @hookimpl
    def get_plugin_characteristics(self) -> PluginCharacteristics:
        return PluginCharacteristics(
            plugin_type=PluginType.LOCAL,
            network_dependent=False,
            cacheable=False,  # File contents change
            retry_suitable=False,
            rate_limit_required=False,
            auth_scopes=["files:read"],
            performance_critical=True
        )

    @hookimpl
    def get_required_scopes(self, capability_id: str) -> list[str]:
        return {
            "read_file": ["files:read"],
            "write_file": ["files:write"],
            "delete_file": ["files:write", "files:admin"],
            "read_sensitive": ["files:read", "files:sensitive"],
        }.get(capability_id, ["files:read"])

    @hookimpl
    def validate_access(self, context: CapabilityContext) -> bool:
        """Additional file-specific authorization."""
        file_path = context.metadata.get("file_path", "")

        # Restrict access to system files
        if file_path.startswith("/etc/") or file_path.startswith("/sys/"):
            return context.has_scope("system:admin")

        # Restrict access to sensitive directories
        sensitive_dirs = ["/home/", "/Users/", "/.ssh/"]
        if any(file_path.startswith(d) for d in sensitive_dirs):
            return context.has_scope("files:sensitive")

        return True

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        capability_id = context.metadata.get("capability_id")
        file_path = context.metadata.get("file_path")

        if capability_id == "read_file":
            return self._read_file(context, file_path)
        elif capability_id == "write_file":
            return self._write_file(context, file_path)
        # ... other operations

    def _read_file(self, context: EnhancedCapabilityContext, file_path: str) -> CapabilityResult:
        try:
            # Security is already validated by framework + validate_access
            with open(file_path, 'r') as f:
                content = f.read()

            self._log_operation(context, "read_file", "success")

            return CapabilityResult(
                content=content,
                success=True,
                metadata={
                    "file_path": file_path,
                    "user_id": context.get_user_id(),
                    "size": len(content)
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
```

### Example 2: External API Plugin

```python
class WeatherAPIPlugin:
    """Plugin for weather API with network-aware security."""

    @hookimpl
    def get_plugin_characteristics(self) -> PluginCharacteristics:
        return PluginCharacteristics(
            plugin_type=PluginType.NETWORK,
            network_dependent=True,
            cacheable=True,
            cache_ttl=1800,  # 30 minutes
            retry_suitable=True,
            rate_limit_required=True,
            auth_scopes=["api:external", "weather:read"],
            performance_critical=False
        )

    @hookimpl
    def get_required_scopes(self, capability_id: str) -> list[str]:
        return {
            "get_weather": ["weather:read", "api:external"],
            "get_forecast": ["weather:read", "api:external"],
            "get_alerts": ["weather:read", "weather:alerts", "api:external"],
        }.get(capability_id, ["weather:read"])

    @hookimpl
    def get_middleware_preferences(self, capability_id: str) -> dict[str, Any]:
        return {
            "cached": {
                "enabled": True,
                "ttl": 1800,
                "key_strategy": "location_aware"
            },
            "rate_limited": {
                "enabled": True,
                "requests_per_minute": 30,  # API limit
                "per_user": True
            },
            "retryable": {
                "enabled": True,
                "max_attempts": 3,
                "backoff_factor": 2.0
            }
        }

    @hookimpl
    def validate_access(self, context: CapabilityContext) -> bool:
        """Custom authorization for weather API."""
        # Check if user has remaining API quota
        user_id = context.get_user_id()
        if not self._check_api_quota(user_id):
            return False

        # Premium features require premium scope
        capability_id = context.metadata.get("capability_id")
        if capability_id == "get_alerts":
            return context.has_scope("weather:premium")

        return True

    def _check_api_quota(self, user_id: str) -> bool:
        """Check if user has remaining API quota."""
        # Implementation would check against quota system
        return True
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

For complete details, see the [A2A Extended Card documentation](../a2a-extended-card.md).

---

## Conclusion

The Agentup Security Framework model provides comprehensive protection while maintaining flexibility for different plugin types. By following this guide, plugin maintainers can implement robust security that integrates  with AgentUp's middleware and authentication system.

The plugin visibility system adds an additional layer of control for enterprise deployments, allowing you to provide different capability levels to public versus authenticated clients.

For additional support or questions, refer to the main AgentUp documentation or reach out to the development team.

---
