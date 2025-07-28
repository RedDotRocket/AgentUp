# Security Overview

AgentUp provides a comprehensive security framework with unified authentication, scope-based authorization, and audit logging. The system is designed to provide enterprise-grade security while maintaining ease of use and A2A protocol compliance.

## Security Module Architecture

AgentUp now features a comprehensive security module (`src/agent/security/`) that provides:

- **Multiple Authentication Types**: API Key, Bearer Token, OAuth2 (with JWT and JWKS support)
- **Secure Operations**: Constant-time comparisons, input validation, audit logging
- **Extensible Design**: Easy to add custom authenticators
- **Thread-Safe**: Designed for high-concurrency environments
- **Configuration-Driven**: All behavior controlled by configuration

## Overview

AgentUp includes a flexible authentication system that supports multiple authentication schemes while maintaining A2A protocol compliance. The system is designed to protect sensitive endpoints while keeping standard A2A discovery endpoints publicly accessible.

## Authentication Endpoints

### Public Endpoints (No Authentication Required)
- `/.well-known/agent.json` - **A2A Discovery Endpoint**
  - Always publicly accessible per A2A specification
  - Allows clients to discover agent capabilities
  - Should never be protected, but you can if you want to of course!

### Protected Endpoints (Authentication Required)
- `/agent/card` - **Duplicate Agent Card Endpoint**
  - Currently used for testing authentication
  - Returns same data as discovery endpoint
  - Protected when security is enabled

## Configuration

### Unified Security Configuration

AgentUp uses a unified security configuration that supports multiple authentication methods simultaneously:

```yaml
security:
  enabled: true
  auth:
    # API Key Authentication
    api_key:
      header_name: "X-API-Key"
      keys:
        - key: "sk-admin-key-123"
          scopes: ["admin"]
        - key: "sk-read-only-456"
          scopes: ["api:read", "files:read"]

    # Bearer Token Authentication
    bearer:
      header_name: "Authorization"
      tokens:
        - token: "bearer-token-789"
          scopes: ["api:write", "files:write"]

    # OAuth2 Authentication
    oauth2:
      enabled: true
      validation_strategy: "jwt"
      jwks_url: "https://oauth-provider.com/.well-known/jwks.json"
      jwt_algorithm: "RS256"
      jwt_issuer: "https://oauth-provider.com"
      jwt_audience: "your-agent-id"

  # Scope hierarchy (permission inheritance)
  scope_hierarchy:
    admin: ["*"]                    # Admin has all permissions
    api:write: ["api:read"]         # Write includes read
    files:admin: ["files:write", "files:read"]
    files:write: ["files:read"]

  # Audit logging
  audit:
    enabled: true
    log_level: "INFO"
    include_request_body: false
    include_response_body: false
```

### Alternative Formats (Also Supported)
```yaml
# Option 1: Full structure with multiple keys
security:
  enabled: true
  type: "api_key"
  api_key:
    header_name: "X-API-Key"
    location: "header"  # Options: header, query, cookie
    keys:
      - "sk-strong-key-1-abcd1234xyz"
      - "sk-strong-key-2-wxyz5678def"

# Option 2: Top-level api_key (legacy)
api_key: "sk-strong-api-key-abcd1234xyz"
security:
  enabled: true
  type: "api_key"

# Option 3: Bearer token authentication
security:
  enabled: true
  type: "bearer"
  bearer_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Option 4: Environment variables
security:
  enabled: true
  type: "api_key"
  api_key: "${API_KEY:default-key-here}"

# Option 5: OAuth2 JWT validation
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"  # Options: jwt, introspection, both
    jwt_secret: "your-jwt-secret-key"
    jwt_algorithm: "HS256"
    jwt_issuer: "https://your-oauth-provider.com"
    jwt_audience: "your-agent-id"
    required_scopes: ["read", "write"]

# Option 6: OAuth2 with JWKS (recommended for production)
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://your-oauth-provider.com/.well-known/jwks.json"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://your-oauth-provider.com"
    jwt_audience: "your-agent-id"
    required_scopes: ["agent:read", "agent:write"]

# Option 7: OAuth2 token introspection
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "introspection"
    client_id: "${OAUTH_CLIENT_ID}"
    client_secret: "${OAUTH_CLIENT_SECRET}"
    introspection_endpoint: "https://your-oauth-provider.com/oauth/introspect"
    required_scopes: ["api:access"]

# Option 8: OAuth2 hybrid (JWT + introspection fallback)
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "both"
    jwks_url: "https://your-oauth-provider.com/.well-known/jwks.json"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://your-oauth-provider.com"
    jwt_audience: "your-agent-id"
    client_id: "${OAUTH_CLIENT_ID}"
    client_secret: "${OAUTH_CLIENT_SECRET}"
    introspection_endpoint: "https://your-oauth-provider.com/oauth/introspect"
    required_scopes: ["agent:full"]
    allowed_scopes: ["agent:read", "agent:write", "agent:admin"]
```

