# A2A Authenticated Extended Card

**Enterprise-grade plugin visibility control for A2A-compliant agents**

The A2A Authenticated Extended Card feature allows you to expose different levels of capabilities to public versus authenticated clients. This is essential for enterprise deployments where you want to advertise basic capabilities publicly while reserving sensitive or advanced features for authenticated users.

## What is an Extended Card?

The A2A protocol supports two types of Agent Cards:

1. **Public Agent Card** (`/.well-known/agent.json`) - Available to anyone, no authentication required
2. **Authenticated Extended Card** (`/agent/authenticatedExtendedCard`) - Only available to authenticated clients

AgentUp implements both endpoints and provides a simple configuration system to control which plugins appear in each card.

## Quick Start

### 1. Basic Setup

Configure plugins with different visibility levels:

```yaml
# agent_config.yaml
plugins:
  # Public plugins - visible to everyone
  - plugin_id: "general_help"
    name: "General Help"
    description: "Basic assistance and information"
    visibility: "public"  # default, can be omitted

  # Extended plugins - only visible to authenticated clients
  - plugin_id: "admin_tools"
    name: "Admin Tools"
    description: "Administrative functions"
    visibility: "extended"

  - plugin_id: "sensitive_data"
    name: "Sensitive Data Access"
    description: "Access to confidential information"
    visibility: "extended"

# Enable security (required for extended card)
security:
  enabled: true
  type: "api_key"
  api_keys:
    - "your-api-key-here"
```

### 2. Test the Implementation

```bash
# Test public card (no auth required)
curl http://localhost:8000/.well-known/agent.json

# Test extended card (requires authentication)
curl -H "X-API-Key: your-api-key-here" \
     http://localhost:8000/agent/authenticatedExtendedCard
```

## Configuration Reference

### Plugin Visibility

The `visibility` field controls which Agent Card includes the plugin:

| Value | Description | Public Card | Extended Card |
|-------|-------------|-------------|---------------|
| `"public"` | Default - visible to all | ✓ | ✓ |
| `"extended"` | Only visible to authenticated clients | ✗ | ✓ |

### Agent Card Behavior

- **supportsAuthenticatedExtendedCard**: Automatically set to `true` if any plugins have `visibility: "extended"`
- **Public Card**: Shows only plugins with `visibility: "public"` (default)
- **Extended Card**: Shows both public and extended plugins

## Security Considerations

### Authentication Requirements

The extended card endpoint requires authentication using any of the configured security schemes:

```yaml
security:
  enabled: true
  type: "api_key"  # or "bearer", "oauth2", "jwt"
  # ... security configuration
```

### Plugin Execution

**Important**: Plugin visibility only affects Agent Card advertisement, not execution. All configured plugins (public and extended) are available for execution once the agent is running.

This design allows:
- **Discovery control**: Hide sensitive plugins from public discovery
- **Full functionality**: Authenticated clients can use all plugins
- **Operational simplicity**: No runtime differences between plugin types

## Advanced Usage

### Enterprise Configuration

```yaml
# agent_config.yaml
agent:
  name: "Enterprise Agent"
  description: "Production agent with tiered capabilities"

plugins:
  # Tier 1: Public capabilities
  - plugin_id: "company_info"
    name: "Company Information"
    description: "Basic company information and contact details"
    visibility: "public"

  - plugin_id: "product_catalog"
    name: "Product Catalog"
    description: "Browse our product offerings"
    visibility: "public"

  # Tier 2: Customer capabilities
  - plugin_id: "order_status"
    name: "Order Status"
    description: "Check order status and tracking"
    visibility: "extended"

  - plugin_id: "support_tickets"
    name: "Support Tickets"
    description: "Create and manage support tickets"
    visibility: "extended"

  # Tier 3: Admin capabilities
  - plugin_id: "user_management"
    name: "User Management"
    description: "Manage user accounts and permissions"
    visibility: "extended"

  - plugin_id: "analytics_dashboard"
    name: "Analytics Dashboard"
    description: "Access to business analytics and reports"
    visibility: "extended"

# Multi-tier authentication
security:
  enabled: true
  type: "jwt"
  jwt:
    secret: "${JWT_SECRET}"
    algorithm: "HS256"
    audience: "enterprise-agent"
    issuer: "company-auth-service"
```

### Scope-Based Access Control

