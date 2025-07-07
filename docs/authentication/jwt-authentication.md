# JWT Authentication with Scope-Based Authorization

**Production-ready JWT Bearer token authentication with advanced scope-based authorization**

JWT (JSON Web Token) authentication in AgentUp provides enterprise-grade security with flexible scope-based authorization. This comprehensive guide covers setup, configuration, scope-based access control, and production deployment patterns.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [JWT Configuration](#jwt-configuration)
- [Scope-Based Authorization](#scope-based-authorization)
- [Authentication Context](#authentication-context)
- [Handler Implementation](#handler-implementation)
- [Token Generation](#token-generation)
- [Testing and Validation](#testing-and-validation)
- [Production Deployment](#production-deployment)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

AgentUp's JWT authentication system provides:

### 🔐 **Core Security Features**
- **JWT Signature Validation** - RFC 7519 compliant with cryptographic verification
- **Claims Validation** - Issuer, audience, expiration, and custom claims
- **Scope-Based Authorization** - Fine-grained permission control
- **Thread-Safe Context** - Authentication info propagated to handlers
- **Auto-Application System** - Middleware and state management auto-applied

### 🎯 **Authorization Architecture**
- **Two-Layer Security** - Authentication (hard gate) + Authorization (application logic)
- **Plugin-First Design** - Authorization logic in plugins, not core framework
- **Context Propagation** - Authentication scopes passed to handlers via SkillContext
- **Graceful Fallbacks** - Handlers work with or without authentication context

### 🚀 **Production Ready**
- **Environment Variable Support** - Secure secret management
- **A2A Protocol Compliance** - Proper security scheme advertising
- **Performance Optimized** - Efficient validation and caching
- **Enterprise Integration** - Works with OAuth2 providers and custom JWT systems

## Quick Start

### Step 1: Agent Configuration

Create `agent_config.yaml` with JWT Bearer authentication:

```yaml
# JWT Test Agent Configuration
agent:
  name: JWT Test Agent
  description: Agent demonstrating JWT authentication and scope-based authorization
  version: 0.1.0

# JWT Bearer Authentication Configuration
security:
  enabled: true
  type: bearer
  bearer:
    # JWT secret for HS256 algorithm (symmetric)
    jwt_secret: "${JWT_SECRET:test-secret-key-change-in-production}"
    
    # JWT algorithm (HS256 for symmetric, RS256 for asymmetric)
    algorithm: HS256
    
    # Expected issuer of the JWT token
    issuer: "${JWT_ISSUER:test-issuer}"
    
    # Expected audience of the JWT token
    audience: "${JWT_AUDIENCE:agentup-jwt-test}"
    
    # Optional: For RS256, specify JWKS URL or public key
    # jwks_url: "${JWKS_URL}"
    # public_key: "${JWT_PUBLIC_KEY}"

# Skills with different scope requirements
skills:
  - skill_id: public_echo
    name: Public Echo
    description: Echo service available to all authenticated users
    tags: [public, basic]
    input_mode: text
    output_mode: text
    # No scopes required - just authentication

  - skill_id: basic_assistant
    name: Basic Assistant
    description: Basic AI assistant requiring 'basic' scope
    tags: [ai, assistant, scoped]
    input_mode: text
    output_mode: text
    # Requires 'basic' scope

  - skill_id: premium_analyzer
    name: Premium Data Analyzer
    description: Advanced data analysis requiring 'premium' scope
    tags: [ai, analysis, premium, scoped]
    input_mode: text
    output_mode: text
    # Requires 'premium' scope

  - skill_id: admin_status
    name: Admin Status
    description: System status and configuration requiring 'admin' scope
    tags: [admin, system, scoped]
    input_mode: text
    output_mode: text
    # Requires 'admin' scope
```

### Step 2: Environment Variables

Create `.env` file with JWT configuration:

```bash
# JWT Configuration
JWT_SECRET=super-secret-jwt-key-for-testing-only-change-in-production
JWT_ISSUER=test-issuer
JWT_AUDIENCE=agentup-jwt-test

# AI Provider (optional)
OLLAMA_BASE_URL=http://localhost:11434

# Logging
LOG_LEVEL=INFO

# Development settings
DEBUG=true
RELOAD=true
```

### Step 3: Start the Agent

```bash
# Navigate to your agent directory
cd my-jwt-agent

# Install dependencies (agentup package provides all functionality)
uv sync

# Start the agent server
agentup agent serve --port 8000
```

### Step 4: Generate Test Tokens

Use the built-in JWT generator to create test tokens:

```bash
# Generate token with basic scope
python -m agentup.tools.jwt_generator --scopes "basic" --user-id "basic-user"

# Generate token with premium scope
python -m agentup.tools.jwt_generator --scopes "basic,premium" --user-id "premium-user"

# Generate token with admin scope
python -m agentup.tools.jwt_generator --scopes "basic,premium,admin" --user-id "admin-user"
```

### Step 5: Test Authentication

```bash
# Test with basic scope token
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "test-1",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "hello"}],
        "messageId": "msg-1"
      },
      "skillId": "basic_assistant"
    }
  }'
```

## JWT Configuration

### Symmetric Key Configuration (HS256)

For development and simple deployments:

```yaml
security:
  enabled: true
  type: bearer
  bearer:
    jwt_secret: "${JWT_SECRET}"
    algorithm: HS256
    issuer: "${JWT_ISSUER}"
    audience: "${JWT_AUDIENCE}"
```

### Asymmetric Key Configuration (RS256)

For production deployments with key rotation:

```yaml
security:
  enabled: true
  type: bearer
  bearer:
    algorithm: RS256
    issuer: "${JWT_ISSUER}"
    audience: "${JWT_AUDIENCE}"
    
    # Option 1: JWKS URL (recommended)
    jwks_url: "${JWKS_URL}"
    
    # Option 2: Static public key
    public_key: "${JWT_PUBLIC_KEY}"
```

### Environment Variable Configuration

```bash
# .env file for development
JWT_SECRET=your-development-secret-key
JWT_ISSUER=https://your-dev-app.com
JWT_AUDIENCE=your-agent-dev

# Production environment variables
JWT_SECRET=your-super-secure-production-secret
JWT_ISSUER=https://your-production-app.com
JWT_AUDIENCE=your-agent-prod
JWKS_URL=https://your-auth-provider.com/.well-known/jwks.json
```

## Scope-Based Authorization

### Scope Design Patterns

AgentUp implements a hierarchical scope system:

```yaml
# Scope hierarchy example
scopes:
  - public      # No additional permissions (just authentication)
  - basic       # Basic features (includes public)
  - premium     # Premium features (includes basic)
  - admin       # Administrative features (includes all)
```

### JWT Token Structure with Scopes

```json
{
  "sub": "user123",
  "iss": "your-app",
  "aud": "agentup-jwt-test",
  "iat": 1640995200,
  "exp": 1640998800,
  "scope": "basic,premium",        // Space or comma-delimited scopes
  "user_id": "user123",
  "email": "user@example.com",
  "name": "John Doe"
}
```

### Scope-Based Skill Configuration

Define skills with different access levels:

```yaml
skills:
  # Public skill - all authenticated users
  - skill_id: public_echo
    name: Public Echo
    description: Available to all authenticated users
    # No scope requirements specified

  # Basic tier skill  
  - skill_id: basic_assistant
    name: Basic Assistant
    description: Requires 'basic' scope
    # Handler will check for 'basic' scope

  # Premium tier skill
  - skill_id: premium_analyzer
    name: Premium Analyzer  
    description: Requires 'premium' scope
    # Handler will check for 'premium' scope

  # Administrative skill
  - skill_id: admin_status
    name: Admin Status
    description: Requires 'admin' scope
    # Handler will check for 'admin' scope
```

## Authentication Context

### SkillContext System

AgentUp automatically provides authentication information to handlers via `SkillContext`:

```python
from typing import Any
from agent.handlers import register_handler

@register_handler("basic_assistant")
async def handle_basic_assistant(task: Any, context=None) -> str:
    """Basic AI assistant requiring 'basic' scope."""
    
    # Authentication context is automatically provided
    if context and hasattr(context, "has_scope"):
        # Check if user has required scope
        if not context.has_scope("basic"):
            if not context.is_authenticated:
                return "❌ Authentication required to access the basic assistant."
            else:
                available_scopes = ", ".join(context.user_scopes) if context.user_scopes else "none"
                return f"❌ Access denied. This feature requires 'basic' scope. You have: {available_scopes}"
    
    # Authorization passed - provide service
    user_id = context.user_id if context else "anonymous"
    return f"👋 Hello {user_id}! I'm your basic AI assistant. How can I help you today?"
```

### SkillContext Properties

The `SkillContext` object provides:

```python
class SkillContext:
    # Authentication status
    is_authenticated: bool          # True if user is authenticated
    
    # User information  
    user_id: str | None            # User ID from JWT 'sub' claim
    user_scopes: set[str]          # Set of user scopes
    
    # Authorization methods
    def has_scope(self, scope: str) -> bool:
        """Check if user has specific scope"""
        return scope in self.user_scopes
    
    def has_any_scope(self, scopes: list[str]) -> bool:
        """Check if user has any of the specified scopes"""
        return any(scope in self.user_scopes for scope in scopes)
    
    def has_all_scopes(self, scopes: list[str]) -> bool:
        """Check if user has all specified scopes"""
        return all(scope in self.user_scopes for scope in scopes)
```

### Auto-Application System

AgentUp automatically applies authentication context to all handlers:

```python
# This happens automatically - no decorators needed!
def register_handler(skill_id: str):
    def decorator(func: Callable[[Task], str]):
        # Authentication context automatically applied
        wrapped_func = _apply_auth_to_handler(func, skill_id)
        # Middleware automatically applied based on config
        wrapped_func = _apply_middleware_to_handler(wrapped_func, skill_id)
        # State management automatically applied based on config
        wrapped_func = _apply_state_to_handler(wrapped_func, skill_id)
        _handlers[skill_id] = wrapped_func
        return wrapped_func
    return decorator
```

## Handler Implementation

### Public Handler (No Scopes Required)

```python
@register_handler("public_echo")
async def handle_public_echo(task: Any, context=None) -> str:
    """Public echo service available to all authenticated users."""
    
    # Extract message from task
    user_message = _extract_user_message(task)
    
    # Get user ID from context if available
    user_id = "anonymous"
    if context and hasattr(context, "user_id"):
        user_id = context.user_id or "anonymous"
    
    return f"Echo: {user_message} (from user {user_id})"
```

### Basic Scope Handler

```python
@register_handler("basic_assistant")
async def handle_basic_assistant(task: Any, context=None) -> str:
    """Basic AI assistant requiring 'basic' scope."""
    
    # Check if user has required scope
    if context and hasattr(context, "has_scope") and not context.has_scope("basic"):
        if not context.is_authenticated:
            return "❌ Authentication required to access the basic assistant."
        else:
            available_scopes = ", ".join(context.user_scopes) if context.user_scopes else "none"
            return f"❌ Access denied. This feature requires 'basic' scope. You have: {available_scopes}"
    
    # Extract user message and provide service
    user_message = _extract_user_message(task)
    user_id = context.user_id if context else "user"
    
    # Simple AI-like responses
    responses = {
        "weather": "🌤️ The weather is looking great today! Perfect for productivity.",
        "hello": f"👋 Hello {user_id}! I'm your basic AI assistant. How can I help you today?",
        "help": "I can help with basic queries like weather, time, simple questions, and friendly conversation.",
        "time": "🕐 It's always a good time to be productive!",
    }
    
    # Simple keyword matching
    for keyword, response in responses.items():
        if keyword in user_message.lower():
            return response
    
    return f"I'm a basic AI assistant helping {user_id}. I can answer simple questions about weather, time, and provide general assistance. What would you like to know?"
```

### Premium Scope Handler

```python
@register_handler("premium_analyzer")
async def handle_premium_analyzer(task: Any, context=None) -> str:
    """Premium data analyzer requiring 'premium' scope."""
    
    # Check if user has required scope
    if context and hasattr(context, "has_scope") and not context.has_scope("premium"):
        if not context.is_authenticated:
            return "❌ Authentication required to access the premium analyzer."
        elif context.has_scope("basic"):
            return "❌ Access denied. Premium analyzer requires 'premium' scope. Consider upgrading your access level."
        else:
            available_scopes = ", ".join(context.user_scopes) if context.user_scopes else "none"
            return f"❌ Access denied. This feature requires 'premium' scope. You have: {available_scopes}"
    
    user_message = _extract_user_message(task)
    user_id = context.user_id if context else "user"
    
    # Advanced analysis responses
    if "data" in user_message.lower():
        return f"""📊 **Premium Data Analysis Report** (for {user_id})
        
🔍 **Analysis Type**: Advanced Data Trends
📈 **Insights**: Based on sophisticated algorithms available to premium users
💡 **Recommendations**: 
   - Data shows positive trending patterns
   - Consider implementing advanced optimization strategies
   - Premium-level insights suggest 15% improvement potential
   
✅ **Premium Feature**: Multi-dimensional analysis complete
🎯 **Confidence Level**: 94% (premium-grade accuracy)
        """
    
    return f"""🚀 **Premium Analyzer Active** (User: {user_id})

I'm your premium AI analyst with access to advanced features:
• Advanced pattern recognition
• Multi-dimensional data analysis  
• Predictive modeling capabilities
• Priority processing queue

What would you like me to analyze with premium-level insights?"""
```

### Admin Scope Handler

```python
@register_handler("admin_status")
async def handle_admin_status(task: Any, context=None) -> str:
    """Admin system status requiring 'admin' scope."""
    
    # Check if user has required scope
    if context and hasattr(context, "has_scope") and not context.has_scope("admin"):
        if not context.is_authenticated:
            return "❌ Authentication required for system administration."
        else:
            available_scopes = ", ".join(context.user_scopes) if context.user_scopes else "none"
            return f"❌ Administrative access denied. Requires 'admin' scope. Current scopes: {available_scopes}"
    
    user_message = _extract_user_message(task)
    user_id = context.user_id if context else "admin"
    user_scopes = context.user_scopes if context else ["admin"]
    
    # Admin-specific responses
    if "config" in user_message.lower():
        return f"""⚙️ **System Configuration** (Admin: {user_id})
        
🔧 **Agent Configuration**:
   - Name: JWT Test Agent
   - Version: 0.1.0
   - Authentication: JWT Bearer (enabled)
   - Security Level: High
   
🔐 **Security Status**:
   - Authentication: ✅ Active
   - Scope Validation: ✅ Active  
   - Admin User: {user_id}
   - Session Scopes: {', '.join(user_scopes)}
   
📊 **System Health**: All systems operational
        """
    
    return f"""🔧 **Administrative System Status** (Admin: {user_id})

🟢 **System Status**: Operational
🔐 **Security**: JWT Authentication Active
👥 **Current Session**: Admin user '{user_id}'
🎯 **Access Level**: Administrator ({', '.join(user_scopes)})

**Available Admin Commands**:
• "show config" - Display system configuration
• "system health" - Check system health
• "security status" - View security settings

**Security Info**:
- Authentication: ✅ Active (JWT Bearer)
- Authorization: ✅ Scope-based access control
- Admin Access: ✅ Verified
"""
```

### Helper Functions

```python
def _extract_user_message(task: Any) -> str:
    """Extract user message from A2A task."""
    try:
        if hasattr(task, "history") and task.history:
            for message in reversed(task.history):
                if message.role == "user" and message.parts:
                    for part in message.parts:
                        if hasattr(part, "root") and hasattr(part.root, "kind"):
                            if part.root.kind == "text" and hasattr(part.root, "text"):
                                return part.root.text
        return ""
    except Exception as e:
        logger.error(f"Error extracting user message: {e}")
        return ""
```

## Token Generation

### Built-in JWT Generator

AgentUp includes a comprehensive JWT token generator:

```bash
# Generate token with basic scope
python -m agentup.tools.jwt_generator \
  --scopes "basic" \
  --user-id "basic-user" \
  --expires-in 3600

# Generate token with multiple scopes
python -m agentup.tools.jwt_generator \
  --scopes "basic,premium,admin" \
  --user-id "admin-user" \
  --expires-in 7200

# Generate token with custom claims
python -m agentup.tools.jwt_generator \
  --scopes "premium" \
  --user-id "premium-user" \
  --claims '{"email": "user@example.com", "department": "engineering"}'

# Generate expired token for testing
python -m agentup.tools.jwt_generator \
  --scopes "basic" \
  --user-id "test-user" \
  --expired

# Generate token with invalid signature for testing
python -m agentup.tools.jwt_generator \
  --scopes "basic" \
  --user-id "test-user" \
  --invalid-signature
```

### Custom Token Generation

```python
#!/usr/bin/env python3
# custom_jwt_generator.py
import time
import jwt
from typing import Dict, List, Any

def generate_jwt_token(
    secret: str = "super-secret-jwt-key-for-testing-only-change-in-production",
    issuer: str = "test-issuer",
    audience: str = "agentup-jwt-test",
    user_id: str = "test-user-123",
    scopes: List[str] = None,
    expires_in_seconds: int = 3600,
    algorithm: str = "HS256",
    additional_claims: Dict[str, Any] = None,
) -> tuple[str, Dict[str, Any]]:
    """Generate a JWT token with custom claims and scopes."""
    
    current_time = int(time.time())
    
    # Standard claims
    payload = {
        "sub": user_id,
        "iss": issuer,
        "aud": audience,
        "iat": current_time,
        "exp": current_time + expires_in_seconds,
        "nbf": current_time,
    }
    
    # Add scopes
    if scopes:
        payload["scope"] = ",".join(scopes)
    
    # Add additional claims
    if additional_claims:
        payload.update(additional_claims)
    
    # Generate token
    token = jwt.encode(payload, secret, algorithm=algorithm)
    
    return token, payload

# Example usage
if __name__ == "__main__":
    # Generate different user tokens
    tokens = {}
    
    # Basic user
    tokens["basic"], _ = generate_jwt_token(
        user_id="basic-user",
        scopes=["basic"],
        additional_claims={
            "email": "basic@example.com",
            "name": "Basic User",
            "role": "user"
        }
    )
    
    # Premium user
    tokens["premium"], _ = generate_jwt_token(
        user_id="premium-user",
        scopes=["basic", "premium"],
        additional_claims={
            "email": "premium@example.com",
            "name": "Premium User", 
            "role": "premium",
            "subscription": "premium_plan"
        }
    )
    
    # Admin user
    tokens["admin"], _ = generate_jwt_token(
        user_id="admin-user",
        scopes=["basic", "premium", "admin"],
        additional_claims={
            "email": "admin@example.com",
            "name": "Admin User",
            "role": "admin",
            "department": "engineering"
        }
    )
    
    for user_type, token in tokens.items():
        print(f"{user_type.upper()} TOKEN:")
        print(token)
        print()
```

## Testing and Validation

### Comprehensive Integration Testing

```python
#!/usr/bin/env python3
# test_jwt_integration.py
"""
Comprehensive JWT integration testing for AgentUp
"""
import json
import requests
import subprocess
import sys
import time

def generate_jwt_token(scopes: str = "", user_id: str = "test-user", expires_in: int = 3600) -> str:
    """Generate a JWT token using the jwt_generator tool."""
    try:
        cmd = [
            sys.executable, "-m", "agentup.tools.jwt_generator",
            "--scopes", scopes,
            "--user-id", user_id,
            "--expires-in", str(expires_in),
            "--format", "token-only"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate JWT token: {e}")
        sys.exit(1)

def test_agent_discovery():
    """Test the A2A agent discovery endpoint."""
    print("🔍 Testing agent discovery endpoint...")
    
    try:
        response = requests.get("http://localhost:8000/.well-known/agent.json", timeout=5)
        response.raise_for_status()
        agent_card = response.json()
        
        # Check required fields
        assert "skills" in agent_card, "Agent card missing skills"
        assert "securitySchemes" in agent_card, "Agent card missing security schemes"
        assert "security" in agent_card, "Agent card missing security requirements"
        
        # Check for JWT test skills
        skill_ids = {skill["id"] for skill in agent_card["skills"]}
        expected_skills = {"public_echo", "basic_assistant", "premium_analyzer", "admin_status"}
        
        for skill in expected_skills:
            assert skill in skill_ids, f"Missing expected skill: {skill}"
        
        print("✅ Agent discovery endpoint working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Agent discovery test failed: {e}")
        return False

def test_skill_authorization(token: str, skill_id: str, expected_success: bool) -> bool:
    """Test authorization for a specific skill."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": f"skill-test-{skill_id}",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": f"test {skill_id}"}],
                "messageId": f"msg-{int(time.time() * 1000)}"
            },
            "skillId": skill_id
        }
    }
    
    try:
        response = requests.post("http://localhost:8000/", json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ HTTP error {response.status_code} for skill {skill_id}")
            return False
            
        result = response.json()
        
        if expected_success:
            if "result" in result and not result["result"]["artifacts"][0]["parts"][0]["text"].startswith("❌"):
                return True
            else:
                print(f"❌ Expected success for {skill_id} but got: {result}")
                return False
        else:
            # Expected failure - should get access denied message
            if "result" in result and "❌" in result["result"]["artifacts"][0]["parts"][0]["text"]:
                return True
            else:
                print(f"❌ Expected access denied for {skill_id} but got: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Skill authorization test failed for {skill_id}: {e}")
        return False

def main():
    """Run comprehensive JWT integration tests."""
    print("🚀 Starting JWT Integration Tests for AgentUp")
    print("=" * 60)
    
    # Test 1: Agent Discovery
    if not test_agent_discovery():
        print("❌ Agent discovery test failed - aborting")
        sys.exit(1)
    
    print()
    
    # Test 2: Scope-based Authorization
    print("🎯 Testing Scope-based Authorization...")
    
    # Test cases: (token_scopes, skill_id, expected_success)
    test_cases = [
        ("", "public_echo", True),              # Public skill - no scopes needed
        ("basic", "basic_assistant", True),     # Basic skill with basic scope
        ("", "basic_assistant", False),         # Basic skill without scope
        ("basic,premium", "premium_analyzer", True),  # Premium skill with premium scope
        ("basic", "premium_analyzer", False),   # Premium skill without premium scope
        ("basic,premium,admin", "admin_status", True),  # Admin skill with admin scope
        ("basic,premium", "admin_status", False),       # Admin skill without admin scope
    ]
    
    all_passed = True
    for scopes, skill_id, expected_success in test_cases:
        token = generate_jwt_token(scopes=scopes, user_id=f"test-{skill_id}")
        
        if test_skill_authorization(token, skill_id, expected_success):
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
            
        scope_desc = scopes if scopes else "none"
        success_desc = "should succeed" if expected_success else "should fail"
        print(f"{status} {skill_id} with scopes '{scope_desc}' ({success_desc})")
    
    print()
    if all_passed:
        print("🎉 JWT Integration Tests Complete!")
        print("=" * 60)
        print("All tests passed! The JWT authentication system is working correctly.")
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### JWT Token Validator

```python
#!/usr/bin/env python3
# jwt_validator.py
"""
JWT token validation and inspection tool
"""
import json
import sys
import base64
import jwt
from datetime import datetime

def decode_jwt_sections(token: str) -> tuple:
    """Decode JWT sections without validation."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None, None, "Invalid JWT format - must have 3 parts"
        
        # Decode header
        header_data = parts[0] + '=' * (4 - len(parts[0]) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_data))
        
        # Decode payload
        payload_data = parts[1] + '=' * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_data))
        
        return header, payload, None
        
    except Exception as e:
        return None, None, str(e)

def validate_jwt_token(token: str, secret: str = None, verify: bool = True) -> dict:
    """Validate JWT token with optional secret verification."""
    if not verify or not secret:
        return {"validated": False, "reason": "Validation skipped"}
    
    try:
        # Decode and validate
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256", "RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": False,  # Optional
                "verify_iss": False,  # Optional
            }
        )
        return {"validated": True, "payload": payload}
        
    except jwt.ExpiredSignatureError:
        return {"validated": False, "reason": "Token has expired"}
    except jwt.InvalidTokenError as e:
        return {"validated": False, "reason": f"Invalid token: {str(e)}"}
    except Exception as e:
        return {"validated": False, "reason": f"Validation error: {str(e)}"}

def format_timestamp(timestamp):
    """Format Unix timestamp to human readable."""
    try:
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
        return str(timestamp)
    except:
        return str(timestamp)

def main():
    """Main JWT validation function."""
    if len(sys.argv) < 2:
        print("Usage: python jwt_validator.py <jwt_token> [secret] [--no-verify]")
        print()
        print("Examples:")
        print("  python jwt_validator.py eyJhbGciOiJIUzI1NiIs...")
        print("  python jwt_validator.py eyJhbGciOiJIUzI1NiIs... my-secret-key")
        print("  python jwt_validator.py eyJhbGciOiJIUzI1NiIs... my-secret-key --no-verify")
        sys.exit(1)
    
    token = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    verify = "--no-verify" not in sys.argv
    
    print("JWT Token Analysis")
    print("=" * 50)
    print(f"Token: {token[:50]}{'...' if len(token) > 50 else ''}")
    print()
    
    # Decode sections
    header, payload, error = decode_jwt_sections(token)
    
    if error:
        print(f"❌ Error decoding token: {error}")
        sys.exit(1)
    
    # Display header
    print("📋 Header:")
    print(json.dumps(header, indent=2))
    print()
    
    # Display payload
    print("📄 Payload:")
    payload_display = payload.copy()
    
    # Format timestamps for better readability
    for time_field in ['iat', 'exp', 'nbf']:
        if time_field in payload_display:
            timestamp = payload_display[time_field]
            payload_display[f"{time_field}_formatted"] = format_timestamp(timestamp)
    
    print(json.dumps(payload_display, indent=2))
    print()
    
    # Validate if requested and secret provided
    if verify and secret:
        print("🔍 Validation:")
        validation_result = validate_jwt_token(token, secret, verify=True)
        
        if validation_result["validated"]:
            print("✅ Token is valid and verified")
        else:
            print(f"❌ Token validation failed: {validation_result['reason']}")
    elif verify and not secret:
        print("⚠️  Validation: Skipped (no secret provided)")
    else:
        print("⚠️  Validation: Skipped (--no-verify flag)")
    
    print()
    
    # Check expiration
    if "exp" in payload:
        import time
        exp_time = payload["exp"]
        current_time = int(time.time())
        
        if exp_time > current_time:
            remaining = exp_time - current_time
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            print(f"⏰ Token expires in {hours}h {minutes}m")
        else:
            expired_ago = current_time - exp_time
            hours = expired_ago // 3600
            minutes = (expired_ago % 3600) // 60
            print(f"⚠️  Token expired {hours}h {minutes}m ago")
    
    # Display scopes if present
    if "scope" in payload:
        scopes = payload["scope"]
        if isinstance(scopes, str):
            scope_list = [s.strip() for s in scopes.replace(',', ' ').split()]
        else:
            scope_list = scopes
        
        print(f"🎯 Scopes: {', '.join(scope_list)}")
    
    # Display user info
    user_fields = ['sub', 'user_id', 'email', 'name']
    user_info = {field: payload.get(field) for field in user_fields if field in payload}
    if user_info:
        print("👤 User Info:")
        for field, value in user_info.items():
            print(f"   {field}: {value}")

if __name__ == "__main__":
    main()
```

### Interactive Test Client

```python
#!/usr/bin/env python3
# interactive_jwt_client.py
"""
Interactive JWT test client for AgentUp
"""
import json
import requests
import time
import sys
from typing import Optional

class JWTTestClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
    
    def set_token(self, token: str):
        """Set the JWT token for authentication."""
        self.token = token
        print(f"✅ Token set: {token[:50]}{'...' if len(token) > 50 else ''}")
    
    def test_discovery(self):
        """Test the agent discovery endpoint."""
        print("🔍 Testing agent discovery...")
        try:
            response = requests.get(f"{self.base_url}/.well-known/agent.json")
            if response.status_code == 200:
                agent_card = response.json()
                print(f"✅ Agent: {agent_card.get('name', 'Unknown')}")
                print(f"   Skills: {len(agent_card.get('skills', []))}")
                print(f"   Security: {agent_card.get('security', 'None')}")
                return True
            else:
                print(f"❌ Discovery failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Discovery error: {e}")
            return False
    
    def test_skill(self, skill_id: str, message: str = "test"):
        """Test a specific skill with authentication."""
        if not self.token:
            print("❌ No token set. Use set_token() first.")
            return False
        
        print(f"🎯 Testing skill: {skill_id}")
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": f"test-{skill_id}-{int(time.time())}",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": message}],
                    "messageId": f"msg-{int(time.time() * 1000)}"
                },
                "skillId": skill_id
            }
        }
        
        try:
            response = requests.post(f"{self.base_url}/", json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    text = result["result"]["artifacts"][0]["parts"][0]["text"]
                    if text.startswith("❌"):
                        print(f"❌ Access denied: {text}")
                        return False
                    else:
                        print(f"✅ Success: {text}")
                        return True
                else:
                    print(f"❌ Error in response: {result}")
                    return False
            else:
                print(f"❌ HTTP error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Request error: {e}")
            return False
    
    def run_authorization_test(self):
        """Run comprehensive authorization test with different scopes."""
        if not self.token:
            print("❌ No token set. Use set_token() first.")
            return
        
        print("🔐 Running authorization test...")
        print("=" * 40)
        
        skills = [
            ("public_echo", "hello world"),
            ("basic_assistant", "hello"),
            ("premium_analyzer", "analyze my data"),
            ("admin_status", "show config")
        ]
        
        for skill_id, message in skills:
            self.test_skill(skill_id, message)
            print()
    
    def interactive_mode(self):
        """Run interactive mode for manual testing."""
        print("🚀 JWT Interactive Test Client")
        print("=" * 40)
        print("Commands:")
        print("  token <jwt_token>     - Set JWT token")
        print("  discovery             - Test discovery endpoint")
        print("  skill <id> [message]  - Test specific skill")
        print("  test                  - Run authorization test")
        print("  quit                  - Exit")
        print()
        
        while True:
            try:
                command = input("jwt-test> ").strip().split()
                if not command:
                    continue
                
                cmd = command[0].lower()
                
                if cmd == "quit" or cmd == "exit":
                    break
                elif cmd == "token":
                    if len(command) > 1:
                        self.set_token(command[1])
                    else:
                        print("Usage: token <jwt_token>")
                elif cmd == "discovery":
                    self.test_discovery()
                elif cmd == "skill":
                    if len(command) > 1:
                        skill_id = command[1]
                        message = " ".join(command[2:]) if len(command) > 2 else "test"
                        self.test_skill(skill_id, message)
                    else:
                        print("Usage: skill <skill_id> [message]")
                elif cmd == "test":
                    self.run_authorization_test()
                else:
                    print(f"Unknown command: {cmd}")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        print("👋 Goodbye!")

def main():
    """Main function."""
    client = JWTTestClient()
    
    if len(sys.argv) > 1:
        # Non-interactive mode with token provided
        token = sys.argv[1]
        client.set_token(token)
        client.test_discovery()
        client.run_authorization_test()
    else:
        # Interactive mode
        client.interactive_mode()

if __name__ == "__main__":
    main()
```

## Production Deployment

### Environment Configuration

```yaml
# production.agent_config.yaml
security:
  enabled: true
  type: bearer
  bearer:
    # Use environment variables for all secrets
    jwt_secret: "${JWT_SECRET}"
    algorithm: "${JWT_ALGORITHM:HS256}"
    issuer: "${JWT_ISSUER}"
    audience: "${JWT_AUDIENCE}"
    
    # For RS256 in production
    jwks_url: "${JWKS_URL}"
    jwks_cache_ttl: "${JWKS_CACHE_TTL:300}"
```

```bash
# production.env
JWT_SECRET=your-super-secure-production-secret-256-bits-minimum
JWT_ALGORITHM=HS256
JWT_ISSUER=https://your-production-app.com
JWT_AUDIENCE=your-production-agent-id

# For JWKS-based validation
JWKS_URL=https://your-auth-provider.com/.well-known/jwks.json
JWKS_CACHE_TTL=3600
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY pyproject.toml ./
RUN pip install -e .

# Copy agent configuration
COPY agent_config.yaml ./
COPY .env ./

# Copy handler implementations if needed
COPY jwt_handlers.py ./

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/.well-known/agent.json || exit 1

# Run agent
CMD ["agentup", "agent", "serve", "--port", "8000", "--host", "0.0.0.0"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  jwt-agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - JWT_ISSUER=${JWT_ISSUER}  
      - JWT_AUDIENCE=${JWT_AUDIENCE}
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/.well-known/agent.json"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jwt-agent
  labels:
    app: jwt-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: jwt-agent
  template:
    metadata:
      labels:
        app: jwt-agent
    spec:
      containers:
      - name: jwt-agent
        image: your-registry/jwt-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: jwt-secrets
              key: jwt-secret
        - name: JWT_ISSUER
          valueFrom:
            configMapKeyRef:
              name: jwt-config
              key: jwt-issuer
        - name: JWT_AUDIENCE
          valueFrom:
            configMapKeyRef:
              name: jwt-config
              key: jwt-audience
        livenessProbe:
          httpGet:
            path: /.well-known/agent.json
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /.well-known/agent.json
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: jwt-agent-service
spec:
  selector:
    app: jwt-agent
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: v1
kind: Secret
metadata:
  name: jwt-secrets
type: Opaque
data:
  jwt-secret: <base64-encoded-secret>

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: jwt-config
data:
  jwt-issuer: "https://your-production-app.com"
  jwt-audience: "your-production-agent-id"
```

## Security Best Practices

### Token Security

#### ✅ **Do's**
- **Use strong secrets** - Minimum 256-bit (32-character) secrets for HS256
- **Short expiration times** - 1-24 hours maximum token lifetime
- **HTTPS only** - Never transmit JWT tokens over HTTP
- **Secure storage** - Store tokens securely on client side (HttpOnly cookies preferred)
- **Algorithm specification** - Always specify and validate allowed algorithms
- **Regular rotation** - Rotate JWT secrets regularly (monthly/quarterly)

#### ❌ **Don'ts**
- **Never use "none" algorithm** - Always require cryptographic verification
- **Don't put secrets in logs** - Ensure JWT secrets never appear in logs
- **Don't use weak secrets** - Avoid dictionary words, short strings, or predictable patterns
- **Don't put tokens in URLs** - Never include JWT tokens in query parameters or URLs
- **Don't ignore expiration** - Always validate token expiration times
- **Don't store in localStorage** - Prefer HttpOnly cookies over localStorage

### Scope Design Best Practices

#### Hierarchical Scopes
```yaml
# Good: Clear hierarchy
scopes:
  - read          # Basic read access
  - write         # Write access (implies read)
  - admin         # Administrative access (implies read/write)

# Bad: Overlapping permissions
scopes:
  - user_read
  - user_write
  - admin_read
  - admin_write
  - super_admin
```

#### Principle of Least Privilege
```python
# Good: Check for specific scope needed
@register_handler("premium_analyzer")
async def handle_premium_analyzer(task: Any, context=None) -> str:
    if not context.has_scope("premium"):
        return "❌ Access denied. Premium analyzer requires 'premium' scope."
    # ... handler logic

# Bad: Check for multiple scopes when only one needed
@register_handler("premium_analyzer") 
async def handle_premium_analyzer(task: Any, context=None) -> str:
    if not context.has_all_scopes(["basic", "premium", "admin"]):
        return "❌ Access denied."
    # ... handler logic
```

### Production Security Checklist

- [ ] **Secrets Management**
  - [ ] JWT secrets stored in secure secret management system
  - [ ] Environment variables used for all secrets
  - [ ] No secrets in configuration files or code
  - [ ] Regular secret rotation procedures in place

- [ ] **Token Validation**
  - [ ] Signature verification enabled
  - [ ] Expiration time validation enabled
  - [ ] Issuer validation configured
  - [ ] Audience validation configured
  - [ ] Algorithm validation enforced

- [ ] **Network Security**
  - [ ] HTTPS/TLS enabled for all communications
  - [ ] Proper certificate management
  - [ ] Network segmentation in place
  - [ ] Firewall rules configured

- [ ] **Monitoring and Logging**
  - [ ] Authentication events logged
  - [ ] Failed authentication alerts configured
  - [ ] Token usage monitoring in place
  - [ ] Security incident response procedures documented

- [ ] **Access Control**
  - [ ] Scope-based authorization implemented
  - [ ] Principle of least privilege followed
  - [ ] Regular access reviews conducted
  - [ ] Unused scopes removed

## Troubleshooting

### Common Issues

#### ❌ "Bearer token is required when using bearer auth type"

**Cause**: Configuration validation failure before authenticator initialization.

**Solution**:
```yaml
# Ensure JWT configuration is present
security:
  enabled: true
  type: bearer
  bearer:
    jwt_secret: "${JWT_SECRET:default-secret}"  # Must have jwt_secret
    algorithm: HS256
    issuer: "${JWT_ISSUER:test-issuer}"
    audience: "${JWT_AUDIENCE:test-audience}"
```

#### ❌ "Invalid JWT token format"

**Cause**: Malformed JWT token or incorrect Bearer header format.

**Solutions**:
```bash
# Correct format
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Common mistakes
Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Missing "Bearer "
Authorization: Bearer=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Extra "="
```

#### ❌ "JWT signature verification failed"

**Cause**: Wrong secret, algorithm mismatch, or token tampering.

**Debug steps**:
```python
# Verify token with known secret
python -m agentup.tools.jwt_validator token secret-key

# Check algorithm in token header
python -c "
import json, base64
token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
header = json.loads(base64.urlsafe_b64decode(token.split('.')[0] + '==='))
print('Algorithm:', header.get('alg'))
"
```

#### ❌ "Token has expired"

**Cause**: JWT token expiration time exceeded.

**Solution**:
```bash
# Generate new token with longer expiration
python -m agentup.tools.jwt_generator \
  --scopes "basic,premium" \
  --user-id "test-user" \
  --expires-in 7200  # 2 hours
```

#### ❌ "Access denied. This feature requires 'X' scope"

**Cause**: User token doesn't include required scope.

**Debug steps**:
```python
# Check token scopes
python -m agentup.tools.jwt_validator your-token

# Generate token with required scopes
python -m agentup.tools.jwt_generator \
  --scopes "basic,premium,admin" \
  --user-id "test-user"
```

### Debugging Tools

#### Configuration Validation
```python
# test_config.py
from agent.config.loader import load_config
from agent.security.manager import SecurityManager

try:
    config = load_config()
    security_manager = SecurityManager(config)
    print("✅ Configuration valid")
except Exception as e:
    print(f"❌ Configuration error: {e}")
```

#### Authentication Flow Testing
```bash
# Test authentication step-by-step

# 1. Check agent discovery
curl http://localhost:8000/.well-known/agent.json

# 2. Generate test token
TOKEN=$(python -m agentup.tools.jwt_generator --scopes "basic" --user-id "test" --format token-only)

# 3. Test authentication
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"message/send","id":"test","params":{"message":{"role":"user","parts":[{"kind":"text","text":"hello"}],"messageId":"msg-1"},"skillId":"basic_assistant"}}' \
     http://localhost:8000/
```

#### Log Analysis
```bash
# Monitor authentication events
tail -f /var/log/agentup/agent.log | grep -E "(authentication|authorization|JWT)"

# Common log patterns to look for:
# INFO - JWT mode detected, setting bearer_token to None
# INFO - User basic-user accessing basic_assistant with scopes: ['basic']
# WARNING - Authorization failed for premium_analyzer: missing premium scope
# ERROR - JWT signature verification failed
```

## Next Steps

### Advanced Implementation
- **[Custom Authentication](../reference/custom-auth.md)** - Build custom authenticators
- **[Plugin Development](../plugins/development.md)** - Create scope-aware plugins
- **[State Management](../configuration/state.md)** - Add stateful authentication context

### Enterprise Integration
- **[OAuth2 Setup](oauth2.md)** - Full OAuth2 provider integration
- **[Multi-Factor Authentication](../configuration/security.md#mfa)** - Additional security layers
- **[SSO Integration](../examples/enterprise-sso.md)** - Single sign-on setup

### Production Operations
- **[Monitoring Setup](../configuration/monitoring.md)** - Authentication monitoring
- **[Performance Tuning](../configuration/performance.md)** - High-throughput optimization
- **[Security Hardening](../configuration/security.md#hardening)** - Production security

---

**Quick Links:**
- [Documentation Home](../index.md)
- [Authentication Overview](index.md)
- [OAuth2 Authentication](oauth2.md)
- [Troubleshooting Guide](../troubleshooting/authentication.md)
- [Configuration Reference](../reference/config-schema.md)