## Security Manager Logic

The new `SecurityManager` class uses modular authenticators to handle different authentication types:
1. **Initialization**: Creates authenticator instances based on configuration
2. **Request Processing**: Routes authentication to the appropriate authenticator
3. **Policy Enforcement**: Applies security policies and scope-based authorization
4. **Audit Logging**: Logs all security events for monitoring

## Context-Aware Security Behavior

The security system now respects global configuration while providing override options:

| Global Setting | Decorator | Behavior | Use Case |
|---|---|---|---|
| `enabled: false` | `@protected()` | ✓ **Allow** (warn) | Development/testing |
| `enabled: false` | `@protected(force_auth=True)` | ✗ **Require auth** | Critical endpoints |
| `enabled: false` | `@protected(required=False)` | ✓ **Allow** (silent) | Public endpoints |
| `enabled: true` | `@protected()` | ✗ **Require auth** | Production mode |
| `enabled: true` | `@protected(force_auth=True)` | ✗ **Require auth** | Production mode |
| `enabled: true` | `@protected(required=False)` | ✓ **Allow** (silent) | Public endpoints |

### Benefits:
- **Development Friendly**: Easy to disable security for testing
- **Production Ready**: Full security when enabled
- **Granular Control**: Per-endpoint override options
- **Audit Trail**: Clear logging of security decisions

## Testing Authentication

### Test Without API Key (Should Fail)
```bash
curl -v http://localhost:8000/agent/card
# Expected: 401 Unauthorized
```

### Test With Valid API Key (Should Succeed)
```bash
curl -v -H "X-API-Key: sk-strong-api-key-abcd1234xyz" http://localhost:8000/agent/card
# Expected: 200 OK with agent card data
```

**Note**: Weak API keys like "password" are rejected by the security validator. Use strong keys with at least 8 characters and no common patterns.

### Test Discovery Endpoint (Always Works)
```bash
curl -v http://localhost:8000/.well-known/agent.json
# Expected: 200 OK (no authentication required)
```

### Test OAuth2 Authentication

#### Test With Valid JWT Token (Should Succeed)
```bash
# Using a valid OAuth2 JWT token
curl -v -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." http://localhost:8000/agent/card
# Expected: 200 OK with agent card data
```

#### Test Without Token (Should Fail)
```bash
curl -v http://localhost:8000/agent/card
# Expected: 401 Unauthorized
```

#### Test With Invalid Token (Should Fail)
```bash
curl -v -H "Authorization: Bearer invalid-token" http://localhost:8000/agent/card
# Expected: 401 Unauthorized
```

#### Test With Insufficient Scopes (Should Fail)
```bash
# If required_scopes is configured but token lacks them
curl -v -H "Authorization: Bearer token-without-required-scopes" http://localhost:8000/agent/card
# Expected: 401 Unauthorized
```

## Implementation Details

### Security Manager Initialization
The security system is initialized during application startup:

