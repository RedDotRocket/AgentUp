# Push Notifications

!!! warning
    Development is moving fast, and this document may not reflect the latest changes. Once updated, we will remove this warning.

AgentUp provides comprehensive push notification capabilities that enable your agents to send asynchronous webhooks when tasks complete,
change state, or require user attention. This allows for real-time integration with external systems and long-running task management.

## Overview

Push notifications in AgentUp allow agents to:

- **Send task updates** to webhook endpoints when tasks complete or change state
- **Handle long-running tasks** without requiring clients to poll for status
- **Integrate with external systems** through webhook delivery
- **Support multiple endpoints** per task for redundancy and fan-out
- **Provide secure delivery** with authentication and URL validation
- **Scale reliably** with persistent storage backends

## How Push Notifications Work

1. **Client sets up webhook**: When sending a task, client provides webhook configuration
2. **Agent stores configuration**: Push notification settings are stored with the task
3. **Task processing**: Agent processes the task (potentially for a long time)
4. **State changes trigger notifications**: When task completes/fails/etc., agent sends HTTP POST to webhooks
5. **Webhook receives update**: Client's webhook endpoint receives complete task information

## A2A Protocol Compliance

AgentUp fully implements the A2A specification for push notifications, supporting all required methods:

- `tasks/pushNotificationConfig/set` - Configure webhook for a task
- `tasks/pushNotificationConfig/get` - Retrieve webhook configuration
- `tasks/pushNotificationConfig/list` - List all webhooks for a task
- `tasks/pushNotificationConfig/delete` - Remove webhook configuration

## Configuration

Push notifications are configured in your `agentup.yml` file. The system supports webhook-based notifications with comprehensive security and validation features.

### Quick Start Configuration

For immediate testing and development:

```yaml
# Minimal configuration for development
push_notifications:
  enabled: true
  backend: webhook      # or memory for testing
  validate_urls: false  # Disable for localhost testing
```

### Basic Configuration

Standard development configuration:

```yaml
# Push notifications configuration
push_notifications:
  enabled: true
  backend: memory             # Options: memory, webhook
  validate_urls: true         # Enable webhook URL validation for security
  config: {}                  # Backend-specific configuration
```

### Production Configuration

For production deployments with webhook delivery:

```yaml
# Push notifications configuration
push_notifications:
  enabled: true
  backend: webhook            # HTTP webhook delivery
  validate_urls: true         # URL validation for security
  config:
    # Webhook delivery settings
    timeout: 10               # Request timeout in seconds
    max_retries: 3           # Retry failed webhooks
    retry_delay: 1.0         # Initial retry delay
    
    # Security settings
    allowed_domains:         # Restrict webhook domains
      - "*.mycompany.com"
      - "webhook.site"      # For testing
      - "localhost"         # For local development
    
    # Default headers for all webhooks
    default_headers:
      User-Agent: "AgentUp/1.0"
      X-Agent-ID: "${AGENT_ID}"
```

### Security Considerations

1. **URL Validation**: When `validate_urls: true`, the system validates webhook URLs:
   - Must be valid HTTP/HTTPS URLs
   - Cannot be private IP addresses (unless explicitly allowed)
   - Domain restrictions can be enforced

2. **Authentication**: Webhooks support multiple authentication methods:
   - Bearer tokens in Authorization header
   - Custom headers
   - Basic authentication

3. **Secure Delivery**: All webhook requests include:
   - Task ID and correlation ID
   - Timestamp and signature (if configured)
   - Custom headers from configuration

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable push notifications |
| `backend` | string | `memory` | Storage backend: `memory` or `webhook` |
| `validate_urls` | boolean | `true` | Enable webhook URL security validation |
| `config.timeout` | integer | `10` | HTTP request timeout in seconds |
| `config.max_retries` | integer | `3` | Maximum retry attempts for failed webhooks |
| `config.retry_delay` | float | `1.0` | Initial retry delay in seconds |
| `config.allowed_domains` | array | `[]` | List of allowed webhook domains (glob patterns) |
| `config.default_headers` | object | `{}` | Headers to include in all webhook requests |

**Note**: The timeout and retry configuration is handled by the HTTP client. The default timeout is 30 seconds per webhook request.

## Setting Up Push Notifications

### Method 1: During Message Send

Include push notification configuration when sending a message:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Generate quarterly report"}],
        "messageId": "msg-001"
      },
      "configuration": {
        "pushNotificationConfig": {
          "url": "https://your-app.com/webhooks/task-updates",
          "token": "your-webhook-token",
          "authentication": {
            "schemes": ["Bearer"],
            "credentials": "your-bearer-token"
          }
        }
      }
    }
  }'
