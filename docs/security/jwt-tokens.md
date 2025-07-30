# Bearer Token Authentication

**Stateless JWT authentication for modern applications**

Bearer token authentication in AgentUp provides JWT (JSON Web Token) validation for stateless, secure authentication. This guide covers
setup, configuration, and best practices for implementing bearer token authentication.

## Overview

Bearer token authentication in AgentUp provides comprehensive JWT-based authentication with AgentUp Security Framework integration:

- **JWT Support** - RFC 7519 compliant JSON Web Token validation with full cryptographic verification
- **Stateless Authentication** - No server-side session storage required for scalable deployments
- **Scope-Based Authorization** - Hierarchical permission system with inherited scope management
- **Unified Security Integration** - Context-aware middleware with plugin classification support
- **Enhanced Endpoint Protection** - Comprehensive coverage including previously vulnerable MCP endpoints
- **Custom Claims** - Extract user information and permissions from tokens for fine-grained access control
- **A2A Compliance** - Proper Bearer token security scheme advertising in agent discovery

### When to Use Bearer Tokens

| Good For | Consider OAuth2 Instead |
|-----------|-------------------------|
| Custom JWT systems | Enterprise OAuth2 providers |
| Stateless applications | Complex authorization flows |
| Microservices auth | Third-party integrations |
| Simple JWT validation | Token revocation requirements |
| Development/testing | Multi-tenant systems |

## Unified Security Integration

Bearer token authentication is fully integrated with AgentUp's AgentUp Security Framework, providing enhanced protection.


### Middleware Integration

Bearer token authentication works  with context-aware middleware:

```yaml
# Context-aware middleware configuration
middleware:
  - name: rate_limited
    params: {}
  - name: cached
    params:
      # Authentication-aware caching
      auth_aware_caching: true
      user_specific_cache: true
```

## Quick Setup

### Step 1: Generate or Obtain a JWT Token

```bash
# For testing, create a simple JWT token
python3 -c "
import time, json
from authlib.jose import jwt

# Create test payload
payload = {
    'sub': 'user123',
    'iss': 'your-app',
    'aud': 'your-agent',
    'iat': int(time.time()),
    'exp': int(time.time()) + 3600,  # 1 hour
    'name': 'Test User',
    'email': 'user@example.com'
}

# Generate token (use your own secret in production)
token = jwt.encode({'alg': 'HS256', 'typ': 'JWT'}, payload, 'your-secret-key')
print('Test JWT Token:')
print(token)
"
```

### Step 2: Configure Your Agent

Add to your `agent_config.yaml`:

```yaml
security:
  enabled: true
  type: "bearer"
  bearer_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Step 3: Test Authentication

```bash
# Start your agent
uv run uvicorn src.agent.main:app --reload --port 8000

# Test with bearer token
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     http://localhost:8000/agent/card

# Should return 200 OK with agent card data
```

## JWT Token Validation

### Current Implementation

AgentUp's bearer token authenticator currently performs:

1. **Format Validation** - Ensures proper "Bearer" prefix
2. **String Comparison** - Secure constant-time comparison with configured token
3. **Basic JWT Structure** - Validates JWT format (header.payload.signature)

> **Note**: Full JWT cryptographic validation (signature verification, claims validation) is available in the OAuth2 authenticator. Consider using OAuth2 for production JWT validation.

### Token Format Requirements

Valid JWT tokens must:
- Be properly formatted (header.payload.signature)
- Include standard claims (iss, aud, exp, etc.)
- Use supported algorithms (HS256, RS256, etc.)
- Be base64-encoded without padding issues
- Include scope claims for authorization (recommended)

## Scope-Based Authorization

Bearer token authentication integrates with AgentUp's hierarchical scope system to provide fine-grained access control. Scopes define what operations users can perform and automatically inherit from parent scopes.

### Scope Hierarchy

The Agentup Security Framework system supports hierarchical scopes with automatic inheritance:

```yaml
# Example scope hierarchy in agent_config.yaml
security:
  enabled: true
  type: "bearer"
  bearer:
    jwt_secret: "${JWT_SECRET}"
    algorithm: "HS256"
    scope_hierarchy:
      # Administrative scopes
      admin: ["*"]                          # Full access
      api:admin: ["api:write", "api:read"]

      # Functional scopes
      api:write: ["api:read"]               # Write includes read
      files:write: ["files:read"]

      # Base scopes
      api:read: []                          # Base permission
      files:read: []
