# Agent Configuration

Master the `agent_config.yaml` file to customize your agent's behavior.

## Overview

AgentUp uses a single configuration file (`agent_config.yaml`) to control all aspects of your agent. This configuration-driven approach makes it easy to customize behavior without writing code.

## Basic Configuration Structure

```yaml
# Basic agent metadata
name: "My Agent"
description: "What this agent does"
version: "1.0.0"

# Plugin selection and configuration
plugins:
  - plugin_id: system_tools
  - plugin_id: web_tools
    config:
      timeout: 30

# Cross-cutting middleware
middleware:
  - name: rate_limiting
    config:
      requests_per_minute: 60
  - name: authentication
    config:
      method: api_key

# Conversation state management
state_management:
  enabled: true
  backend: memory

# Server configuration
server:
  host: "0.0.0.0"
  port: 8000
```

## Configuration Sections

### Agent Metadata

```yaml
name: "My Agent"              # Required: Agent display name
description: "Agent purpose"  # Required: What the agent does
version: "1.0.0"             # Required: Semantic version
author: "Your Name"          # Optional: Agent author
license: "MIT"               # Optional: License type
```

### Plugin Configuration

```yaml
plugins:
  # Simple plugin enablement
  - plugin_id: system_tools
  
  # Plugin with configuration
  - plugin_id: web_tools
    config:
      timeout: 30
      retries: 3
      
  # Plugin with middleware override
  - plugin_id: expensive_api
    middleware_override:
      - name: rate_limiting
        config:
          requests_per_minute: 10
```

### Middleware Configuration

```yaml
middleware:
  # Rate limiting
  - name: rate_limiting
    config:
      requests_per_minute: 60
      burst_limit: 10
      
  # Authentication
  - name: authentication
    config:
      method: api_key
      required_scopes: ["read", "write"]
      
  # Request logging
  - name: request_logging
    config:
      log_level: INFO
      include_request_body: false
      include_response_body: false
      
  # Response caching
  - name: caching
    config:
      backend: memory
      default_ttl: 300
      cache_responses: true
```

### State Management

```yaml
state_management:
  enabled: true
  backend: memory              # memory, valkey, redis, postgres
  config:
    ttl: 3600                 # Session timeout in seconds
    cleanup_interval: 300      # Cleanup frequency
    max_sessions: 1000        # Maximum concurrent sessions
```

### Authentication

```yaml
authentication:
  enabled: true
  method: api_key              # api_key, bearer_token, oauth2
  config:
    # API Key authentication
    api_keys:
      - key: "${API_KEY_1}"
        name: "development"
        scopes: ["read", "write"]
      - key: "${API_KEY_2}"
        name: "production"
        scopes: ["read"]
    
    # Bearer token authentication
    bearer_tokens:
      - token: "${BEARER_TOKEN}"
        issuer: "my-service"
        audience: "my-agent"
    
    # OAuth2 authentication
    oauth2:
      provider: "google"
      client_id: "${OAUTH_CLIENT_ID}"
      client_secret: "${OAUTH_CLIENT_SECRET}"
      scopes: ["openid", "email"]
```

### Server Configuration

```yaml
server:
  host: "0.0.0.0"             # Bind address
  port: 8000                  # Port number
  workers: 1                  # Number of worker processes
  timeout: 30                 # Request timeout
  max_request_size: 10485760  # 10MB max request size
  
  # TLS configuration (optional)
  tls:
    enabled: true
    cert_file: "/path/to/cert.pem"
    key_file: "/path/to/key.pem"
```

### Logging Configuration

```yaml
logging:
  level: INFO                 # DEBUG, INFO, WARNING, ERROR
  format: "json"              # json, text
  
  handlers:
    - type: console
      level: INFO
    - type: file
      level: DEBUG
      filename: "logs/agent.log"
      max_size: 10485760       # 10MB
      backup_count: 5
    - type: syslog
      level: WARNING
      facility: "local0"
```

## Environment Variable Substitution

Use environment variables in configuration:

```yaml
# Environment variable with default value
database_url: "${DATABASE_URL:sqlite:///default.db}"

# Required environment variable (fails if not set)
api_key: "${REQUIRED_API_KEY}"

# Nested environment variables
authentication:
  config:
    api_keys:
      - key: "${API_KEY_1}"
        name: "${KEY_1_NAME:development}"
```

## Configuration Validation