```python
# In main.py
from .security import create_security_manager

config = load_config()
security_manager = create_security_manager(config)
app.state.security_manager = security_manager
```

### Security Module Structure
```
src/agent/security/
├── __init__.py              # Main exports and factory functions
├── manager.py               # SecurityManager class
├── decorators.py            # @protected decorator
├── base.py                  # Abstract base classes
├── exceptions.py            # Security exceptions
├── validators.py            # Configuration validation
├── utils.py                 # Security utilities
└── authenticators/          # Authentication modules
    ├── api_key.py          # API key authentication
    ├── bearer.py           # Bearer token authentication
    └── __init__.py         # Authenticator registry
```

### Protecting Endpoints

#### New Method: @protected() Decorator (Recommended)
The cleanest way to protect endpoints is using the `@protected()` decorator:

```python
@router.get("/protected-endpoint")
@protected()
async def protected_endpoint(request: Request):
    """Protected endpoint requiring authentication."""
    return {"message": "Access granted"}
```

#### Decorator Options

**Context-Aware Protection (New Default Behavior):**
```python
# Respects global security setting (recommended)
@protected()
async def smart_endpoint(request: Request):
    # When security.enabled = false: Allows access (logs warning)
    # When security.enabled = true: Requires authentication
    return {"message": "Context-aware protection"}

# Force authentication regardless of global setting
@protected(force_auth=True)
async def always_secure_endpoint(request: Request):
    # Always requires auth even when security.enabled = false
    return {"message": "Always protected"}

# Never requires authentication
@protected(required=False)
async def public_endpoint(request: Request):
    # Always allows access regardless of global setting
    return {"message": "Always accessible"}
```

**Advanced Options:**
```python
# Force specific authentication type
@protected(auth_type="api_key")
async def api_key_endpoint(request: Request):
    return {"message": "Protected with API key only"}

# Scope-based authorization
@protected(scopes={"read", "write"})
async def scoped_endpoint(request: Request):
    return {"message": "Requires read and write permissions"}

# Anonymous access allowed
@protected(allow_anonymous=True)
async def mixed_endpoint(request: Request):
    # Check if user is authenticated
    from .security import get_auth_result
    auth_result = get_auth_result(request)
    if auth_result:
        return {"message": f"Hello {auth_result.user_id}"}
    return {"message": "Hello anonymous user"}
```

#### Convenience Decorators
```python
# API key specific (respects global setting)
@api_key_required()
async def api_endpoint(request: Request):
    return {"message": "API key required"}

# Bearer token specific (respects global setting)
@bearer_token_required()
async def jwt_endpoint(request: Request):
    return {"message": "Bearer token required"}

# Always protected regardless of global setting
@always_protected()
async def critical_endpoint(request: Request):
    return {"message": "Always requires authentication"}

# Always protected with specific requirements
@always_protected(auth_type="api_key", scopes={"admin"})
async def super_admin_endpoint(request: Request):
    return {"message": "Always requires API key + admin scope"}

# Scope requirements (respects global setting)
@require_scopes("admin", "write")
async def admin_endpoint(request: Request):
    return {"message": "Admin access required"}
```

## Debugging

### Startup Logging
The security manager logs initialization information:

```
INFO:src.agent.main:Security enabled with api_key authentication
INFO:src.agent.security.manager:Security manager initialized - enabled: True, primary auth: api_key
```

### Runtime Security Events
Authentication attempts are automatically logged:

```
INFO:src.agent.security.utils:Security event: authentication
WARNING:src.agent.security.utils:Security event failed: authentication
```

### Security Bypass Warnings
When global security is disabled, protected endpoints log bypass warnings:

```
WARNING:src.agent.security.decorators:Security bypass: /agent/card - Global security disabled, @protected() allowing access. Use force_auth=True to override.
```

This helps identify which endpoints would be protected in production.

### Common Issues Discovered

1. **Wrong Endpoint Testing**
   - Testing `/.well-known/agent.json` instead of `/agent/card`
   - Discovery endpoint is intentionally unprotected

