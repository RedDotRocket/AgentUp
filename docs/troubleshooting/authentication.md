# Authentication Troubleshooting

**Quick solutions to common authentication problems**

This guide helps you diagnose and fix authentication issues in AgentUp. Each problem includes symptoms, causes, and step-by-step solutions.

## Quick Diagnostic Steps

Before diving into specific issues, run these quick checks:

### 1. Verify Configuration
```bash
# Check your configuration is valid
uv run python -c "
from src.agent.config import load_config
from src.agent.security import validate_security_config
try:
    config = load_config()
    validate_security_config(config.get('security', {}))
    print('✓ Configuration is valid')
except Exception as e:
    print(f'✗ Configuration error: {e}')
"
```

### 2. Check Agent Logs
```bash
# Start agent with debug logging
uv run uvicorn src.agent.main:app --reload --log-level debug
```

### 3. Test Discovery Endpoint
```bash
# This should always work (no auth required)
curl http://localhost:8000/.well-known/agent.json
```

## Common Problems

### API Key Authentication

#### Problem: "Unauthorized" with Correct API Key

**Symptoms:**
- 401 Unauthorized response
- Correct API key in configuration
- Agent starts successfully

**Possible Causes:**
1. API key not sent in correct header
2. Typo in API key value
3. Agent not restarted after config change
4. API key rejected as "weak"

**Solutions:**

**Step 1: Verify Header Format**
```bash
# Correct format
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/agent/card

# Common mistakes
curl -H "Authorization: your-api-key-here"  # ✗ Wrong header
curl -H "Api-Key: your-api-key-here"        # ✗ Wrong header name
curl -H "X-API-Key: Bearer your-api-key"    # ✗ Don't use "Bearer"
```

**Step 2: Check API Key Strength**
```bash
# Test if your API key is being rejected
uv run python -c "
from src.agent.security.validators import SecurityConfigValidator
config = {'enabled': True, 'type': 'api_key', 'api_key': 'YOUR_KEY_HERE'}
try:
    SecurityConfigValidator.validate_security_config(config)
    print('✓ API key is valid')
except Exception as e:
    print(f'✗ API key rejected: {e}')
"
```

**Step 3: Restart Agent**
Security configuration is loaded at startup. Always restart after changes:
```bash
# Stop current agent (Ctrl+C) then restart
uv run uvicorn src.agent.main:app --reload --port 8000
```

#### Problem: "API key appears to contain weak pattern"

**Symptoms:**
- Agent fails to start
- Error message about weak pattern
- Common words in API key

**Cause:** AgentUp rejects API keys containing common weak patterns like "password", "test", "admin", etc.

**Solution:**
Use a strong, randomly generated API key:
```bash
# Generate a strong API key
python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"

# Example strong keys
sk-strong-api-key-abcd1234xyz789
sk-2Kj9mNxP7qR4sV8yA3bC6dE9fH2jK5lM8nP1qS4tU7vW0xY3zA6b
```

#### Problem: "Security manager not initialized"

**Symptoms:**
- 500 Internal Server Error
- Error in logs about security manager

**Causes:**
1. Security configuration missing
2. Invalid YAML syntax
3. Startup error not caught

**Solutions:**

**Step 1: Validate YAML Syntax**
```bash
# Check YAML syntax
python -c "
import yaml
with open('agent_config.yaml') as f:
    try:
        yaml.safe_load(f)
        print('✓ YAML syntax is valid')
    except yaml.YAMLError as e:
        print(f'✗ YAML syntax error: {e}')
"
```

**Step 2: Check Security Section**
Ensure you have a complete security section:
```yaml
security:
  enabled: true
  type: "api_key"
  api_key: "sk-your-strong-key-here"
```

### 🎫 Bearer Token Authentication

#### Problem: "Invalid bearer token format"

**Symptoms:**
- 401 Unauthorized with bearer tokens
- Valid JWT tokens being rejected

**Causes:**
1. Missing "Bearer" prefix
2. Extra spaces in Authorization header
3. Token not base64-encoded properly

**Solutions:**

**Step 1: Check Header Format**
```bash
# Correct format
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." http://localhost:8000/agent/card

# Common mistakes
curl -H "Authorization: eyJhbGciOiJIUzI1NiIs..."          # ✗ Missing "Bearer"
curl -H "Authorization:Bearer eyJhbGciOiJIUzI1NiIs..."     # ✗ Missing space
curl -H "Authorization: bearer eyJhbGciOiJIUzI1NiIs..."    # ✗ Lowercase "bearer"
```

**Step 2: Validate JWT Token**
```bash
# Check if your JWT is valid using jwt.io or:
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | python -m json.tool
```

#### Problem: Bearer Token Configuration Not Working

**Symptoms:**
- Agent starts but bearer auth doesn't work
- API key mode still being used

**Cause:** Incorrect configuration format

**Solution:**
```yaml
# Correct bearer token configuration
security:
  enabled: true
  type: "bearer"  # Make sure type is "bearer"
  bearer_token: "your-bearer-token-here"

# Alternative format
security:
  enabled: true
  type: "bearer"
  bearer:
    bearer_token: "your-bearer-token-here"
```