Combine plugin visibility with scope-based authorization:

```yaml
plugins:
  - plugin_id: "financial_reports"
    name: "Financial Reports"
    description: "Access to financial data and reports"
    visibility: "extended"
    required_scopes: ["finance:read", "reports:access"]

  - plugin_id: "user_admin"
    name: "User Administration"
    description: "Manage user accounts and permissions"
    visibility: "extended"
    required_scopes: ["admin:users"]
```

## API Reference

### Endpoints

#### GET /.well-known/agent.json
**Purpose**: A2A agent discovery endpoint (public)
**Authentication**: None required
**Response**: AgentCard with public plugins only

#### GET /agent/authenticatedExtendedCard
**Purpose**: A2A authenticated extended card endpoint
**Authentication**: Required (any configured scheme)
**Response**: AgentCard with both public and extended plugins

### Response Format

Both endpoints return the same AgentCard structure, but with different plugin sets:

```json
{
  "protocolVersion": "0.2.9",
  "name": "Enterprise Agent",
  "description": "Production agent with tiered capabilities",
  "version": "1.0.0",
  "url": "https://agent.company.com",
  "supportsAuthenticatedExtendedCard": true,
  "skills": [
    {
      "id": "company_info",
      "name": "Company Information",
      "description": "Basic company information and contact details"
    }
    // Extended card would include additional skills here
  ],
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "securitySchemes": {
    "ApiKey": {
      "type": "apiKey",
      "name": "X-API-Key",
      "in": "header"
    }
  },
  "security": [
    {"ApiKey": []}
  ]
}
```

## Best Practices

### 1. Gradual Disclosure

Structure your plugin visibility to provide a natural progression:

```yaml
plugins:
  # Level 1: Public information
  - plugin_id: "basic_info"
    visibility: "public"

  # Level 2: Authenticated features
  - plugin_id: "user_features"
    visibility: "extended"

  # Level 3: Admin features (with scope control)
  - plugin_id: "admin_features"
    visibility: "extended"
    required_scopes: ["admin"]
```

### 2. Clear Descriptions

Use plugin descriptions to indicate access levels:

```yaml
plugins:
  - plugin_id: "reports"
    name: "Reports"
    description: "Generate business reports (authenticated users only)"
    visibility: "extended"
```

### 3. Security Validation

Always validate that extended plugins have appropriate security:

```yaml
plugins:
  - plugin_id: "sensitive_data"
    name: "Sensitive Data Access"
    description: "Access to confidential information"
    visibility: "extended"
    required_scopes: ["data:sensitive"]
    auth_required: true
```

## Troubleshooting

### Common Issues

#### Extended Card Not Available
**Symptoms**: `supportsAuthenticatedExtendedCard` is `false`
**Solution**: Ensure at least one plugin has `visibility: "extended"`

#### Authentication Errors
**Symptoms**: 401/403 errors when accessing extended card
**Solution**: Verify security configuration and provide valid credentials

#### Plugin Not Visible
**Symptoms**: Plugin missing from expected card
**Solution**: Check plugin `visibility` setting and authentication status

### Debugging

Enable debug logging to trace card generation:

```yaml
logging:
  level: "DEBUG"
  modules:
    "agent.api.routes": "DEBUG"
```

## Migration Guide

### From Basic to Extended Cards

1. **Identify sensitive plugins** in your current configuration
2. **Add visibility field** to appropriate plugins:
   ```yaml
   # Before
   - plugin_id: "admin_tools"
     name: "Admin Tools"

   # After
   - plugin_id: "admin_tools"
     name: "Admin Tools"
     visibility: "extended"
   ```
3. **Test both endpoints** to verify behavior
4. **Update client code** to use extended card when authenticated

### Backward Compatibility

The extended card feature is fully backward compatible:
- Existing configurations work unchanged
- `visibility` defaults to `"public"`
- Public Agent Card behavior remains identical
- No breaking changes to existing APIs

## A2A Compliance

This implementation follows the A2A Protocol Specification v0.2.9:
- ✓ Correct endpoint path: `/agent/authenticatedExtendedCard`
- ✓ Proper authentication requirements
- ✓ Standard HTTP response codes
- ✓ Compatible AgentCard format
- ✓ Appropriate `supportsAuthenticatedExtendedCard` flag

Your AgentUp agents are now fully A2A compliant with enterprise-grade plugin visibility control.