```

### JWT Token with Scopes

Include scopes in your JWT token payload:

```python
# Generate JWT with scopes
payload = {
    "sub": "user123",
    "iss": "your-app",
    "aud": "your-agent",
    "iat": int(time.time()),
    "exp": int(time.time()) + 3600,

    # Scope-based authorization
    "scopes": ["api:write", "files:read"],

    # Additional claims
    "name": "John Doe",
    "email": "john@example.com"
}

token = jwt.encode(header, payload, secret)
```

### Automatic Scope Resolution

The system automatically resolves inherited permissions:

```python
# User has "api:write" scope
# Automatically grants: ["api:write", "api:read"]

# Plugin requires "api:read" scope
# Request succeeds because api:write inherits api:read
```

### Plugin-Specific Scopes

Different plugin types can require specific scopes:

```yaml
# Plugin configuration with scope requirements
plugins:
  - plugin_id: document_processor
    plugin_type: "hybrid"
    required_scopes: ["files:write", "api:read"]

  - plugin_id: ai_assistant
    plugin_type: "ai_function"
    required_scopes: ["api:read"]

  - plugin_id: system_monitor
    plugin_type: "network"
    required_scopes: ["system:read", "api:read"]
```

### Scope Validation in Practice

The system automatically validates scopes for each request:

1. **Token Extraction** - JWT token extracted from Authorization header
2. **Scope Resolution** - User scopes resolved with inheritance
3. **Plugin Classification** - Target plugin type identified
4. **Requirement Matching** - Required scopes checked against user scopes
5. **Context Enhancement** - Request context enhanced with security information

## Configuration Options

### Simple Configuration

```yaml
# Basic bearer token setup
security:
  enabled: true
  type: "bearer"
  bearer_token: "your-jwt-token-here"
```

### Advanced Configuration with Unified Security

```yaml
# Full bearer token configuration with AgentUp Security Framework
security:
  enabled: true
  type: "bearer"
  bearer:
    jwt_secret: "your-secret-key"
    algorithm: "HS256"
    issuer: "your-app"
    audience: "your-agent"

    # Scope hierarchy for authorization
    scope_hierarchy:
      admin: ["*"]
      api:write: ["api:read"]
      api:read: []
      files:write: ["files:read"]
      files:read: []
      system:read: []

    # Optional: Custom scope claim name in JWT
    scope_claim: "scopes"  # Default: "scopes"

    # Optional: User ID claim name in JWT
    user_claim: "sub"      # Default: "sub"
```

### Plugin Classification Integration

```yaml
# Bearer authentication with plugin classification
security:
  enabled: true
  type: "bearer"
  bearer:
    jwt_secret: "${JWT_SECRET}"
    algorithm: "HS256"
    scope_hierarchy:
      admin: ["*"]
      api:admin: ["api:write", "api:read"]
      api:write: ["api:read"]
      files:admin: ["files:write", "files:read"]
      files:write: ["files:read"]
      ai:execute: ["api:read"]
      network:admin: ["system:read", "api:read"]
      api:read: []
      files:read: []
      system:read: []

# Plugin configuration with scope requirements
plugins:
  - plugin_id: local_processor
    plugin_type: "local"
    required_scopes: ["api:read"]

  - plugin_id: network_api
    plugin_type: "network"
    required_scopes: ["network:admin"]

  - plugin_id: ai_assistant
    plugin_type: "ai_function"
    required_scopes: ["ai:execute"]

  - plugin_id: file_manager
    plugin_type: "hybrid"
    required_scopes: ["files:write"]
```

### Environment Variables

```yaml
# Using environment variables (recommended)
security:
  enabled: true
  type: "bearer"
  bearer_token: "${JWT_TOKEN}"
```

```bash
# .env file
JWT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Custom JWT Claims

### Standard Claims

JWT tokens should include standard claims:

```json
{
  "sub": "user123",           // Subject (user ID)
  "iss": "your-app",         // Issuer
  "aud": "your-agent",       // Audience
  "iat": 1640995200,         // Issued at
  "exp": 1640998800,         // Expires at
  "nbf": 1640995200          // Not before
}
```

### Custom Claims with Scopes

Add application-specific claims including scope-based authorization:

```json
{
  "sub": "user123",
  "iss": "your-app",
  "aud": "your-agent",
  "iat": 1640995200,
  "exp": 1640998800,

  // Scope-based authorization (AgentUp Security Framework)
  "scopes": ["api:write", "files:read", "system:read"],

  // Legacy role-based claims (optional)
  "roles": ["user", "admin"],
  "permissions": ["read", "write"],

  // Additional custom claims
  "name": "John Doe",
  "email": "john@example.com",
  "tenant_id": "org123",
  "department": "engineering"
}
```