```

### Method 2: Set Configuration Separately

Configure push notifications for an existing task:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "task-uuid-here",
      "pushNotificationConfig": {
        "url": "https://your-app.com/webhooks/task-updates",
        "token": "your-webhook-token"
      }
    }
  }'
```

### Push Notification Configuration Fields

```typescript
interface PushNotificationConfig {
  url: string;                    // Webhook URL (must be HTTPS in production)
  token?: string;                 // Optional client token for validation
  authentication?: {              // Optional authentication for webhook calls
    schemes: string[];            // Authentication schemes: ["Bearer", "ApiKey"]
    credentials?: string;         // Authentication credentials
  };
}
```

## Managing Push Notifications

### Get Configuration

Retrieve current push notification configuration for a task:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tasks/pushNotificationConfig/get",
    "params": {
      "id": "task-uuid-here"
    }
  }'
```

### list All Configurations

list all push notification configurations for a task (supports multiple webhooks):

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tasks/pushNotificationConfig/list",
    "params": {
      "id": "task-uuid-here"
    }
  }'
```

### Delete Configuration

Remove a specific push notification configuration:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tasks/pushNotificationConfig/delete",
    "params": {
      "id": "task-uuid-here",
      "pushNotificationConfigId": "config-uuid-here"
    }
  }'
```

## Webhook Delivery

### Webhook Request Format

When a task state changes, AgentUp sends an HTTP POST request to your webhook URL:

```http
POST /your-webhook-endpoint HTTP/1.1
Host: your-app.com
Content-Type: application/json
User-Agent: AgentUp-PushNotifier/1.0
X-A2A-Notification-Token: your-webhook-token
Authorization: Bearer your-bearer-token

{
  "id": "task-uuid-here",
  "contextId": "context-uuid-here",
  "status": {
    "state": "completed",
    "timestamp": "2025-01-29T10:30:00Z",
    "message": {
      "role": "agent",
      "parts": [{"kind": "text", "text": "Task completed successfully"}],
      "messageId": "response-msg-id"
    }
  },
  "artifacts": [
    {
      "artifactId": "artifact-uuid",
      "name": "quarterly-report.pdf",
      "parts": [
        {
          "kind": "file",
          "file": {
            "name": "report.pdf",
            "mimeType": "application/pdf",
            "uri": "https://storage.example.com/reports/uuid.pdf"
          }
        }
      ]
    }
  ],
  "history": [...],
  "metadata": {...},
  "kind": "task"
}
```

### Webhook Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | Always `application/json` |
| `User-Agent` | `AgentUp-PushNotifier/1.0` |
| `X-A2A-Notification-Token` | Client-provided token for validation (if set) |
| `Authorization` | Authentication header (if configured) |

### Webhook Response

Your webhook should respond with HTTP 200-299 status code to indicate successful receipt:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "received"}
```

## Multiple Webhook Endpoints

AgentUp supports multiple webhook endpoints per task for redundancy and fan-out scenarios:

### Setting Multiple Webhooks

```bash
# Set first webhook
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "task-uuid",
      "pushNotificationConfig": {
        "url": "https://primary-system.com/webhook",
        "token": "primary-token"
      }
    }
  }'

# Set second webhook for the same task
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "task-uuid",
      "pushNotificationConfig": {
        "url": "https://backup-system.com/webhook",
        "token": "backup-token"
      }
    }
  }'
```

When the task completes, both webhook endpoints will receive the notification.

## Security Features

### URL Validation

AgentUp validates webhook URLs to prevent security issues:

- **HTTPS Enforcement**: Production environments require HTTPS URLs
- **SSRF Protection**: Prevents requests to localhost/private IPs (configurable)
- **Scheme Validation**: Only allows HTTP/HTTPS protocols
- **Hostname Validation**: Ensures valid hostnames

### Authentication Support

Webhook calls can include authentication headers:

#### Bearer Token Authentication

```json
{
  "url": "https://your-app.com/webhook",
  "authentication": {
    "schemes": ["Bearer"],
    "credentials": "your-jwt-token"
  }
}
```

Results in header: `Authorization: Bearer your-jwt-token`

#### API Key Authentication

```json
{
  "url": "https://your-app.com/webhook",
  "authentication": {
    "schemes": ["ApiKey"],
    "credentials": "your-api-key"
  }
}
```

Results in header: `X-API-Key: your-api-key`

### Client Token Validation

Include a client token for webhook validation:

```json
{
  "url": "https://your-app.com/webhook",
  "token": "client-generated-token"
}
```

