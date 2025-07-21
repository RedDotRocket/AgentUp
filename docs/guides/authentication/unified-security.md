# AgentUp Security Framework (ASF)

**Comprehensive security model for AgentUp agents with context-aware middleware selection**

The AgentUp Security Framework represents a fundamental element in AgentUp's security model, providing protection across all endpoint
types with  middleware selection and scope-based authorization.

## Architecture Overview

### ASF Model

The Framework provides consistent protection across all AgentUp endpoints including JSON-RPC, MCP (Streamble HTTP), and push notification systems.

## Scope-Based Authorization

### Hierarchical Permissions

The AgentUp Security Framework implements comprehensive scope-based authorization with hierarchical permission inheritance. Scopes define what operations users are authorized to perform, with higher-level scopes automatically granting lower-level permissions.

The scope hierarchy simplifies permission management while maintaining security granularity. Admin scopes provide comprehensive
access, while specialized scopes grant specific permissions for targeted operations.

### Scope Inheritance

Scopes support inheritance patterns where higher-level permissions automatically include lower-level capabilities:

```yaml
scope_hierarchy:
  admin: ["*"]  # Admin has all permissions
  api:admin: ["api:write", "api:read"]
  api:write: ["api:read"]
  files:admin: ["files:write", "files:read", "files:sensitive"]
  files:write: ["files:read"]
  system:admin: ["system:write", "system:read"]
  system:write: ["system:read"]
```

### Plugin Scope Integration

Plugins define their scope requirements through the enhanced capability system, with automatic validation during execution. The
system ensures that users have appropriate permissions before allowing plugin execution.

Plugin scope requirements integrate with the classification system, providing automatic scope suggestions based on plugin
characteristics. This reduces configuration overhead while ensuring comprehensive authorization.

## Enhanced Security Context

### EnhancedCapabilityContext

The AgentUp Security Framework architecture provides comprehensive authentication and authorization information through
the `EnhancedCapabilityContext` class. This context flows through all plugin executions, providing consistent access to security information.

```python
@dataclass
class EnhancedCapabilityContext:
    # Core execution context
    task: Task
    config: dict[str, Any]
    services: dict[str, Any]
    state: dict[str, Any]
    metadata: dict[str, Any]

    # Enhanced security context
    auth: AuthContext
    user_scopes: list[str]
    plugin_classification: PluginCharacteristics
    request_id: str

    # Authorization helpers
    def require_scope(self, scope: str) -> None:
        """Require specific scope for operation"""

    def has_scope(self, scope: str) -> bool:
        """Check if user has specific scope"""

    def get_user_id(self) -> str:
        """Get authenticated user ID"""
```

### Context Propagation

Security context automatically propagates through all plugin executions, ensuring consistent access to authentication information.
Plugins receive comprehensive context without additional configuration requirements.

The context includes plugin classification information, enabling plugins to make security decisions based on their operational
characteristics. This provides flexibility for  authorization logic while maintaining consistent behavior.

## Middleware Integration

### Context-Aware Selection

The AgentUp Security Framework integrates with AgentUp's middleware system to provide  security middleware selection. Middleware is
automatically selected based on plugin characteristics and operational requirements.

LOCAL plugins receive minimal middleware overhead with basic timing and authentication checks. NETWORK plugins get comprehensive
middleware stacks including caching, retry logic, and rate limiting. The system optimizes middleware selection to match operational
characteristics.

### Middleware Compatibility Matrix

The system maintains a compatibility matrix that defines which middleware types are suitable for different plugin classifications:

```python
middleware_compatibility = {
    PluginType.LOCAL: {
        "cached": {"suitable": True, "default_ttl": 300},
        "rate_limited": {"suitable": False, "reason": "Local operations are fast"},
        "retryable": {"suitable": False, "reason": "Local operations don't fail network-wise"},
        "timed": {"suitable": True, "default": True}
    },
    PluginType.NETWORK: {
        "cached": {"suitable": True, "default_ttl": 600},
        "rate_limited": {"suitable": True, "default_rpm": 30},
        "retryable": {"suitable": True, "default_attempts": 3},
        "timed": {"suitable": True, "default": True}
    },
    PluginType.AI_FUNCTION: {
        "cached": {"suitable": False, "reason": "AI responses should be fresh"},
        "rate_limited": {"suitable": True, "default_rpm": 10},
        "retryable": {"suitable": False, "reason": "AI failures need different handling"},
        "timed": {"suitable": True, "default": True}
    }
}
```

### Sane Defaults

The system provides  middleware defaults based on plugin classification, reducing configuration overhead while ensuring appropriate
protection. Manual override capabilities allow for custom middleware configurations when needed.

Middleware defaults optimize for common use cases while providing flexibility for specialized requirements. The system maintains
performance through  selection while ensuring comprehensive security coverage.

## Endpoint Protection

### Comprehensive Coverage

The AgentUp Security Framework protects all AgentUp endpoints such as JSON RPC, MCP endpoints, push notification systems, and
JSON-RPC endpoints all receive consistent security protection.