### Scope Claim Examples

Different scope configurations for various user types:

```json
// Admin user
{
  "sub": "admin123",
  "scopes": ["admin"],  // Inherits all permissions
  "name": "System Administrator"
}

// API developer
{
  "sub": "dev456",
  "scopes": ["api:write", "files:read"],
  "name": "API Developer"
}

// Read-only user
{
  "sub": "viewer789",
  "scopes": ["api:read", "files:read"],
  "name": "Read Only User"
}

// AI service account
{
  "sub": "ai-service",
  "scopes": ["ai:execute", "api:read"],
  "name": "AI Service Account"
}
```

### Generating Custom Tokens

Note, the following scripts are for validation and development, tokens should be generated in secure
vault, preferably with a hardware backend.

```python
#!/usr/bin/env python3
# generate-jwt.py
import time
from authlib.jose import jwt

def generate_custom_jwt(user_id, name, email, scopes=None, roles=None, secret="your-secret"):
    """Generate a custom JWT token with scope-based authorization."""

    # Default scopes based on roles (for backward compatibility)
    if not scopes and roles:
        if "admin" in roles:
            scopes = ["admin"]
        elif "developer" in roles:
            scopes = ["api:write", "files:read"]
        else:
            scopes = ["api:read"]
    elif not scopes:
        scopes = ["api:read"]  # Default minimal access

    payload = {
        # Standard claims
        "sub": user_id,
        "iss": "your-app",
        "aud": "your-agent",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,  # 1 hour

        # Scope-based authorization (AgentUp Security Framework)
        "scopes": scopes,

        # Additional claims
        "name": name,
        "email": email,

        # Legacy claims (optional)
        "roles": roles or ["user"],
    }

    token = jwt.encode(
        header={"alg": "HS256", "typ": "JWT"},
        payload=payload,
        key=secret
    )

    return token.decode('utf-8') if isinstance(token, bytes) else token

# Example usage
if __name__ == "__main__":
    # Generate tokens with scope-based authorization
    admin_token = generate_custom_jwt(
        user_id="admin123",
        name="Admin User",
        email="admin@example.com",
        scopes=["admin"]  # Full access
    )

    developer_token = generate_custom_jwt(
        user_id="dev456",
        name="API Developer",
        email="dev@example.com",
        scopes=["api:write", "files:read"]
    )

    readonly_token = generate_custom_jwt(
        user_id="user789",
        name="Read Only User",
        email="user@example.com",
        scopes=["api:read", "files:read"]
    )

    ai_service_token = generate_custom_jwt(
        user_id="ai-service",
        name="AI Service Account",
        email="ai@example.com",
        scopes=["ai:execute", "api:read"]
    )

    print("Admin Token (full access):")
    print(admin_token)
    print("\nDeveloper Token (api:write, files:read):")
    print(developer_token)
    print("\nRead-only Token (api:read, files:read):")
    print(readonly_token)
    print("\nAI Service Token (ai:execute, api:read):")
    print(ai_service_token)
```

## Environment Variables

### Secure Token Management

```yaml
# agent_config.yaml (safe to commit)
security:
  enabled: true
  type: "bearer"
  bearer_token: "${JWT_TOKEN}"
  bearer:
    jwt_secret: "${JWT_SECRET:default-dev-secret}"
    jwt_issuer: "${JWT_ISSUER:your-app}"
    jwt_audience: "${JWT_AUDIENCE:your-agent}"
```

```bash
# .env file (DO NOT commit)
JWT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
JWT_SECRET=your-production-secret-key
JWT_ISSUER=https://your-app.com
JWT_AUDIENCE=your-agent-id
```

### Multiple Environment Setup

```bash
# development.env
JWT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dev-token...
JWT_SECRET=dev-secret-key
JWT_ISSUER=localhost

# production.env
JWT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.prod-token...
JWT_SECRET=super-secure-production-secret
JWT_ISSUER=https://your-production-app.com
```

## Testing and Validation

### Bearer Token Test Script

