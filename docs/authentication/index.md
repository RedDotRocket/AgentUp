# Authentication Overview

**Enterprise-grade security for your AgentUp agents**

AgentUp provides a comprehensive authentication system that combines ease of use with enterprise-grade security. Whether you're building a simple development agent or a production system serving thousands of requests, our authentication framework has you covered.

## Authentication Methods

### [API Key Authentication](api-keys.md)
**Perfect for**: Development, internal APIs, service-to-service authentication

- **Simple setup** - Secure your agent in 2 minutes
- **Multiple keys** - Support different environments and clients  
- **Strong validation** - Automatic rejection of weak keys
- **Flexible locations** - Headers, query params, or cookies

```yaml
security:
  enabled: true
  type: "api_key"
  api_key: "sk-your-strong-api-key-here"
```

**When to use**: Development environments, internal microservices, simple integrations

---

### [Bearer Token Authentication](bearer-tokens.md)
**Perfect for**: Custom JWT tokens, stateless authentication

- **JWT support** - Full JSON Web Token validation
- **Stateless** - No server-side session storage
- **Flexible claims** - Extract user info and scopes
- **Standard format** - RFC 7519 compliant

```yaml
security:
  enabled: true
  type: "bearer"
  bearer_token: "your-jwt-token-here"
```

**When to use**: Custom authentication systems, JWT-based workflows, stateless applications

---

### [JWT Authentication](jwt-authentication.md) 🚀 **NEW**
**Perfect for**: Production JWT with scope-based authorization

- **Full JWT validation** - Cryptographic signature verification
- **Scope-based authorization** - Fine-grained permission control
- **Authentication context** - Scopes passed to handlers automatically
- **Production ready** - Environment variables, Docker, Kubernetes

```yaml
security:
  enabled: true
  type: "bearer"
  bearer:
    jwt_secret: "${JWT_SECRET}"
    algorithm: "HS256"
    issuer: "${JWT_ISSUER}"
    audience: "${JWT_AUDIENCE}"
```

**When to use**: Production systems, scope-based access control, enterprise applications

---

### [OAuth2 Authentication](oauth2.md)
**Perfect for**: Enterprise integration, third-party access, production systems

- **Enterprise providers** - Google, Auth0, Azure AD, AWS Cognito
- **Multiple strategies** - JWT validation, token introspection, or both
- **Scope-based auth** - Fine-grained permissions
- **Real-time validation** - Token revocation support

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://provider.com/.well-known/jwks.json"
    jwt_issuer: "https://provider.com"
    jwt_audience: "your-agent-id"
```

**When to use**: Enterprise environments, third-party integrations, complex authorization needs

## Quick Start Guides

### [5-Minute Setup](quick-start.md)
Get your agent secured with API key authentication in just 5 minutes. Perfect for getting started quickly.

### [Provider Integration](providers.md)
Step-by-step setup guides for popular OAuth2 providers including Google, Auth0, Microsoft Azure AD, and more.

## Security Features

### Enterprise-Grade Security
- **Constant-time comparisons** - Protection against timing attacks
- **Secure credential handling** - Never log or expose secrets
- **Input validation** - Comprehensive validation of all inputs
- **Audit logging** - Complete authentication event tracking

### A2A Protocol Compliance
- **Public discovery** - Agent capabilities advertised correctly
- **Security schemes** - Proper authentication method declarations
- **Standard formats** - Following OpenAPI security scheme specifications

### Performance Optimized
- **Efficient validation** - Optimized for high-throughput scenarios
- **Caching support** - JWKS and configuration caching
- **Async operations** - Non-blocking authentication flows

## Architecture

### Authentication Flow
```mermaid
graph TD
    A[Client Request] --> B{Security Enabled?}
    B -->|No| H[Allow Access]
    B -->|Yes| C[@protected Decorator]
    C --> D[Security Manager]
    D --> E[Route to Authenticator]
    E --> F{Authentication Valid?}
    F -->|Yes| G[Extract User Info]
    F -->|No| I[Return 401 Unauthorized]
    G --> H[Allow Access]
```

## Configuration Philosophy

AgentUp follows a **configuration-driven** approach to security:

### What This Means
- **All behavior controlled by config** - No hardcoded security policies
- **Environment-specific settings** - Different configs for dev/staging/prod
- **Runtime flexibility** - Change auth methods without code changes
- **Validation at startup** - Catch configuration errors early

### 📝 Configuration Examples

**Development Environment:**
```yaml
security:
  enabled: false  # Disable for local development