### Validate Configuration

```bash
# Validate configuration file
agentup agent validate

# Validate with verbose output
agentup agent validate --verbose

# Validate specific file
agentup agent validate --config custom_config.yaml
```

### Common Validation Errors

```yaml
# ❌ Missing required field
name: "My Agent"
# description: "Required field missing"
version: "1.0.0"

# ❌ Invalid plugin configuration
plugins:
  - plugin_id: "nonexistent_plugin"

# ❌ Invalid middleware order
middleware:
  - name: authentication  # Should come before rate_limiting
  - name: rate_limiting

# ❌ Invalid state backend
state_management:
  enabled: true
  backend: "unsupported_backend"
```

## Configuration Best Practices

### 1. Use Environment Variables for Secrets

```yaml
# ✅ Good: Use environment variables
authentication:
  config:
    api_keys:
      - key: "${API_KEY}"

# ❌ Bad: Hardcode secrets
authentication:
  config:
    api_keys:
      - key: "secret-key-123"
```

### 2. Provide Sensible Defaults

```yaml
# ✅ Good: Provide defaults
database_url: "${DATABASE_URL:sqlite:///agent.db}"
log_level: "${LOG_LEVEL:INFO}"

# ❌ Bad: No defaults for optional values
database_url: "${DATABASE_URL}"
log_level: "${LOG_LEVEL}"
```

### 3. Document Your Configuration

```yaml
# Agent configuration for production deployment
name: "Production Agent"
description: "Production-ready agent with full security"
version: "1.0.0"

plugins:
  # Core system operations
  - plugin_id: system_tools
    config:
      # Restrict file operations to safe directories
      allowed_paths: ["/app/data", "/tmp"]
  
  # External API integration
  - plugin_id: web_tools
    config:
      # Conservative timeout for production
      timeout: 10
      retries: 2
```

### 4. Use Configuration Profiles

Create different configurations for different environments:

```bash
# Development
cp config/development.yaml agent_config.yaml

# Production  
cp config/production.yaml agent_config.yaml

# Testing
cp config/testing.yaml agent_config.yaml
```

## Advanced Configuration Patterns

### Conditional Plugin Loading

```yaml
plugins:
  # Load development plugins only in dev environment
  - plugin_id: debug_tools
    enabled: "${ENVIRONMENT:production}" != "production"
  
  # Load production plugins only in production
  - plugin_id: monitoring
    enabled: "${ENVIRONMENT}" == "production"
```

### Dynamic Middleware Configuration

```yaml
middleware:
  # Rate limiting with environment-specific limits
  - name: rate_limiting
    config:
      requests_per_minute: "${RATE_LIMIT:60}"
      
  # Authentication only in production
  - name: authentication
    enabled: "${REQUIRE_AUTH:false}" == "true"
```

### Configuration Inheritance

```yaml
# Base configuration
base_config: &base
  middleware:
    - name: logging
    - name: rate_limiting

# Development extends base
development:
  <<: *base
  plugins:
    - plugin_id: debug_tools

# Production extends base  
production:
  <<: *base
  plugins:
    - plugin_id: monitoring
```

## Configuration Reference

For complete configuration options, see:
- **[Configuration Schema](../../reference/configuration-schema.md)** - All available options
- **[Plugin Configuration](../plugin-development/configuration.md)** - Plugin-specific settings
- **[Middleware Reference](../configuration/middleware.md)** - Middleware options
- **[Authentication Guide](../authentication/)** - Security configuration

## Troubleshooting Configuration

### Debug Configuration Loading

```bash
# Show resolved configuration
agentup agent config show

# Show configuration with environment variables resolved
agentup agent config show --resolve-env

# Validate configuration step by step
agentup agent validate --debug
```

### Common Issues

1. **YAML Syntax Errors**: Use proper indentation and quoting
2. **Environment Variables Not Set**: Provide defaults or set required variables
3. **Plugin Not Found**: Ensure plugin is installed and plugin_id is correct
4. **Middleware Order**: Authentication should come before other middleware
5. **Invalid References**: Check that all referenced files and resources exist

## Next Steps

- **[Customization Guide](customization.md)** - Customize CLI and templates
- **[Deployment Guide](deployment.md)** - Deploy your configured agent
- **[Middleware Configuration](../configuration/middleware.md)** - Advanced middleware setup
- **[Plugin Development](../plugin-development/)** - Create custom plugins