2. **Configuration Format**
   - Multiple valid formats supported
   - Simple `api_key: "value"` format works
   - Complex nested structures also supported

3. **Server Restart Required**
   - Configuration changes require server restart
   - Security manager is initialized at startup

4. **Weak API Key Rejection**
   - API keys containing "password", "test", "admin", etc. are rejected
   - Use strong keys with at least 8 characters
   - Avoid common patterns and dictionary words

## Supported Authentication Types

### API Key Authentication
- **Header**: `X-API-Key: your-key-here`
- **Configuration**: Set in `security.api_key` or root `api_key`
- **Status**: ✓ Working

### Bearer Token Authentication
- **Header**: `Authorization: Bearer your-token-here`
- **Configuration**: Set in `security.bearer_token`
- **Status**: ✓ Fully implemented and tested

### OAuth2 Authentication
- **Header**: `Authorization: Bearer oauth-token`
- **Configuration**: Set in `security.oauth2`
- **Status**: ✓ Fully implemented with Authlib
- **Features**: JWT validation, token introspection, JWKS support, scope validation

## A2A Compliance Notes

- Discovery endpoint (`/.well-known/agent.json`) must remain publicly accessible
- Agent cards should be discoverable without authentication
- Protected endpoints are application-specific, not part of A2A spec
- Security schemes should be declared in agent card for client discovery

## Security Features

### 1. Secure Operations
- **Constant-Time Comparisons**: All credential comparisons use `secrets.compare_digest()` to prevent timing attacks
- **Input Validation**: Comprehensive validation of all security inputs
- **No Secret Logging**: Credentials are never logged, only masked versions for debugging
- **Thread Safety**: All operations are designed to be thread-safe

### 2. Audit Logging
The security system logs all authentication attempts and security events:
```python
# Security events are automatically logged
# Example log entry:
{
    "timestamp": "2024-01-01T12:00:00Z",
    "event_type": "authentication",
    "success": true,
    "client_ip": "192.168.1.100",
    "user_agent": "curl/7.68.0",
    "endpoint": "/agent/card",
    "method": "GET"
}
```

### 3. Configuration Validation
The system validates security configuration at startup:
```python
# Invalid configurations are caught early
from .security import validate_security_config

try:
    validate_security_config(config)
except SecurityConfigurationException as e:
    print(f"Security config error: {e}")
```

### 4. Extensible Architecture
Adding new authenticators is straightforward:
```python
from .security.base import BaseAuthenticator

class CustomAuthenticator(BaseAuthenticator):
    def _validate_config(self):
        # Validate custom config
        pass

    async def authenticate(self, request):
        # Implement custom authentication
        return AuthenticationResult(success=True, user_id="custom_user")
```

## Migration Guide

### From Old to New Security System

**Old Pattern:**
```python
# Old inline security handler (deprecated)
await security_handler.authenticate_request(request)
```

**New Pattern:**
```python
# New declarative decorator (recommended)
@protected()
async def my_endpoint(request: Request):
    return {"message": "Protected"}
```

### Accessing Authentication Information
```python
@protected()
async def my_endpoint(request: Request):
    from .security import get_auth_result, get_current_user_id, has_scope

    # Get full authentication result
    auth_result = get_auth_result(request)

    # Get just the user ID
    user_id = get_current_user_id(request)

    # Check specific scopes
    if has_scope(request, "admin"):
        return {"message": "Admin access granted"}
```

## OAuth2 Provider Examples

### Google OAuth2
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://www.googleapis.com/oauth2/v3/certs"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://accounts.google.com"
    jwt_audience: "your-google-client-id.apps.googleusercontent.com"
    required_scopes: ["openid", "email"]
```

### Auth0
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://your-domain.auth0.com/.well-known/jwks.json"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://your-domain.auth0.com/"
    jwt_audience: "your-auth0-api-identifier"
    required_scopes: ["read:agents", "write:agents"]
```

