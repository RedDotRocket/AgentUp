# A2A Protocol Implementation in AgentUp

**Complete A2A Protocol compliance with enterprise-grade plugin visibility control**

AgentUp implements the full A2A (Agent-to-Agent) Protocol specification v0.2.9, enabling seamless
interoperability between AI agents.

The A2A protocol defines standardized communication patterns, discovery mechanisms, and capability
advertising for autonomous agents.

## A2A Protocol Overview

The A2A Protocol is a standardized specification for agent discovery, capability advertisement, and
inter-agent communication. It defines:

- **Agent Discovery**: Standardized endpoints for agent identification
- **Capability Advertisement**: AgentCard format for describing agent skills
- **Communication Protocols**: JSON-RPC 2.0 for agent messaging
- **Security Schemes**: Authentication and authorization patterns
- **Task Management**: Lifecycle management for agent tasks

### Protocol Version
AgentUp implements A2A Protocol **v0.2.6** with full compliance across all specified endpoints and
data structures.

## AgentCard Structure

The AgentCard is the core data structure for agent capability advertisement. AgentUp automatically
generates compliant AgentCards from your plugin configuration.

### Core AgentCard Fields

```json
{
  "protocolVersion": "0.2.6",
  "name": "image-agent",
  "description": "AI Agent image-agent Project.",
  "version": "0.5.0",
  "url": "http://localhost:8000",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true,
    "extensions": null
  },
  "skills": [
    {
      "id": "image_processing",
      "name": "Image Processing",
      "description": "Process and analyze images",
      "inputModes": ["text"],
      "outputModes": ["text"],
      "tags": ["general"],
      "examples": null
    }
  ],
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  "securitySchemes": {
    "X-API-Key": {
      "type": "apiKey",
      "name": "X-API-Key",
      "in": "header",
      "description": "API key for authentication"
    }
  },
  "security": [
    {"X-API-Key": []}
  ],
  "supportsAuthenticatedExtendedCard": false,
  "additionalInterfaces": null,
  "documentationUrl": null,
  "iconUrl": null,
  "preferredTransport": null,
  "provider": null
}
```

### Skills Extraction from Plugin Configuration

AgentUp automatically extracts agent skills from your plugin configuration. **Important**: The skill ID in the AgentCard may differ from the plugin_id in your configuration. The system uses the first capability's ID or derives it from the plugin.

```yaml
# agentup.yml - Actual plugin configuration
plugins:
  - plugin_id: image_vision
    name: Image Vision Plugin
    description: A plugin for image analysis, transformation, and format conversion.
    priority: 50
    tags: ["image", "vision"]
    input_mode: multimodal
    output_mode: multimodal
    capabilities:
      - capability_id: analyze_image
        required_scopes: ["image:read"]
        enabled: true
      - capability_id: transform_image
        required_scopes: ["image:write"]
        enabled: true
```

**Becomes** (note the transformed skill ID and simplified description):

```json
{
  "id": "image_processing",
  "name": "Image Processing",
  "description": "Process and analyze images",
  "inputModes": ["text"],
  "outputModes": ["text"],
  "tags": ["general"],
  "examples": null
}
```

**Key Observations:**
- Plugin `image_vision` becomes skill `image_processing`
- Complex plugin description gets simplified
- `multimodal` input/output modes become `text` in the AgentCard
- Plugin tags `["image", "vision"]` become `["general"]`
- Multiple capabilities are consolidated into a single skill

## Agent Discovery Endpoints

The A2A protocol defines two discovery endpoints that AgentUp implements:

### 1. Public Agent Card (`/.well-known/agent.json`)
**Purpose**: Public agent discovery (A2A Protocol requirement)
**Authentication**: None required
**Response**: AgentCard with public plugins only
**Compliance**: Required by A2A specification

### 2. Authenticated Extended Card (`/agent/authenticatedExtendedCard`) {#authenticated-extended-card}
**Purpose**: Extended capability discovery for authenticated clients
**Authentication**: Required (any configured scheme)
**Response**: AgentCard with both public and extended plugins
**Compliance**: Optional A2A extension

## Plugin Visibility System

AgentUp provides enterprise-grade plugin visibility control through the `visibility` field:

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

### Plugin Visibility Control

The `visibility` field controls which Agent Card includes the plugin:

| Value | Description | Public Card | Extended Card | Use Case |
|-------|-------------|-------------|---------------|----------|
| `"public"` | Default - visible to all | ✓ | ✓ | General capabilities, public APIs |
| `"extended"` | Only visible to authenticated clients | ✗ | ✓ | Sensitive operations, admin functions |

### Skill Mapping Process

The AgentCard generation process (`src/agent/api/routes.py:create_agent_card()`) follows this logic:

1. **Load Plugin Configuration**: Parse plugins from `agentup.yml`
2. **Filter by Visibility**: Include plugins based on card type (public vs extended)
3. **Convert to AgentSkill**: Map plugin fields to A2A AgentSkill format
4. **Generate Capabilities**: Determine agent capabilities from configuration
5. **Apply Security Schemes**: Add authentication requirements
6. **Cache Results**: Cache generated cards for performance

```python
# From src/agent/api/routes.py
def create_agent_card(extended: bool = False) -> AgentCard:
    for plugin in plugins:
        plugin_visibility = plugin.get("visibility", "public")

        # Include plugin based on visibility and card type
        if plugin_visibility == "public" or (extended and plugin_visibility == "extended"):
            agent_skill = AgentSkill(
                id=plugin.get("plugin_id"),
                name=plugin.get("name"),
                description=plugin.get("description"),
                inputModes=[plugin.get("input_mode", "text")],
                outputModes=[plugin.get("output_mode", "text")],
                tags=plugin.get("tags", ["general"]),
            )
            agent_skills.append(agent_skill)
```

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

## A2A Protocol Compliance

AgentUp is fully compliant with A2A Protocol Specification v0.2.6:

### Core Requirements ✓
- **Agent Discovery**: `/.well-known/agent.json` endpoint
- **AgentCard Format**: Compliant data structure and field naming
- **Protocol Version**: Correctly advertises `"protocolVersion": "0.2.6"`
- **JSON-RPC 2.0**: Complete support for agent messaging
- **Security Schemes**: Multiple authentication methods

### Extended Features ✓
- **Authenticated Extended Card**: `/agent/authenticatedExtendedCard` endpoint
- **Plugin Visibility**: Enterprise-grade capability control
- **Streaming Support**: Real-time task execution with SSE
- **Push Notifications**: Webhook-based task updates
- **MCP Integration**: Model Context Protocol extensions

### Task Management ✓
- **Task Lifecycle**: Complete state management (pending → working → completed)
- **Task Cancellation**: Graceful task termination
- **Task Resubscription**: SSE streaming for task updates
- **Push Notification Configuration**: Per-task webhook management

### Communication Protocols ✓
- **JSON-RPC Methods**: All required A2A methods implemented
  - `message/send` - Synchronous messaging
  - `message/stream` - Streaming responses
  - `tasks/get` - Task status retrieval
  - `tasks/cancel` - Task cancellation
  - `tasks/resubscribe` - Task state streaming
  - `tasks/pushNotificationConfig/*` - Push notification management

### Executor Integration

The `GenericAgentExecutor` (`src/agent/core/executor.py`) provides A2A-compliant task execution:

```python
class GenericAgentExecutor(AgentExecutor):
    """A2A-compliant executor for AgentUp agents.
    Handles both direct plugin routing and AI-based routing.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # A2A task lifecycle management
        task = context.current_task or new_task(context.message)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Transition through A2A task states
        await updater.update_status(TaskState.working, ...)

        # Route to appropriate plugin or AI dispatcher
        if direct_plugin := self._find_direct_plugin(user_input):
            result = await self._process_direct_routing(task, direct_plugin)
        else:
            result = await self.dispatcher.process_task(task)

        # Complete with A2A-compliant artifacts
        await self._create_response_artifact(result, task, updater)
```

## Configuration Integration

AgentUp maps YAML configuration to A2A structures:

### Agent Metadata
```yaml
# agentup.yml
name: "Enterprise Agent"           # → AgentCard.name
description: "AI Assistant"       # → AgentCard.description
version: "1.0.0"                  # → AgentCard.version
```

### Capabilities Detection
```yaml
# agentup.yml
api:
  enabled: true                   # → capabilities.streaming: true
push_notifications:
  enabled: true                   # → capabilities.pushNotifications: true
mcp:
  server:
    enabled: true                 # → capabilities.extensions: [MCP]
```

### Security Scheme Generation
```yaml
# agentup.yml
security:
  enabled: true
  auth:
    api_key:
      header_name: "X-API-Key"    # → securitySchemes.X-API-Key
    oauth2:
      required_scopes: ["read"]   # → security: [{"OAuth2": ["read"]}]
```

## Validation and Testing

### Agent Card Validation
```bash
# Validate A2A compliance
curl http://localhost:8000/.well-known/agent.json | jq '.protocolVersion'
# Should return: "0.2.6"

# Check actual skills extraction
curl http://localhost:8000/.well-known/agent.json | jq '.skills[0]'
# Returns skill with potentially different ID than plugin_id

# Test authenticated extended card
curl -H "X-API-Key: your-key" \
     http://localhost:8000/agent/authenticatedExtendedCard
```

### JSON-RPC Testing
```bash
# Test A2A messaging
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"root": {"kind": "text", "text": "Hello"}}]
      }
    },
    "id": 1
  }'
```
