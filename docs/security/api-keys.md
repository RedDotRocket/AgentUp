# API Key Authentication

**Simple, secure authentication with comprehensive endpoint protection**

API key authentication provides a straightforward way to secure your AgentUp agent through the security architecture. This authentication method now protects all endpoints including the main Agent JSON RPC,MCP endpoints and the push notification systems, while integrating with context-aware middleware selection and scope-based authorization.

## Table of Contents

- [Overview](#overview)
- [Quick Setup](#quick-setup)
- [Configuration Options](#configuration-options)
- [Multiple API Keys with Scopes](#multiple-api-keys-with-scopes)
- [Environment Variables](#environment-variables)
- [Plugin Integration](#plugin-integration)
- [Comprehensive Endpoint Protection](#comprehensive-endpoint-protection)
- [Security Best Practices](#security-best-practices)
- [Testing and Validation](#testing-and-validation)

## Overview

API key authentication in AgentUp integrates with the AgentUp Security Framework to provide comprehensive protection across all
endpoint types with middleware selection and scope-based authorization capabilities.

### Enhanced Security Features

The API key system provides simple setup with comprehensive protection, flexible configuration options including headers, query
parameters, and cookies, and support for multiple keys with individual scope assignments. The system includes automatic rejection
of weak keys and A2A spec compliance with proper security scheme advertising through the Agent Card endpoint.

The enhanced system now supports scope-based authorization, allowing different API keys to have different permission levels. Context-aware
middleware selection ensures optimal security measures based on plugin characteristics, while comprehensive endpoint protection
covers all AgentUp endpoints including MCP and push notification systems.

### When to Use API Keys

API key authentication is ideal for development and testing environments, internal APIs, service-to-service authentication, simple
authentication scenarios, and microservices architectures.

The system now supports complex authorization needs through scope integration, making API keys suitable for a broader range of use cases
while maintaining the simplicity that makes them attractive for straightforward authentication scenarios.

## Integration

### Comprehensive Endpoint Protection

The AgentUp Security Framework ensures that API key authentication protects all AgentUp endpoints. MCP endpoints at `/mcp`, push notification
configuration endpoints, and all JSON-RPC endpoints now require proper API key authentication.

This comprehensive protection eliminates security gaps while maintaining the simplicity that makes API keys attractive for
development and internal use. The system ensures consistent behavior across all endpoint types while providing appropriate
security measures for each operational context.

### Scope-Based Authorization Support

The enhanced API key system supports scope-based authorization, allowing different keys to have different permission levels. This enables
access control patterns while maintaining the operational simplicity that makes API keys attractive for internal use.

API keys can be associated with specific scopes through configuration, enabling fine-grained access control that adapts to organizational
requirements. The scope system integrates with the plugin classification system to provide automatic scope suggestions and validation.

## Quick Setup

### Step 1: Generate a Strong API Key

```bash
# Generate a secure API key
python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"

# Example output: sk-8K2mNx9P7qR4sV5yA3bC6dE9fH2jK5lM8nP1qS4t
```

### Step 2: Configure Your Agent with Unified Security

Add comprehensive security configuration to your `agent_config.yaml`:

```yaml
# Unified security configuration
security:
  enabled: true
  type: "api_key"
  api_key: "sk-8K2mNx9P7qR4sV5yA3bC6dE9fH2jK5lM8nP1qS4t"

# Context-aware middleware
middleware:
  - name: "timed"
    params: {}
  - name: "cached"
    params:
      ttl: 300  # 5 minutes
  - name: "rate_limited"
    params:
      requests_per_minute: 60

# Plugin configuration with classification
plugins:
  - plugin_id: "system_info"
    name: "System Information"
    plugin_type: "local"
    required_scopes: ["system:read"]
  - plugin_id: "external_api"
    name: "External API"
    plugin_type: "network"
    required_scopes: ["api:read"]
```

### Step 3: Test Comprehensive Authentication

The AgentUp Security Framework now protects all endpoints:

```bash
# Start your agent
agentup agent serve --port 8000

# Test JSON-RPC endpoint
curl -H "X-API-Key: sk-8K2mNx9P7qR4sV5yA3bC6dE9fH2jK5lM8nP1qS4t" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"capabilities","id":"test-1"}' \
     http://localhost:8000/

# Test MCP endpoint (now protected)
curl -H "X-API-Key: sk-8K2mNx9P7qR4sV5yA3bC6dE9fH2jK5lM8nP1qS4t" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":"mcp-test-1"}' \
     http://localhost:8000/mcp

# Test Agent Card endpoint
curl -H "X-API-Key: sk-8K2mNx9P7qR4sV5yA3bC6dE9fH2jK5lM8nP1qS4t" \
     http://localhost:8000/.well-known/agent.json

# All should return 200 OK with proper authentication
```

## Configuration Options

### Basic Configuration

```yaml
# Simple format (recommended for most use cases)
security:
  enabled: true
  type: "api_key"
  api_key: "sk-your-strong-api-key-here"
```

### Advanced Configuration

```yaml
# Full configuration with all options
security:
  enabled: true
  type: "api_key"
  api_key:
    header_name: "X-API-Key"     # Custom header name
    location: "header"           # Options: header, query, cookie
    keys:                        # Multiple API keys
      - "sk-prod-key-abc123"
      - "sk-staging-key-xyz789"
      - "sk-dev-key-def456"
```

### Location Options

#### Header Authentication (Default)
```yaml
api_key:
  header_name: "X-API-Key"
  location: "header"
  keys: ["sk-your-key-here"]
```

**Usage:**
```bash
curl -H "X-API-Key: sk-your-key-here" http://localhost:8000/agent/card
```

#### Query Parameter Authentication
```yaml
api_key:
  header_name: "api_key"  # Query parameter name
  location: "query"
  keys: ["sk-your-key-here"]
```

**Usage:**
```bash
curl "http://localhost:8000/agent/card?api_key=sk-your-key-here"
```

> **Security Note**: Query parameters may be logged by web servers and proxies. Use headers in production.

#### Cookie Authentication
```yaml
api_key:
  header_name: "auth_token"  # Cookie name
  location: "cookie"
  keys: ["sk-your-key-here"]
```

**Usage:**
```bash
curl -H "Cookie: auth_token=sk-your-key-here" http://localhost:8000/agent/card
```

## Multiple API Keys with Scopes

### Use Cases for Multiple Keys with Scope-Based Authorization

The AgentUp Security Framework enhances multiple API key support with comprehensive scope-based authorization. Different API keys
can have different permission levels, enabling  access control patterns while maintaining the operational simplicity that makes API
keys attractive for internal use.

**Environment Separation with Scopes**: Different keys for dev/staging/prod environments, each with appropriate permission levels
for their operational context. Production keys receive restrictive scopes while development keys get broader permissions for testing flexibility.

**Role-Based Access Control**: API keys can represent different organizational roles, each with specific scope assignments that match
their operational responsibilities. This enables fine-grained access control without complex authentication flows.

**Client Segmentation with Permissions**: Separate keys for different applications or services, each with scopes tailored to their
specific integration requirements. This ensures that each client has only the permissions necessary for their intended operations.

**Team-Based Authorization**: Different teams receive API keys with scopes matching their operational needs and security clearance
levels. Development teams might receive broader scopes for testing, while production teams get restrictive operational scopes.

### Configuration with Scope Integration

The AgentUp Security Framework supports API key scope assignment through multiple configuration patterns:

```yaml
security:
  enabled: true
  type: "api_key"
  api_key:
    header_name: "X-API-Key"
    location: "header"
    scope_hierarchy:
      admin: ["*"]
      api:write: ["api:read"]
      files:write: ["files:read"]
      system:read: []
    keys:
      - key: "sk-admin-key-2024-01-abcd1234"
        scopes: ["admin"]                          # Full administrative access
      - key: "sk-prod-api-2024-01-efgh5678"
        scopes: ["api:write", "files:read"]        # Production API access
      - key: "sk-staging-api-2024-01-ijkl9012"
        scopes: ["api:read", "files:read"]         # Staging read access
      - key: "sk-dev-all-2024-01-mnop3456"
        scopes: ["api:write", "files:write", "system:read"]  # Development flexibility
      - key: "sk-client-readonly-2024-01-qrst7890"
        scopes: ["api:read"]                       # Client read-only access
```

### Advanced Scope Assignment Patterns

The scope-based authorization system supports  assignment patterns for complex organizational requirements:

```yaml
# Advanced scope assignment with custom domains
security:
  enabled: true
  type: "api_key"
  api_key:
    header_name: "X-API-Key"
    location: "header"
    scope_hierarchy:
      admin: ["*"]
      enterprise:admin: ["enterprise:write", "enterprise:read", "api:admin"]
      enterprise:write: ["enterprise:read", "api:write"]
      enterprise:read: ["api:read"]
      finance:admin: ["finance:write", "finance:read", "enterprise:read"]
      finance:write: ["finance:read"]
      reporting:read: ["api:read"]
    keys:
      - key: "sk-enterprise-admin-2024-01-abc123"
        scopes: ["enterprise:admin"]
        metadata:
          description: "Enterprise administrator access"
          department: "IT Operations"
          valid_until: "2024-12-31"
      - key: "sk-finance-write-2024-01-def456"
        scopes: ["finance:write"]
        metadata:
          description: "Finance department write access"
          department: "Finance"
          valid_until: "2024-06-30"
      - key: "sk-reporting-read-2024-01-ghi789"
        scopes: ["reporting:read"]
        metadata:
          description: "Read-only reporting access"
          department: "Business Intelligence"
          valid_until: "2024-12-31"
```

### Key Management Best Practices

#### 1. Naming Convention
```
sk-{environment}-{purpose}-{date}-{random}

Examples:
sk-prod-webapp-2024-01-abc123
sk-staging-api-2024-01-def456
sk-dev-testing-2024-01-ghi789
```

#### 2. Key Rotation Strategy
```yaml
# Phase 1: Add new key alongside old key
keys:
  - "sk-prod-old-key-abc123"  # Keep old key active
  - "sk-prod-new-key-def456"  # Add new key

# Phase 2: Update clients to use new key

# Phase 3: Remove old key
keys:
  - "sk-prod-new-key-def456"  # Only new key
```

#### 3. Environment-Specific Files
```bash
# agent_config.prod.yaml
security:
  enabled: true
  type: "api_key"
  api_key: "sk-prod-key-strong-and-secure"

# agent_config.staging.yaml
security:
  enabled: true
  type: "api_key"
  api_key: "sk-staging-key-for-testing"
```

## Environment Variables

### Why Use Environment Variables?

- **Security**: Keep secrets out of configuration files
- **Flexibility**: Different values per environment
- **CI/CD Integration**: Easy deployment automation
- **Team Collaboration**: Safe to commit configs to version control

### Configuration with Environment Variables

```yaml
# agent_config.yaml (safe to commit)
security:
  enabled: true
  type: "api_key"
  api_key: "${API_KEY}"  # Will be replaced with env var value
```

```bash
# .env file (DO NOT commit)
API_KEY=sk-your-actual-secret-key-here
```

### Environment Variable Formats

#### Simple Substitution
```yaml
api_key: "${API_KEY}"
```

#### With Default Values
```yaml
api_key: "${API_KEY:sk-default-dev-key}"  # Use default if API_KEY not set
```

#### Multiple Keys from Environment
```yaml
api_key:
  keys:
    - "${PROD_API_KEY}"
    - "${STAGING_API_KEY}"
    - "${DEV_API_KEY:sk-default-dev-key}"
```

### Setting Environment Variables

#### Local Development
```bash
# .env file
API_KEY=sk-dev-key-for-local-testing

# Or export directly
export API_KEY=sk-dev-key-for-local-testing
```

#### Production Deployment
```bash
# Docker
docker run -e API_KEY=sk-prod-key-secure app:latest

# Kubernetes
kubectl create secret generic agent-secrets --from-literal=api-key=sk-prod-key

# Systemd
echo "API_KEY=sk-prod-key" >> /etc/environment
```

#### CI/CD Pipelines
```yaml
# GitHub Actions
env:
  API_KEY: ${{ secrets.API_KEY }}

# GitLab CI
variables:
  API_KEY: $API_KEY_SECRET
```

## Plugin Integration

### Enhanced Capability Context Integration

API key authentication provides comprehensive security context through the EnhancedCapabilityContext system. This context flows through all plugin executions, ensuring that plugins have consistent access to authentication and authorization information.

```python
@hookimpl
def execute_capability(self, context: EnhancedCapabilityContext) -> CapabilityResult:
    """Execute capability with API key authentication context."""

    # Access API key authentication information
    api_key_id = context.auth.metadata.get("api_key_id")
    auth_method = context.auth.method  # "api_key"

    # Validate specific scopes for API key operations
    context.require_scope("api:read")

    # Conditional logic based on API key permissions
    if context.has_scope("api:write"):
        # Allow write operations for keys with appropriate permissions
        result = self._perform_write_operation(context)
    else:
        # Restrict to read-only operations
        result = self._perform_read_operation(context)

    return result
```

### Scope Validation in Plugin Operations

Plugins can implement  authorization logic beyond basic API key validation using the scope-based authorization system.
This enables runtime permission checking and conditional logic based on the specific API key's assigned permissions.

```python
@hookimpl
def validate_plugin_access(self, context: EnhancedCapabilityContext) -> bool:
    """Custom authorization logic for API key authenticated requests."""

    # Basic API key scope validation
    if not context.has_scope("files:read"):
        return False

    # API key specific validation
    api_key_metadata = context.auth.metadata

    # Time-based restrictions for API keys
    if api_key_metadata.get("access_hours"):
        current_hour = datetime.datetime.now().hour
        allowed_hours = api_key_metadata["access_hours"]
        if current_hour not in allowed_hours:
            return False

    # Department-based access control
    key_department = api_key_metadata.get("department")
    requested_resource = context.metadata.get("resource_path", "")

    if requested_resource.startswith("/departments/"):
        resource_dept = requested_resource.split("/")[2]
        if key_department != resource_dept and not context.has_scope("admin"):
            return False

    # Rate limiting based on API key tier
    key_tier = api_key_metadata.get("tier", "basic")
    if key_tier == "basic":
        # Additional rate limiting for basic tier keys
        return self._check_basic_tier_limits(context)

    return True
```

### Plugin Configuration with API Key Scopes

Plugin configurations integrate with the API key scope system to provide automatic authorization configuration. Plugins specify
their required scopes, and the system ensures that API keys have appropriate permissions before allowing plugin execution.

```yaml
# Plugin configuration with API key scope requirements
plugins:
  - plugin_id: "system_information"
    name: "System Information"
    plugin_type: "local"
    required_scopes: ["system:read"]
    api_key_specific:
      minimum_tier: "basic"
      department_access: ["IT", "Operations"]

  - plugin_id: "external_api_client"
    name: "External API Client"
    plugin_type: "network"
    required_scopes: ["api:external", "api:read"]
    api_key_specific:
      minimum_tier: "premium"
      rate_limit_override:
        basic: 10  # requests per minute for basic keys
        premium: 50
        enterprise: 200

  - plugin_id: "file_manager"
    name: "File Manager"
    plugin_type: "local"
    required_scopes: ["files:read"]
    api_key_specific:
      sensitive_files_scope: "files:sensitive"
      bulk_operations_scope: "files:bulk"
```

### Middleware Integration for API Keys

API key authentication integrates with the context-aware middleware system to provide  security measures based on both API key
characteristics and plugin classification. The system applies appropriate middleware configurations while maintaining performance.

```yaml
# Middleware configuration with API key integration
middleware:
  - name: "timed"
    params: {}
  - name: "api_key_enhanced"
    params:
      validation_cache_ttl: 300  # Cache API key validation for 5 minutes
      scope_validation: true
      metadata_enrichment: true
  - name: "rate_limited"
    params:
      requests_per_minute: 60
      key_specific_limits:
        basic: 30
        premium: 100
        enterprise: 200
  - name: "cached"
    params:
      ttl: 300
      key_specific_ttl:
        basic: 120    # Shorter cache for basic keys
        premium: 300
        enterprise: 600

# Plugin-specific middleware overrides
plugins:
  - plugin_id: "high_volume_api"
    plugin_type: "network"
    required_scopes: ["api:external"]
    middleware_override:
      - name: "rate_limited"
        params:
          requests_per_minute: 200
          burst_size: 50
          key_specific_limits:
            enterprise: 500  # Higher limits for enterprise keys
      - name: "cached"
        params:
          ttl: 600  # Longer cache for high-volume operations
```

## Comprehensive Endpoint Protection

### Universal API Key Protection

The AgentUp Security Framework ensures that API key authentication protects all AgentUp endpoints.

**JSON-RPC Endpoint Protection**: The main JSON-RPC endpoint at `/` receives comprehensive API key authentication with proper scope
validation for all A2A protocol methods. This ensures that all agent-to-agent communication is properly authenticated and authorized.

**MCP Endpoint Security**: Previously unprotected MCP endpoints at `/mcp` now require proper API key authentication, eliminating a
critical security vulnerability. MCP operations integrate with the scope-based authorization system while maintaining protocol compliance.

**Agent Card Protection**: The agent discovery endpoint at `/.well-known/agent.json` receives appropriate protection while maintaining
A2A protocol compliance. The system ensures that agent capabilities are only exposed to properly authenticated clients.

**Push Notification Security**: Push notification configuration endpoints require API key authentication with appropriate scopes
for notification management. This prevents unauthorized notification configuration while enabling legitimate push notification operations.

### API Key Validation Across All Endpoints

The AgentUp Security Framework provides consistent API key validation across all endpoint types with appropriate performance
optimization for each operational context. The system ensures comprehensive protection while maintaining optimal performance characteristics.

Network endpoints receive enhanced validation with comprehensive scope checking and middleware protection. Local endpoints get
optimized validation that maintains security while minimizing overhead for high-frequency operations.

The validation system supports all API key location options (headers, query parameters, cookies) across all endpoint types, providing
flexible authentication approaches while maintaining security consistency.

### Scope-Based Endpoint Access Control

Different endpoints require different scope combinations based on their operational characteristics and security requirements. The system
provides  scope requirements while supporting custom configurations for specialized use cases.

```yaml
# Endpoint-specific scope requirements
endpoint_scopes:
  "/.well-known/agent.json":
    required_scopes: []  # Public discovery endpoint
    optional_scopes: ["agent:enhanced_info"]

  "/":  # JSON-RPC endpoint
    required_scopes: ["api:read"]
    method_specific:
      "capabilities": ["api:read"]
      "execute": ["plugin:execute"]
      "status": ["system:read"]

  "/mcp":  # MCP endpoint
    required_scopes: ["mcp:access"]
    method_specific:
      "tools/list": ["mcp:tools:read"]
      "tools/call": ["mcp:tools:execute"]
      "resources/list": ["mcp:resources:read"]

  "/push/configure":  # Push notification configuration
    required_scopes: ["push:configure"]
    additional_validation: true
```

## Security Best Practices

### 🔒 Key Generation

#### Strong API Keys
```bash
# Good: Long, random, prefixed
sk-8K2mNx9P7qR4sV5yA3bC6dE9fH2jK5lM8nP1qS4tU7vW0xY3zA6b

# Bad: Short, predictable, common words
password123
api-key-test
admin-key
```

#### Automated Generation
```python
# generate_api_key.py
import secrets
import string

def generate_api_key(length=32, prefix="sk-"):
    """Generate a cryptographically secure API key."""
    alphabet = string.ascii_letters + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}{key}"

# Generate 5 keys for different environments
for env in ["prod", "staging", "dev", "test", "demo"]:
    key = generate_api_key()
    print(f"{env.upper()}_API_KEY={key}")
```

### 🛡️ Storage and Transmission

#### Secure Practices
- Store in environment variables or secure vaults
- Transmit only over HTTPS
- Use headers instead of query parameters
- Implement key rotation procedures
- Monitor for unauthorized usage

#### Avoid These Mistakes
- Hardcoding keys in source code
- Committing keys to version control
- Logging keys in application logs
- Using keys in URLs or query parameters
- Sharing keys through insecure channels

### Monitoring and Auditing

AgentUp automatically logs authentication attempts:

```python
# Enable security event logging
import logging
logging.getLogger("src.agent.security").setLevel(logging.INFO)
```

Example log entries:
```
INFO:src.agent.security.utils:Security event: authentication
WARNING:src.agent.security.utils:Security event failed: authentication
```

### Key Compromise Response

If an API key is compromised:

1. **Immediately remove the key** from configuration
2. **Restart the agent** to apply changes
3. **Generate a new key** with different pattern
4. **Update all clients** with new key
5. **Monitor logs** for unauthorized access attempts
6. **Review access patterns** before compromise

```yaml
# Emergency key rotation
security:
  enabled: true
  type: "api_key"
  api_key:
    keys:
      # Remove compromised key immediately
      # - "sk-compromised-key-remove-now"  # REMOVED
      - "sk-new-secure-replacement-key"    # NEW KEY
```

## Testing and Validation

### Automated Testing Script

```bash
#!/bin/bash
# test-api-key.sh - Validate API key authentication

AGENT_URL="http://localhost:8000"
API_KEY="$1"

if [ -z "$API_KEY" ]; then
    echo "Usage: $0 <api_key>"
    echo "Example: $0 sk-your-api-key-here"
    exit 1
fi

echo "Testing API Key Authentication"
echo "=================================="

# Test 1: Discovery endpoint (should work without auth)
echo "1. Testing discovery endpoint (no auth required)..."
DISCOVERY_STATUS=$(curl -s -w "%{http_code}" "${AGENT_URL}/.well-known/agent.json" -o /dev/null)
if [ "$DISCOVERY_STATUS" = "200" ]; then
    echo "   Discovery endpoint accessible"
else
    echo "   Discovery endpoint failed ($DISCOVERY_STATUS)"
    exit 1
fi

# Test 2: Protected endpoint without key (should fail)
echo "2. Testing protected endpoint without API key..."
NO_AUTH_STATUS=$(curl -s -w "%{http_code}" "${AGENT_URL}/agent/card" -o /dev/null)
if [ "$NO_AUTH_STATUS" = "401" ]; then
    echo "   Protected endpoint correctly requires authentication"
else
    echo "   Protected endpoint should require authentication ($NO_AUTH_STATUS)"
fi

# Test 3: Protected endpoint with wrong key (should fail)
echo "3. Testing protected endpoint with invalid API key..."
WRONG_KEY_STATUS=$(curl -s -w "%{http_code}" -H "X-API-Key: invalid-key" "${AGENT_URL}/agent/card" -o /dev/null)
if [ "$WRONG_KEY_STATUS" = "401" ]; then
    echo "   Invalid API key correctly rejected"
else
    echo "   Invalid API key should be rejected ($WRONG_KEY_STATUS)"
fi

# Test 4: Protected endpoint with correct key (should work)
echo "4. Testing protected endpoint with valid API key..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "X-API-Key: ${API_KEY}" "${AGENT_URL}/agent/card")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$STATUS" = "200" ]; then
    echo "   Valid API key accepted"
    AGENT_NAME=$(echo "$BODY" | python -c "import sys, json; print(json.load(sys.stdin).get('name', 'Unknown Agent'))")
    echo "   Connected to: $AGENT_NAME"

    # Check security scheme in response
    SECURITY_SCHEME=$(echo "$BODY" | python -c "
import sys, json
data = json.load(sys.stdin)
schemes = data.get('securitySchemes', {})
if 'X-API-Key' in schemes:
    print('API Key security scheme correctly advertised')
else:
    print('Warning: API Key security scheme not found in agent card')
")
    echo "   $SECURITY_SCHEME"
else
    echo "   Valid API key rejected ($STATUS)"
    echo "   Error: $BODY"
fi

echo ""
echo "API Key testing completed!"
```

### Key Validation Script

```python
#!/usr/bin/env python3
# validate-api-key.py
import re
import sys

def validate_api_key(api_key):
    """Validate API key strength and format."""

    issues = []

    # Length check
    if len(api_key) < 8:
        issues.append("Key too short (minimum 8 characters)")

    # Weak patterns check
    weak_patterns = ['password', 'test', 'admin', 'key', '123', 'abc']
    for pattern in weak_patterns:
        if pattern.lower() in api_key.lower():
            issues.append(f"Contains weak pattern: {pattern}")

    # Character diversity check
    if not re.search(r'[A-Za-z]', api_key):
        issues.append("No letters found")

    if not re.search(r'[0-9]', api_key):
        issues.append("No numbers found")

    # Good patterns check
    good_patterns = []
    if api_key.startswith('sk-'):
        good_patterns.append("Good prefix (sk-)")

    if len(api_key) >= 20:
        good_patterns.append("Good length (20+ characters)")

    if re.search(r'[A-Z]', api_key) and re.search(r'[a-z]', api_key):
        good_patterns.append("Mixed case letters")

    return issues, good_patterns

def main():
    if len(sys.argv) != 2:
        print("Usage: python validate-api-key.py <api_key>")
        sys.exit(1)

    api_key = sys.argv[1]
    issues, good_patterns = validate_api_key(api_key)

    print(f"API Key Validation: {api_key}")
    print("=" * 50)

    if good_patterns:
        print("Strengths:")
        for pattern in good_patterns:
            print(f"   • {pattern}")

    if issues:
        print("Issues:")
        for issue in issues:
            print(f"   • {issue}")
        print("\nRecommendation: Generate a stronger API key")
        sys.exit(1)
    else:
        print("API key passes all validation checks!")

if __name__ == "__main__":
    main()
```

### Integration Testing

```python
# test_api_key_auth.py
import pytest
import httpx
from fastapi.testclient import TestClient

@pytest.fixture
def agent_app():
    """Create test agent with API key auth."""
    from src.agent.main import app
    return app

@pytest.fixture
def client(agent_app):
    """Create test client."""
    return TestClient(agent_app)

def test_api_key_authentication(client):
    """Test API key authentication flow."""

    # Test 1: Discovery endpoint (no auth required)
    response = client.get("/.well-known/agent.json")
    assert response.status_code == 200

    # Test 2: Protected endpoint without key
    response = client.get("/agent/card")
    assert response.status_code == 401

    # Test 3: Protected endpoint with invalid key
    response = client.get(
        "/agent/card",
        headers={"X-API-Key": "invalid-key"}
    )
    assert response.status_code == 401

    # Test 4: Protected endpoint with valid key
    response = client.get(
        "/agent/card",
        headers={"X-API-Key": "sk-test-key-for-testing"}
    )
    assert response.status_code == 200

    # Verify security scheme in response
    agent_card = response.json()
    assert "securitySchemes" in agent_card
    assert "X-API-Key" in agent_card["securitySchemes"]
```

## Migration and Upgrading

### From No Authentication

```yaml
# Before: No security
agent:
  name: "My Agent"

# After: API key security
agent:
  name: "My Agent"

security:
  enabled: true
  type: "api_key"
  api_key: "sk-your-new-api-key"
```

**Migration checklist:**
1. Generate strong API keys
2. Update configuration
3. Restart agent
4. Update all clients
5. Test thoroughly

### From Bearer Token to API Key

```yaml
# Before: Bearer token
security:
  enabled: true
  type: "bearer"
  bearer_token: "your-bearer-token"

# After: API key
security:
  enabled: true
  type: "api_key"
  api_key: "sk-your-api-key"
```

**Client changes:**
```bash
# Before
curl -H "Authorization: Bearer your-bearer-token" URL

# After
curl -H "X-API-Key: sk-your-api-key" URL
```