### Microsoft Azure AD
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://login.microsoftonline.com/{tenant-id}/v2.0"
    jwt_audience: "your-azure-app-id"
    required_scopes: ["api://your-app-id/Agent.Read"]
```

### GitHub OAuth (using introspection)
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "introspection"
    client_id: "${GITHUB_CLIENT_ID}"
    client_secret: "${GITHUB_CLIENT_SECRET}"
    introspection_endpoint: "https://api.github.com/applications/{client_id}/token"
    # GitHub doesn't use traditional scopes for apps
```

### Custom OAuth2 Provider
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "both"  # Try JWT first, fallback to introspection
    jwks_url: "https://your-oauth-provider.com/.well-known/jwks.json"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://your-oauth-provider.com"
    jwt_audience: "agentup-api"
    client_id: "${OAUTH_CLIENT_ID}"
    client_secret: "${OAUTH_CLIENT_SECRET}"
    introspection_endpoint: "https://your-oauth-provider.com/oauth/introspect"
    required_scopes: ["agent:access"]
    allowed_scopes: ["agent:read", "agent:write", "agent:admin"]
```

## Future Enhancements

1. **Advanced OAuth2 Features**
   - Authorization code flow support for human-to-agent scenarios
   - Client credentials flow for service-to-service communication
   - Token refresh capabilities

2. **Advanced Features**
   - Rate limiting per user/API key
   - Credential rotation support
   - Multi-factor authentication
   - Role-based access control (RBAC)

3. **Monitoring & Analytics**
   - Security dashboards
   - Attack detection and prevention
   - Performance metrics for authentication

## Testing Checklist

### Basic Functionality
- [ ] Security disabled: All endpoints accessible
- [ ] Security enabled: Discovery endpoint still public
- [ ] Security enabled: Protected endpoints require auth
- [ ] Invalid API key: Returns 401
- [ ] Valid API key: Returns 200
- [ ] Configuration changes: Require server restart

### Security Module Features
- [ ] API key validation: Weak keys rejected
- [ ] Bearer token authentication: Works with valid tokens
- [ ] Multiple API keys: All configured keys work
- [ ] Environment variables: `${VAR:default}` format works
- [ ] Audit logging: Security events logged properly
- [ ] Decorator patterns: `@protected()` works correctly
- [ ] Scope validation: Scope-based authorization works
- [ ] Anonymous access: `allow_anonymous=True` works

### Error Handling
- [ ] Invalid configuration: Fails fast with clear errors
- [ ] Missing headers: Returns appropriate 401 errors
- [ ] Malformed tokens: Returns appropriate 400 errors
- [ ] Security manager not initialized: Returns 500 errors

---

## Scope-Based Authorization

AgentUp implements a hierarchical scope-based authorization system that provides fine-grained access control across all agent capabilities.

### Understanding Scopes

Scopes are permission strings that control access to specific capabilities. They follow a hierarchical pattern:

- `admin` - Full system access (wildcard `*`)
- `api:read` - Read access to API endpoints
- `api:write` - Write access to API endpoints (inherits `api:read`)
- `files:read` - Read file operations
- `files:write` - Write file operations (inherits `files:read`)
- `files:delete` - Delete file operations
- `plugins:read` - List and inspect plugins
- `plugins:write` - Install and configure plugins
- `mcp:use` - Use MCP tools

### Scope Hierarchy Configuration

The `scope_hierarchy` section defines which scopes inherit permissions from others:

```yaml
security:
  scope_hierarchy:
    # Universal access
    admin: ["*"]

    # API access levels
    api:admin: ["api:write", "api:read"]
    api:write: ["api:read"]

    # File system access
    files:admin: ["files:delete", "files:write", "files:read"]
    files:write: ["files:read"]

    # Plugin management
    plugins:admin: ["plugins:write", "plugins:read"]
    plugins:write: ["plugins:read"]

    # MCP access
    mcp:admin: ["mcp:write", "mcp:read"]
    mcp:write: ["mcp:read"]