The token is sent in the `X-A2A-Notification-Token` header, allowing your webhook to validate the request origin.

## Storage Backends

### Memory Backend

- **Use case**: Development, testing, single-instance deployments
- **Persistence**: No (lost on agent restart)
- **Performance**: Fastest
- **Configuration**: Default, no additional setup required

```yaml
push_notifications:
  enabled: true
  backend: memory
```

### Valkey Backend

- **Use case**: Production, distributed deployments
- **Persistence**: Yes (survives agent restarts)
- **Performance**: Excellent
- **Configuration**: Requires Valkey service configuration

```yaml
# Required: Valkey service must be configured for Valkey backend
services:
  valkey:
    type: cache
    config:
      url: "${VALKEY_URL:valkey://localhost:6379}"
      db: 0
      max_connections: 20
      retry_on_timeout: true

push_notifications:
  enabled: true
  backend: valkey
  key_prefix: "agentup:push:"
```

**Important**: When using the Valkey backend, you must configure a Valkey service in the `services` section with `type: cache`. The push notification system will automatically discover and use this Valkey service.

## Common Patterns

### Long-Running Task Notifications

```javascript
// Client code example
async function submitLongRunningTask() {
  const response = await fetch('/jsonrpc', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'message/send',
      params: {
        message: {
          role: 'user',
          parts: [{kind: 'text', text: 'Generate comprehensive market analysis'}],
          messageId: 'analysis-request-001'
        },
        configuration: {
          pushNotificationConfig: {
            url: 'https://myapp.com/api/task-completed',
            token: generateSecureToken(),
            authentication: {
              schemes: ['Bearer'],
              credentials: await getAuthToken()
            }
          }
        }
      }
    })
  });
  
  const result = await response.json();
  const taskId = result.result.id;
  
  // Store task ID for tracking
  await storeTaskId(taskId);
  
  // Return immediately - webhook will notify when complete
  return {taskId, message: 'Task submitted, you will be notified when complete'};
}
```

### Webhook Handler Implementation

```javascript
// Express.js webhook handler example
app.post('/api/task-completed', (req, res) => {
  // Validate the notification token
  const token = req.headers['x-a2a-notification-token'];
  if (!validateToken(token)) {
    return res.status(401).json({error: 'Invalid token'});
  }
  
  const task = req.body;
  
  // Handle task completion
  if (task.status.state === 'completed') {
    console.log(`Task ${task.id} completed!`);
    
    // Process artifacts
    if (task.artifacts) {
      task.artifacts.forEach(artifact => {
        console.log(`Artifact: ${artifact.name}`);
        // Download files, process data, etc.
      });
    }
    
    // Notify user
    notifyUser(task.contextId, 'Your task is complete!');
    
  } else if (task.status.state === 'failed') {
    console.log(`Task ${task.id} failed:`, task.status.message);
    notifyUser(task.contextId, 'Your task failed. Please try again.');
  }
  
  res.json({status: 'received'});
});
```

### Multi-System Integration

```yaml
# Configure multiple webhooks for different systems
```

```bash
# Primary business system
curl -X POST http://localhost:8000/ \
  -d '{
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "report-task-001",
      "pushNotificationConfig": {
        "url": "https://business-system.com/api/reports/completed",
        "authentication": {"schemes": ["Bearer"], "credentials": "business-token"}
      }
    }
  }'

# Analytics system
curl -X POST http://localhost:8000/ \
  -d '{
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "report-task-001",
      "pushNotificationConfig": {
        "url": "https://analytics.com/api/task-events",
        "authentication": {"schemes": ["ApiKey"], "credentials": "analytics-key"}
      }
    }
  }'

# Monitoring system
curl -X POST http://localhost:8000/ \
  -d '{
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "report-task-001",
      "pushNotificationConfig": {
        "url": "https://monitoring.com/webhooks/tasks",
        "token": "monitoring-validation-token"
      }
    }
  }'
```

## Error Handling

### Common Error Codes

| Code | Error | Description |
|------|-------|-------------|
| `-32001` | TaskNotFoundError | Task ID not found |
| `-32601` | Method not found | Push notifications not supported |
| `-32602` | Invalid params | Invalid webhook configuration |
| `-32603` | Internal error | Server-side processing error |