Each endpoint type receives appropriate security measures based on its operational characteristics. The system ensures that all
endpoints have proper authentication, authorization, and middleware protection.

### MCP Endpoint Security

Previously unprotected MCP endpoints now receive comprehensive security including authentication, rate limiting, and proper
middleware application. This addresses a critical vulnerability while maintaining MCP protocol compliance.

MCP endpoints integrate with the AgentUp Security Framework authentication system, supporting all authentication methods with consistent
scope-based authorization. The system ensures proper security without compromising MCP functionality.

### Push Notification Security

Push notification systems receive enhanced security including authentication for configuration endpoints and validation for webhook
URLs. The system provides SSRF protection and proper authorization for notification operations.

Push notification security integrates with the AgentUp Security Framework authentication system, ensuring consistent behavior
across all notification operations. The system maintains notification functionality while providing comprehensive protection.

## Configuration Examples

Some common configuration patterns for the AgentUp Security Framework, I will also throw in some examples of sane middleware
defaults to rate limit, cache, and retry operations based on plugin characteristics.

### Basic Configuration

```yaml
# Basic API Key Authentication
security:
  enabled: true
  type: "api_key"
  api_key: "${API_KEY}"


# Plugin classification
plugins:
  - plugin_id: "system_tools"
    plugin_type: "local"
    required_scopes: ["system:read"]
  - plugin_id: "weather_api"
    plugin_type: "network"
    required_scopes: ["api:external"]
```

### Advanced Unified Configuration

```yaml

security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "${JWKS_URL}"
    jwt_issuer: "${JWT_ISSUER}"
    jwt_audience: "${JWT_AUDIENCE}"
    scope_hierarchy:
      admin: ["*"]
      api:admin: ["api:write", "api:read"]
      api:write: ["api:read"]
      files:admin: ["files:write", "files:read", "files:sensitive"]
      files:write: ["files:read"]

# Intelligent middleware with plugin-specific overrides
middleware:
  - name: "cached"
    params:
      ttl: 600
  - name: "rate_limited"
    params:
      requests_per_minute: 100
  - name: "retryable"
    params:
      max_attempts: 3
  - name: "timed"
    params: {}

# Plugin classification with custom characteristics
plugins:
  - plugin_id: "database_operations"
    plugin_type: "hybrid"
    required_scopes: ["data:read", "data:write"]
    middleware_override:
      - name: "cached"
        params:
          ttl: 120  # Shorter cache for database operations
      - name: "rate_limited"
        params:
          requests_per_minute: 200
      - name: "timed"
        params: {}

  - plugin_id: "ai_summarizer"
    plugin_type: "ai_function"
    required_scopes: ["ai:execute"]
    middleware_override:
      - name: "rate_limited"
        params:
          requests_per_minute: 20
      - name: "timed"
        params: {}
      # No caching for AI responses
```

### Enterprise Configuration

```yaml
# Enterprise-grade AgentUp Security Framework
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://login.microsoftonline.com/tenant/discovery/v2.0/keys"
    jwt_issuer: "https://login.microsoftonline.com/tenant/v2.0"
    jwt_audience: "enterprise-agent-id"
    scope_hierarchy:
      admin: ["*"]
      enterprise:admin: ["enterprise:write", "enterprise:read", "api:admin"]
      enterprise:write: ["enterprise:read", "api:write"]
      enterprise:read: ["api:read"]
      api:admin: ["api:write", "api:read"]
      api:write: ["api:read"]
      files:admin: ["files:write", "files:read", "files:sensitive"]
      files:write: ["files:read"]

# Enterprise middleware with enhanced protection
middleware:
  - name: "cached"
    params:
      ttl: 1800  # 30 minutes
      cache_errors: false
  - name: "rate_limited"
    params:
      requests_per_minute: 200
      burst_size: 20
  - name: "retryable"
    params:
      max_attempts: 5
      backoff_factor: 2.0
      max_delay: 60.0
  - name: "timed"
    params: {}

# Enterprise plugin classification
plugins:
  - plugin_id: "enterprise_reporting"
    plugin_type: "hybrid"
    required_scopes: ["enterprise:read", "api:read"]
    middleware_override:
      - name: "cached"
        params:
          ttl: 3600  # 1 hour for reports
      - name: "rate_limited"
        params:
          requests_per_minute: 50
      - name: "timed"
        params: {}

  - plugin_id: "user_management"
    plugin_type: "network"
    required_scopes: ["enterprise:admin"]
    middleware_override:
      - name: "cached"
        params:
          ttl: 300  # 5 minutes for user data
      - name: "rate_limited"
        params:
          requests_per_minute: 100
      - name: "retryable"
        params:
          max_attempts: 3
      - name: "timed"
        params: {}
```

---

**Quick Links:**
- [Authentication Overview](index.md)
- [Scope-Based Authorization](scope-based-authorization.md)
- [JWT Authentication](jwt-authentication.md)
- [API Key Authentication](api-keys.md)
- [OAuth2 Authentication](oauth2.md)