```bash
#!/bin/bash
# test-bearer-auth.sh - Test bearer token authentication

AGENT_URL="http://localhost:8000"
JWT_TOKEN="$1"

if [ -z "$JWT_TOKEN" ]; then
    echo "Usage: $0 <jwt_token>"
    echo "Example: $0 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    exit 1
fi

echo "Testing Bearer Token Authentication"
echo "====================================="

# Test 1: Discovery endpoint (should work without auth)
echo "1. Testing discovery endpoint (no auth required)..."
DISCOVERY_STATUS=$(curl -s -w "%{http_code}" "${AGENT_URL}/.well-known/agent.json" -o /dev/null)
if [ "$DISCOVERY_STATUS" = "200" ]; then
    echo "   Discovery endpoint accessible"
else
    echo "   Discovery endpoint failed ($DISCOVERY_STATUS)"
    exit 1
fi

# Test 2: Protected endpoint without token (should fail)
echo "2. Testing protected endpoint without bearer token..."
NO_AUTH_STATUS=$(curl -s -w "%{http_code}" "${AGENT_URL}/agent/card" -o /dev/null)
if [ "$NO_AUTH_STATUS" = "401" ]; then
    echo "   Protected endpoint correctly requires authentication"
else
    echo "   Protected endpoint should require authentication ($NO_AUTH_STATUS)"
fi

# Test 3: Protected endpoint with malformed token (should fail)
echo "3. Testing protected endpoint with malformed token..."
BAD_TOKEN_STATUS=$(curl -s -w "%{http_code}" -H "Authorization: Bearer invalid-token" "${AGENT_URL}/agent/card" -o /dev/null)
if [ "$BAD_TOKEN_STATUS" = "401" ]; then
    echo "   Malformed token correctly rejected"
else
    echo "   Malformed token should be rejected ($BAD_TOKEN_STATUS)"
fi

# Test 4: Protected endpoint without "Bearer" prefix (should fail)
echo "4. Testing protected endpoint without Bearer prefix..."
NO_BEARER_STATUS=$(curl -s -w "%{http_code}" -H "Authorization: ${JWT_TOKEN}" "${AGENT_URL}/agent/card" -o /dev/null)
if [ "$NO_BEARER_STATUS" = "401" ]; then
    echo "   Missing Bearer prefix correctly rejected"
else
    echo "   Missing Bearer prefix should be rejected ($NO_BEARER_STATUS)"
fi

# Test 5: Protected endpoint with valid token (should work)
echo "5. Testing protected endpoint with valid bearer token..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${JWT_TOKEN}" "${AGENT_URL}/agent/card")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$STATUS" = "200" ]; then
    echo "   Valid bearer token accepted"
    AGENT_NAME=$(echo "$BODY" | python -c "import sys, json; print(json.load(sys.stdin).get('name', 'Unknown Agent'))")
    echo "   📝 Connected to: $AGENT_NAME"

    # Check security scheme in response
    SECURITY_SCHEME=$(echo "$BODY" | python -c "
import sys, json
data = json.load(sys.stdin)
schemes = data.get('securitySchemes', {})
if 'BearerAuth' in schemes:
    print('Bearer token security scheme correctly advertised')
else:
    print('Warning: Bearer token security scheme not found')
")
    echo "   $SECURITY_SCHEME"
else
    echo "   Valid bearer token rejected ($STATUS)"
    echo "   📝 Error: $BODY"
fi

echo ""
echo "Bearer token testing completed!"
```

### JWT Token Decoder

```python
#!/usr/bin/env python3
# decode-jwt.py - Decode and validate JWT tokens
import json
import sys
import base64
from authlib.jose import jwt

def decode_jwt_header(token):
    """Decode JWT header without validation."""
    try:
        header_b64 = token.split('.')[0]
        # Add padding if needed
        header_b64 += '=' * (4 - len(header_b64) % 4)
        header_json = base64.urlsafe_b64decode(header_b64)
        return json.loads(header_json)
    except Exception as e:
        return {"error": str(e)}

def decode_jwt_payload(token):
    """Decode JWT payload without validation."""
    try:
        payload_b64 = token.split('.')[1]
        # Add padding if needed
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_json)
    except Exception as e:
        return {"error": str(e)}

def validate_jwt_token(token, secret=None):
    """Validate JWT token with secret."""
    if not secret:
        return {"error": "Secret required for validation"}

    try:
        claims = jwt.decode(token, secret)
        return {"valid": True, "claims": claims}
    except Exception as e:
        return {"valid": False, "error": str(e)}

def main():
    if len(sys.argv) < 2:
        print("Usage: python decode-jwt.py <jwt_token> [secret]")
        print("Example: python decode-jwt.py eyJhbGciOiJIUzI1NiIs... optional-secret")
        sys.exit(1)

    token = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 else None

    print("JWT Token Analysis")
    print("=" * 50)

    # Decode header
    header = decode_jwt_header(token)
    print("Header:")
    print(json.dumps(header, indent=2))

    # Decode payload
    payload = decode_jwt_payload(token)
    print("\nPayload:")
    print(json.dumps(payload, indent=2))

    # Validate if secret provided
    if secret:
        validation = validate_jwt_token(token, secret)
        print(f"\nValidation:")
        if validation.get("valid"):
            print("Token is valid")
        else:
            print(f"Token invalid: {validation.get('error')}")
    else:
        print("\nValidation: Skipped (no secret provided)")

    # Check expiration
    if "exp" in payload and not isinstance(payload.get("exp"), str):
        import time
        exp_time = payload["exp"]
        current_time = int(time.time())
        if exp_time > current_time:
            remaining = exp_time - current_time
            print(f"Token expires in {remaining} seconds")
        else:
            print(f"Token expired {current_time - exp_time} seconds ago")

if __name__ == "__main__":
    main()
```