### 🔑 OAuth2 Authentication

#### Problem: "JWT validation failed"

**Symptoms:**
- Valid OAuth2 tokens being rejected
- Error logs mention JWT validation
- JWKS or signature issues

**Possible Causes:**
1. Incorrect JWKS URL
2. Algorithm mismatch
3. Issuer/audience validation failure
4. Expired tokens

**Solutions:**

**Step 1: Verify JWKS URL**
```bash
# Test JWKS endpoint accessibility
curl "https://your-provider.com/.well-known/jwks.json"

# Should return JSON with "keys" array
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "key-id",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

**Step 2: Check Token Claims**
```bash
# Decode JWT header and payload (without verification)
TOKEN="your.jwt.token"
echo $TOKEN | cut -d. -f1 | base64 -d | jq .  # Header
echo $TOKEN | cut -d. -f2 | base64 -d | jq .  # Payload
```

**Step 3: Verify Configuration Matches Token**
```yaml
oauth2:
  jwt_issuer: "https://accounts.google.com"      # Must match token "iss" claim
  jwt_audience: "your-client-id"                 # Must match token "aud" claim
  jwt_algorithm: "RS256"                         # Must match token header "alg"
```

#### Problem: "OAuth2 token introspection failed"

**Symptoms:**
- Introspection strategy not working
- Network or authentication errors

**Causes:**
1. Incorrect client credentials
2. Wrong introspection endpoint
3. Network connectivity issues
4. Token not supported by provider

**Solutions:**

**Step 1: Test Introspection Manually**
```bash
# Test introspection endpoint directly
curl -u "client_id:client_secret" \
     -d "token=YOUR_ACCESS_TOKEN" \
     -d "token_type_hint=access_token" \
     https://your-provider.com/oauth/introspect

# Should return something like:
{
  "active": true,
  "client_id": "your-client-id",
  "username": "user@example.com",
  "scope": "read write",
  "exp": 1640995200
}
```

**Step 2: Verify Client Credentials**
```bash
# Test client credentials separately
curl -u "client_id:client_secret" \
     -d "grant_type=client_credentials" \
     https://your-provider.com/oauth/token
```

**Step 3: Check Network Connectivity**
```bash
# Test from your server
curl -v https://your-provider.com/oauth/introspect
```

#### Problem: "Required scopes not met"

**Symptoms:**
- 401 Unauthorized despite valid token
- Scope-related error messages

**Causes:**
1. Token missing required scopes
2. Scope claim format mismatch
3. Configuration too restrictive

**Solutions:**

**Step 1: Check Token Scopes**
```bash
# Decode token to see scopes
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | jq '.scope, .scopes'
```

**Step 2: Adjust Configuration**
```yaml
oauth2:
  required_scopes: ["read"]        # Token must have ALL these scopes
  allowed_scopes: ["read", "write", "admin"]  # Token can have any of these
```

**Step 3: Provider-Specific Scope Formats**
```yaml
# Auth0 format
required_scopes: ["read:agents", "write:agents"]

# Google format  
required_scopes: ["https://www.googleapis.com/auth/userinfo.email"]

# Azure AD format
required_scopes: ["api://your-app-id/Agent.Read"]
```

### 🌐 General Authentication Issues

#### Problem: Authentication Working Inconsistently

**Symptoms:**
- Sometimes works, sometimes doesn't
- Different behavior across environments

**Causes:**
1. Environment variable issues
2. Load balancer problems
3. Cached configurations
4. Clock synchronization (for JWT exp claims)

**Solutions:**

**Step 1: Check Environment Variables**
```bash
# Verify environment variables are set
echo "OAUTH_CLIENT_ID: ${OAUTH_CLIENT_ID}"
echo "API_KEY: ${API_KEY}"

# Check if variables are being substituted
uv run python -c "
from src.agent.config import load_config
config = load_config()
print(config.get('security', {}))
"
```

**Step 2: Check System Clock**
```bash
# JWT tokens are time-sensitive
date
ntpdate -q pool.ntp.org  # Check time sync
```

#### Problem: "Security event failed" in Logs

**Symptoms:**
- Warning messages in logs
- Authentication still works

**Cause:** This is usually informational logging, not an error

**Explanation:**
AgentUp logs all authentication attempts for security auditing:
- `Security event: authentication` = successful auth
- `Security event failed: authentication` = failed auth attempt

These logs are normal and help with security monitoring.

#### Problem: Performance Issues with Authentication

**Symptoms:**
- Slow response times
- Timeouts on auth requests

**Causes:**
1. JWKS fetching delays
2. Introspection endpoint latency
3. Network issues

**Solutions:**

**Step 1: Use JWT Validation (Faster)**
```yaml
# JWT validation is faster than introspection
oauth2:
  validation_strategy: "jwt"  # Instead of "introspection"
  jwks_url: "https://provider.com/.well-known/jwks.json"