```

**Staging Environment:**
```yaml
security:
  enabled: true
  type: "api_key"
  api_key: "${STAGING_API_KEY}"
```

**Production Environment:**
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "${OAUTH_JWKS_URL}"
    jwt_issuer: "${OAUTH_ISSUER}"
    jwt_audience: "${OAUTH_AUDIENCE}"
    required_scopes: ["agent:read", "agent:write"]
```

## Best Practices

### 🔐 Security Best Practices
1. **Use HTTPS in production** - Never transmit credentials over HTTP
2. **Rotate credentials regularly** - Implement key/token rotation procedures
3. **Use environment variables** - Keep secrets out of configuration files
4. **Monitor authentication attempts** - Set up alerts for failed attempts
5. **Follow principle of least privilege** - Grant minimum necessary permissions

### Configuration Best Practices
1. **Validate configurations** - Use built-in validation tools
2. **Use strong credentials** - Follow password/key strength guidelines
3. **Environment separation** - Different credentials per environment
4. **Document requirements** - Clear setup instructions for your team
5. **Test thoroughly** - Validate auth works before deploying

### Performance Best Practices
1. **Use JWT validation** - Faster than token introspection
2. **Cache JWKS keys** - Reduce external API calls
3. **Implement rate limiting** - Protect against brute force attacks
4. **Monitor performance** - Track authentication latency
5. **Use async patterns** - Non-blocking authentication flows

## Common Use Cases

### Development Workflow
```yaml
# Local development - no auth for simplicity
security:
  enabled: false

# CI/CD testing - simple API key
security:
  enabled: true
  type: "api_key" 
  api_key: "sk-ci-test-key"

# Staging - OAuth2 for testing integrations  
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    # ... staging OAuth2 config
```

### Microservices Architecture
```yaml
# Service-to-service authentication
security:
  enabled: true
  type: "api_key"
  api_key:
    keys:
      - "${USER_SERVICE_KEY}"
      - "${ORDER_SERVICE_KEY}" 
      - "${PAYMENT_SERVICE_KEY}"
```

### Enterprise Integration
```yaml
# Enterprise OAuth2 with Azure AD
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://login.microsoftonline.com/tenant/discovery/v2.0/keys"
    jwt_issuer: "https://login.microsoftonline.com/tenant/v2.0"
    jwt_audience: "your-app-id"
    required_scopes: ["api://your-app/Agent.Access"]
```

## Migration Guide

### Adding Authentication to Existing Agent
1. **Choose authentication method** based on your needs
2. **Update configuration** with security section
3. **Test locally** with new authentication
4. **Update clients** to include credentials
5. **Deploy and monitor** for any issues

### Switching Authentication Methods
1. **Plan transition period** - consider dual authentication temporarily
2. **Update configuration** with new method
3. **Update all clients** with new credential format
4. **Remove old method** after successful transition
5. **Update documentation** for your team

## Troubleshooting

### Quick Diagnostics
```bash
# Test agent configuration
uv run python -c "
from src.agent.config import load_config
from src.agent.security import validate_security_config
config = load_config()
validate_security_config(config.get('security', {}))
print('Configuration valid')
"

# Test authentication endpoint
curl -v http://localhost:8000/.well-known/agent.json
```

### Common Issues
- **[Authentication Problems](../troubleshooting/authentication.md)** - Comprehensive troubleshooting guide
- **Configuration errors** - YAML syntax and validation issues
- **Network connectivity** - OAuth2 provider connection problems
- **Performance issues** - Slow authentication responses

## Next Steps

### Get Started
- **[Quick Start Guide](quick-start.md)** - Secure your first agent
- **[API Key Setup](api-keys.md)** - Simple authentication method
- **[JWT Authentication](jwt-authentication.md)** - Production JWT with scopes 🚀 **NEW**
- **[OAuth2 Setup](oauth2.md)** - Enterprise-grade authentication

### Advanced Topics
- **[Custom Authentication](../reference/custom-auth.md)** - Build your own authenticator
- **[Security Configuration](../configuration/security.md)** - Advanced security settings
- **[Production Deployment](../examples/enterprise-agent.md)** - Production-ready setups

### References
- **[Configuration Schema](../reference/config-schema.md)** - Complete configuration reference
- **[API Reference](../reference/api.md)** - Authentication API endpoints
- **[Troubleshooting](../troubleshooting/authentication.md)** - Problem-solving guide

---

**Quick Links:**
- [Documentation Home](../index.md)
- [5-Minute Quick Start](quick-start.md)
- [Troubleshooting Guide](../troubleshooting/authentication.md)
- [Configuration Reference](../reference/config-schema.md)