### Integration Testing

```python
# test_bearer_auth.py
import pytest
import time
from authlib.jose import jwt
from fastapi.testclient import TestClient

@pytest.fixture
def test_jwt_token():
    """Generate test JWT token."""
    payload = {
        "sub": "test-user",
        "iss": "test-app",
        "aud": "test-agent",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "name": "Test User",
        "email": "test@example.com"
    }

    token = jwt.encode(
        header={"alg": "HS256", "typ": "JWT"},
        payload=payload,
        key="test-secret"
    )

    return token.decode('utf-8') if isinstance(token, bytes) else token

@pytest.fixture
def agent_app():
    """Create test agent with bearer auth."""
    from src.agent.main import app
    return app

@pytest.fixture
def client(agent_app):
    """Create test client."""
    return TestClient(agent_app)

def test_bearer_token_authentication(client, test_jwt_token):
    """Test bearer token authentication flow."""

    # Test 1: Discovery endpoint (no auth required)
    response = client.get("/.well-known/agent.json")
    assert response.status_code == 200

    # Test 2: Protected endpoint without token
    response = client.get("/agent/card")
    assert response.status_code == 401

    # Test 3: Protected endpoint with malformed authorization
    response = client.get(
        "/agent/card",
        headers={"Authorization": "Invalid token"}
    )
    assert response.status_code == 401

    # Test 4: Protected endpoint without Bearer prefix
    response = client.get(
        "/agent/card",
        headers={"Authorization": test_jwt_token}
    )
    assert response.status_code == 401

    # Test 5: Protected endpoint with valid bearer token
    response = client.get(
        "/agent/card",
        headers={"Authorization": f"Bearer {test_jwt_token}"}
    )
    assert response.status_code == 200

    # Verify security scheme in response
    agent_card = response.json()
    assert "securitySchemes" in agent_card
    assert "BearerAuth" in agent_card["securitySchemes"]
    assert agent_card["securitySchemes"]["BearerAuth"]["type"] == "http"
    assert agent_card["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
```

## Security Considerations

### Token Security

#### Best Practices
- **Use HTTPS only** - Never transmit JWT tokens over HTTP
- **Short expiration times** - Limit token lifetime (1-24 hours)
- **Secure storage** - Store tokens securely on client side
- **Secret protection** - Keep JWT secrets secure and rotate regularly
- **Algorithm specification** - Always specify allowed algorithms

#### Common Vulnerabilities
- **None algorithm attack** - Always validate algorithms are present
- **Weak secrets** - Use strong, random secrets (256+ bits)
- **Token in URLs** - Never put tokens in query parameters or URLs
- **XSS exposure** - Protect against cross-site scripting
- **Replay attacks** - Use short expiration and secure transmission

### AgentUp Security Features

- **Format validation** - Proper Bearer token format checking
- **Constant-time comparison** - Protection against timing attacks
- **No token logging** - Tokens are never logged or exposed
- **Secure error messages** - Generic "Unauthorized" responses
- **Input sanitization** - Comprehensive input validation

## Migration and Upgrading

### From API Key to Bearer Token

```yaml
# Before: API key authentication
security:
  enabled: true
  type: "api_key"
  api_key: "sk-your-api-key"

# After: Bearer token authentication
security:
  enabled: true
  type: "bearer"
  bearer_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Client changes:**
```bash
# Before: API key in header
curl -H "X-API-Key: sk-your-api-key" URL

# After: Bearer token in Authorization header
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." URL
```