### Error Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32001,
    "message": "Task not found",
    "data": "No task found with ID: non-existent-task-id"
  }
}
```

### Webhook Delivery Failures

When webhook delivery fails:

1. **Retry Logic**: AgentUp retries failed deliveries (configurable)
2. **Timeout Handling**: Requests timeout after configured duration
3. **Error Logging**: Failures are logged for debugging
4. **Graceful Degradation**: Agent continues processing even if webhooks fail

## Monitoring and Debugging

### Logging

Enable debug logging to monitor push notification activity:

```python
import logging
logging.getLogger('src.agent.push_notifier').setLevel(logging.DEBUG)
```

### Valkey Inspection

For Valkey backend, inspect stored configurations:

```bash
valkey-cli
> KEYS agentup:push:*
> GET agentup:push:task-id:config-id
```

### Webhook Testing

Test webhook endpoints independently:

```bash
# Test webhook with sample data
curl -X POST https://your-app.com/webhook \
  -H "Content-Type: application/json" \
  -H "X-A2A-Notification-Token: test-token" \
  -d '{
    "id": "test-task",
    "status": {"state": "completed"},
    "kind": "task"
  }'
```

## Best Practices

### Security

1. **Use HTTPS**: Always use HTTPS URLs for webhook endpoints
2. **Validate Tokens**: Check `X-A2A-Notification-Token` in your webhook
3. **Authenticate Requests**: Use Bearer tokens or API keys for webhook authentication
4. **Validate Payloads**: Verify the task data structure and content
5. **Rate Limiting**: Implement rate limiting on your webhook endpoints

### Reliability

1. **Idempotent Handlers**: Make webhook handlers idempotent (safe to retry)
2. **Quick Response**: Respond to webhooks quickly (process asynchronously if needed)
3. **Error Handling**: Handle webhook errors gracefully
4. **Monitoring**: Monitor webhook delivery success rates
5. **Backup Systems**: Use multiple webhooks for critical tasks

### Performance

1. **Async Processing**: Process webhook data asynchronously when possible
2. **Batch Operations**: Batch multiple notifications if your system supports it
3. **Efficient Storage**: Use Valkey backend for high-throughput scenarios
4. **Connection Pooling**: Configure appropriate connection pools

## Troubleshooting

### Common Issues

1. **Webhook Not Receiving Notifications**
   - Verify task state changes trigger notifications
   - Check webhook URL is accessible
   - Confirm push notification is configured for the task
   - Check agent logs for delivery errors

2. **Authentication Failures**
   - Verify authentication credentials are correct
   - Check authentication scheme spelling
   - Ensure webhook endpoint expects the authentication method

3. **Valkey Connection Issues**
   - Verify Valkey server is running and accessible
   - Check Valkey URL format and credentials in environment variables
   - Ensure Valkey service is configured with `type: cache` in the services section
   - Confirm Valkey backend is enabled in push_notifications configuration
   - Check agent logs for Valkey connection errors during startup

4. **URL Validation Errors**
   - Check webhook URL format
   - Verify HTTPS usage in production
   - Disable URL validation for development if needed

### Debug Steps

1. **Check Agent Logs**: Look for push notification related errors
2. **Test Webhook Manually**: Send test requests to webhook endpoint
3. **Verify Configuration**: Confirm push notification settings in agent config
4. **Check Network**: Ensure webhook URL is accessible from agent
5. **Monitor Valkey**: For Valkey backend, check data storage and expiration

## Migration

### Upgrading from Basic Implementation

If upgrading from a basic push notification setup:

1. **Update Configuration**: Add new push notification settings to agent config
2. **Test Multiple Configs**: Verify multiple webhook support
3. **Update Client Code**: Use new list/delete methods if needed
4. **Monitor Delivery**: Ensure webhook delivery continues working

### Moving to Valkey Backend

To migrate from memory to Valkey backend:

1. **Add Valkey Service**: Configure Valkey in services section with `type: cache`
2. **Set Environment Variables**: Ensure `VALKEY_URL` is configured
3. **Update Backend Setting**: Change `push_notifications.backend` from `memory` to `valkey`
4. **Restart Agent**: The system will automatically discover and use the Valkey service
5. **Verify Persistence**: Test that configurations survive restarts

**Example migration configuration**:

```yaml
# Before (memory backend)
push_notifications:
  enabled: true
  backend: memory

# After (Valkey backend)
services:
  valkey:
    type: cache
    config:
      url: "${VALKEY_URL:valkey://localhost:6379}"

push_notifications:
  enabled: true
  backend: valkey
```

## Next Steps

1. **Configure push notifications** in your `agent_config.yaml`
2. **Set up webhook endpoints** in your application
3. **Test with sample tasks** to verify delivery
4. **Implement proper security** with tokens and authentication
5. **Monitor delivery success** and handle failures gracefully

Push notifications enable powerful asynchronous workflows and real-time integration with external systems, making your AgentUp agents more responsive and scalable.