```

### Plugin Capability Authorization

Each plugin capability can require specific scopes:

```yaml
plugins:
  - plugin_id: "file_system"
    capabilities:
      - capability_id: "read_file"
        required_scopes: ["files:read"]
        enabled: true
      - capability_id: "write_file"
        required_scopes: ["files:write"]
        enabled: true
      - capability_id: "delete_file"
        required_scopes: ["files:delete", "files:write"]
        enabled: true
```

### MCP Tool Security

MCP tools are mapped to AgentUp scopes for fine-grained security:

```yaml
mcp:
  servers:
    - name: "filesystem"
      type: "stdio"
      command: "mcp-server-filesystem"
      args: ["/workspace"]
      # Map each MCP tool to required scopes
      tool_scopes:
        read_file: ["files:read"]
        write_file: ["files:write"]
        list_directory: ["files:read"]
        create_directory: ["files:write"]
        delete_file: ["files:delete"]

    - name: "github"
      type: "http"
      url: "https://api.github.com/mcp"
      tool_scopes:
        list_repos: ["github:read"]
        create_repo: ["github:write"]
        delete_repo: ["github:admin"]
        create_issue: ["github:write"]
        close_issue: ["github:write"]
```

### User Access Control

Users are granted specific scopes through their authentication tokens:

```yaml
security:
  auth:
    api_key:
      keys:
        # Admin user with full access
        - key: "sk-admin-key-123"
          scopes: ["admin"]

        # Developer with file and API access
        - key: "sk-dev-key-456"
          scopes: ["api:write", "files:write", "plugins:read"]

        # Read-only user
        - key: "sk-readonly-789"
          scopes: ["api:read", "files:read"]

    oauth2:
      # OAuth2 tokens can carry scopes from the provider
      required_scopes: ["agent:access"]  # Minimum required
      allowed_scopes: ["agent:read", "agent:write", "agent:admin"]
```

### Scope Validation Process

1. **Request Received**: Agent receives request with authentication
2. **Token Validation**: Authentication method validates the token/key
3. **Scope Extraction**: System extracts user's granted scopes
4. **Scope Expansion**: Hierarchy rules expand scopes (e.g., `api:write` → `["api:write", "api:read"]`)
5. **Permission Check**: Required scopes for the operation are checked against user's expanded scopes
6. **Access Decision**: Request allowed if user has all required scopes

### Example: File Operation Flow

```yaml
# User request to write a file
# 1. User authenticated with scopes: ["files:write"]
# 2. Scope expansion: ["files:write"] → ["files:write", "files:read"]
# 3. Plugin capability requires: ["files:write"]
# 4. Check: user has "files:write" ✓
# 5. Access granted
```

### Audit Logging

All scope-based authorization decisions are logged:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "event": "authorization_check",
  "user_id": "api-key-hash",
  "required_scopes": ["files:write"],
  "user_scopes": ["files:write", "files:read"],
  "result": "allowed",
  "resource": "file_system.write_file"
}
```

### Best Practices

1. **Principle of Least Privilege**: Grant only necessary scopes
2. **Scope Naming**: Use consistent, hierarchical naming (e.g., `service:action`)
3. **Regular Audits**: Review user scopes periodically
4. **Scope Documentation**: Document what each scope allows
5. **Testing**: Test with restricted users to ensure proper enforcement

### Common Scope Patterns

```yaml
# Service-based scopes
database:read: ["db:query", "db:select"]
database:write: ["db:insert", "db:update", "database:read"]
database:admin: ["db:schema", "database:write"]

# Resource-based scopes
files:user: ["files:read"]  # User's own files
files:shared: ["files:read", "files:user"]  # Shared files
files:system: ["files:admin", "files:shared"]  # System files

# Operation-based scopes
api:public: []  # Public endpoints
api:authenticated: ["api:read"]  # Authenticated endpoints
api:privileged: ["api:write", "api:authenticated"]  # Privileged operations
```