# JWT Authentication Quick Start

**Get JWT authentication with scope-based authorization running in 5 minutes**

This guide will get you up and running with production-ready JWT authentication in AgentUp, including scope-based authorization and authentication context.

## Prerequisites

- AgentUp installed (`pip install agentup`)
- Python 3.11+ 
- Basic understanding of JWT tokens

## Step 1: Create JWT Agent

```bash
# Create a new agent with JWT authentication
agentup agent create jwt-demo --template standard

# Navigate to the agent directory
cd jwt-demo
```

## Step 2: Configure JWT Authentication

Edit `agent_config.yaml`:

```yaml
# JWT Authentication Configuration
security:
  enabled: true
  type: bearer
  bearer:
    jwt_secret: "${JWT_SECRET:demo-secret-change-in-production}"
    algorithm: HS256
    issuer: "${JWT_ISSUER:jwt-demo}"
    audience: "${JWT_AUDIENCE:agentup-jwt-demo}"

# Skills with different scope requirements
skills:
  - skill_id: public_info
    name: Public Information
    description: Available to all authenticated users
    input_mode: text
    output_mode: text

  - skill_id: basic_service
    name: Basic Service
    description: Requires 'basic' scope
    input_mode: text
    output_mode: text

  - skill_id: premium_service
    name: Premium Service
    description: Requires 'premium' scope
    input_mode: text
    output_mode: text
```

## Step 3: Set Environment Variables

Create `.env` file:

```bash
# JWT Configuration
JWT_SECRET=demo-secret-change-in-production
JWT_ISSUER=jwt-demo
JWT_AUDIENCE=agentup-jwt-demo
```

## Step 4: Create Scope-Aware Handlers

Create `jwt_handlers.py`:

```python
from typing import Any
from agent.handlers import register_handler

@register_handler("public_info")
async def handle_public_info(task: Any, context=None) -> str:
    """Public information - no scopes required."""
    user_id = context.user_id if context else "anonymous"
    return f"📋 Public information accessible to {user_id}"

@register_handler("basic_service")
async def handle_basic_service(task: Any, context=None) -> str:
    """Basic service requiring 'basic' scope."""
    
    # Check if user has required scope
    if context and hasattr(context, "has_scope") and not context.has_scope("basic"):
        if not context.is_authenticated:
            return "❌ Authentication required for basic service."
        else:
            scopes = ", ".join(context.user_scopes) if context.user_scopes else "none"
            return f"❌ Access denied. Requires 'basic' scope. You have: {scopes}"
    
    user_id = context.user_id if context else "user"
    return f"✅ Basic service activated for {user_id}"

@register_handler("premium_service")
async def handle_premium_service(task: Any, context=None) -> str:
    """Premium service requiring 'premium' scope."""
    
    # Check if user has required scope
    if context and hasattr(context, "has_scope") and not context.has_scope("premium"):
        if not context.is_authenticated:
            return "❌ Authentication required for premium service."
        elif context.has_scope("basic"):
            return "❌ Access denied. Premium service requires 'premium' scope. Consider upgrading!"
        else:
            scopes = ", ".join(context.user_scopes) if context.user_scopes else "none"
            return f"❌ Access denied. Requires 'premium' scope. You have: {scopes}"
    
    user_id = context.user_id if context else "user"
    return f"🚀 Premium service activated for {user_id} with advanced features!"
```

## Step 5: Import Handlers

Update `__init__.py`:

```python
# Import JWT handlers to register them
from . import jwt_handlers  # noqa: F401
```

## Step 6: Start the Agent

```bash
# Install dependencies
uv sync

# Start the agent
agentup agent serve --port 8000
```

You should see:
```
INFO:agent.api.app:Starting JWT Demo Agent v0.1.0
INFO:agent.security.manager:Security manager initialized - enabled: True, primary auth: bearer
INFO:agent.api.app:Security enabled with bearer authentication
```

## Step 7: Generate Test Tokens

```bash
# Generate token with no scopes (public access only)
python -c "
import jwt, time
payload = {
    'sub': 'public-user',
    'iss': 'jwt-demo', 
    'aud': 'agentup-jwt-demo',
    'iat': int(time.time()),
    'exp': int(time.time()) + 3600,
    'scope': ''
}
token = jwt.encode(payload, 'demo-secret-change-in-production', algorithm='HS256')
print('PUBLIC TOKEN:', token)
"

# Generate token with basic scope
python -c "
import jwt, time
payload = {
    'sub': 'basic-user',
    'iss': 'jwt-demo',
    'aud': 'agentup-jwt-demo', 
    'iat': int(time.time()),
    'exp': int(time.time()) + 3600,
    'scope': 'basic'
}
token = jwt.encode(payload, 'demo-secret-change-in-production', algorithm='HS256')
print('BASIC TOKEN:', token)
"

# Generate token with premium scope
python -c "
import jwt, time
payload = {
    'sub': 'premium-user',
    'iss': 'jwt-demo',
    'aud': 'agentup-jwt-demo',
    'iat': int(time.time()), 
    'exp': int(time.time()) + 3600,
    'scope': 'basic,premium'
}
token = jwt.encode(payload, 'demo-secret-change-in-production', algorithm='HS256')
print('PREMIUM TOKEN:', token)
"
```