```

**Step 2: Cache JWKS Keys**
AgentUp automatically caches JWKS keys, but you can verify:
```bash
# Check logs for JWKS fetch messages
grep "JWKS" agent.log
```

**Step 3: Use Hybrid Strategy**
```yaml
# Try JWT first, fallback to introspection
oauth2:
  validation_strategy: "both"
```

## Debug Mode

Enable detailed authentication debugging:

```python
# Add to your agent startup
import logging
logging.getLogger("src.agent.security").setLevel(logging.DEBUG)
logging.getLogger("authlib").setLevel(logging.DEBUG)
```

Or set environment variable:
```bash
export PYTHONPATH=. 
export LOG_LEVEL=DEBUG
uv run uvicorn src.agent.main:app --reload --log-level debug
```

## Testing Tools

### Authentication Test Script

```bash
#!/bin/bash
# auth-test.sh - Comprehensive authentication testing

AGENT_URL="http://localhost:8000"
AUTH_TYPE="$1"
CREDENTIAL="$2"

if [ -z "$AUTH_TYPE" ] || [ -z "$CREDENTIAL" ]; then
    echo "Usage: $0 <api_key|bearer|oauth2> <credential>"
    exit 1
fi

echo "Testing ${AUTH_TYPE} authentication..."

case $AUTH_TYPE in
    "api_key")
        HEADER="X-API-Key: ${CREDENTIAL}"
        ;;
    "bearer"|"oauth2")
        HEADER="Authorization: Bearer ${CREDENTIAL}"
        ;;
    *)
        echo "Invalid auth type. Use: api_key, bearer, or oauth2"
        exit 1
        ;;
esac

# Test 1: Discovery (should always work)
echo "1. Testing discovery endpoint..."
STATUS=$(curl -s -w "%{http_code}" "${AGENT_URL}/.well-known/agent.json" -o /dev/null)
if [ "$STATUS" = "200" ]; then
    echo "   ✓ Discovery endpoint working"
else
    echo "   ✗ Discovery endpoint failed ($STATUS)"
fi

# Test 2: Protected endpoint without auth (should fail)
echo "2. Testing protected endpoint without auth..."
STATUS=$(curl -s -w "%{http_code}" "${AGENT_URL}/agent/card" -o /dev/null)
if [ "$STATUS" = "401" ]; then
    echo "   ✓ Protected endpoint correctly requiring auth"
else
    echo "   ✗ Protected endpoint not requiring auth ($STATUS)"
fi

# Test 3: Protected endpoint with auth (should work)
echo "3. Testing protected endpoint with auth..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$HEADER" "${AGENT_URL}/agent/card")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$STATUS" = "200" ]; then
    echo "   ✓ Authentication successful"
    echo "   📝 Agent: $(echo "$BODY" | jq -r '.name // "Unknown"')"
else
    echo "   ✗ Authentication failed ($STATUS)"
    echo "   📝 Error: $(echo "$BODY" | jq -r '.detail // "Unknown error"')"
fi

echo "Authentication testing complete!"
```

### JWT Token Generator

```python
#!/usr/bin/env python3
# generate-test-jwt.py
import time
import json
from authlib.jose import jwt

def generate_test_token(secret="test-secret", algorithm="HS256"):
    """Generate a test JWT token for debugging."""
    
    payload = {
        "sub": "test-user-123",
        "iss": "https://test-provider.com",
        "aud": "test-agent",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,  # 1 hour
        "scope": "agent:read agent:write",
        "scopes": ["agent:read", "agent:write"],
        "email": "test@example.com",
        "name": "Test User"
    }
    
    token = jwt.encode(
        header={"alg": algorithm, "typ": "JWT"},
        payload=payload,
        key=secret
    )
    
    return token.decode('utf-8') if isinstance(token, bytes) else token

if __name__ == "__main__":
    token = generate_test_token()
    print(f"Test JWT Token:\n{token}")
    
    # Decode for verification
    payload = jwt.decode(token, "test-secret")
    print(f"\nDecoded Payload:\n{json.dumps(payload, indent=2)}")
```

## Getting Help

If you're still experiencing issues:

1. **Check Agent Logs**: Look for specific error messages
2. **Verify Configuration**: Use the validation scripts above
3. **Test Components**: Use the testing tools provided
4. **Review Documentation**: Check the relevant auth guide
5. **Create Issue**: [Report bugs](https://github.com/rdrocket-projects/AgentUp/issues) with:
   - Agent configuration (remove secrets!)
   - Error logs
   - Steps to reproduce

## Next Steps

- **[Authentication Quick Start](../authentication/quick-start.md)** - Basic setup
- **[OAuth2 Comprehensive Guide](../authentication/oauth2.md)** - Advanced OAuth2
- **[Configuration Reference](../reference/config-schema.md)** - All options
- **[Security Best Practices](../configuration/security.md)** - Production tips

---

**Quick Links:**
- 🏠 [Documentation Home](../index.md)
- [Authentication Guides](../authentication/quick-start.md)
- [Configuration Reference](../reference/config-schema.md)