## Step 8: Test Authentication

```bash
# Test without authentication (should fail)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "test-1",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "test"}],
        "messageId": "msg-1"
      },
      "skillId": "public_info"
    }
  }'
# Should return 401 Unauthorized

# Test with valid token (replace TOKEN with actual token from step 7)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send", 
    "id": "test-2",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "test"}],
        "messageId": "msg-2"
      },
      "skillId": "public_info"
    }
  }'
# Should return success with public information
```

## Step 9: Test Scope-Based Authorization

```bash
# Test basic service with basic token
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer BASIC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "test-3", 
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "test"}],
        "messageId": "msg-3"
      },
      "skillId": "basic_service"
    }
  }'
# Should succeed: "✅ Basic service activated for basic-user"

# Test premium service with basic token (should fail)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer BASIC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "test-4",
    "params": {
      "message": {
        "role": "user", 
        "parts": [{"kind": "text", "text": "test"}],
        "messageId": "msg-4"
      },
      "skillId": "premium_service"
    }
  }'
# Should fail: "❌ Access denied. Premium service requires 'premium' scope"

# Test premium service with premium token (should succeed)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer PREMIUM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "test-5",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "test"}],
        "messageId": "msg-5"
      },
      "skillId": "premium_service"
    }
  }'
# Should succeed: "🚀 Premium service activated for premium-user with advanced features!"
```

## Step 10: Verify Agent Discovery

```bash
# Check agent discovery endpoint
curl http://localhost:8000/.well-known/agent.json | jq .

# Should show security schemes:
# {
#   "securitySchemes": {
#     "BearerAuth": {
#       "type": "http",
#       "scheme": "bearer",
#       "description": "Bearer token for authentication"
#     }
#   },
#   "security": [{"BearerAuth": []}],
#   "skills": [...]
# }
```

## 🎉 Success!

You now have a working JWT authentication system with scope-based authorization! Your agent:

- ✅ **Validates JWT tokens** with signature verification
- ✅ **Extracts user information** from JWT claims  
- ✅ **Enforces scope-based authorization** at the handler level
- ✅ **Provides authentication context** to handlers automatically
- ✅ **Advertises security schemes** correctly in agent discovery

## Next Steps

### Enhanced Implementation
- **[Full JWT Guide](jwt-authentication.md)** - Complete production implementation
- **[Token Generation Tools](jwt-authentication.md#token-generation)** - Built-in JWT generators
- **[Advanced Scope Patterns](jwt-authentication.md#scope-based-authorization)** - Hierarchical scopes

### Production Deployment  
- **[Environment Configuration](jwt-authentication.md#production-deployment)** - Production setup
- **[Docker Deployment](jwt-authentication.md#docker-deployment)** - Containerized deployment
- **[Security Best Practices](jwt-authentication.md#security-best-practices)** - Production security

### Integration
- **[OAuth2 Providers](oauth2.md)** - Enterprise OAuth2 integration
- **[Custom Claims](jwt-authentication.md#jwt-configuration)** - Custom JWT claims processing
- **[Monitoring Setup](../configuration/monitoring.md)** - Authentication monitoring

## Troubleshooting

### Common Issues

**❌ "Bearer token is required when using bearer auth type"**
- Ensure `jwt_secret` is configured in the `bearer` section
- Check that environment variables are loaded correctly

**❌ "Invalid JWT token format"**  
- Verify Authorization header format: `Bearer <token>`
- Check that JWT token has 3 parts separated by dots

**❌ "JWT signature verification failed"**
- Ensure JWT secret matches between generation and validation
- Verify algorithm matches (HS256, RS256, etc.)

**❌ "Access denied" for scoped services**
- Check that token includes required scopes in `scope` claim
- Verify scope checking logic in handlers

### Debug Commands

```bash
# Validate agent configuration
python -c "
from agent.config.loader import load_config
from agent.security.manager import SecurityManager
config = load_config()
sm = SecurityManager(config)
print('✅ Configuration valid')
"

# Decode JWT token (replace TOKEN)
python -c "
import jwt
token = 'TOKEN'
print('Header:', jwt.get_unverified_header(token))
print('Payload:', jwt.decode(token, options={'verify_signature': False}))
"
```

---

**Quick Links:**
- [Full JWT Authentication Guide](jwt-authentication.md)
- [Authentication Overview](index.md)
- [OAuth2 Setup](oauth2.md)
- [Troubleshooting](../troubleshooting/authentication.md)