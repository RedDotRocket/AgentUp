# Push Notification Testing Guide

This guide provides step-by-step manual testing scenarios to verify the complete push notification implementation in AgentUp.

## 🎯 What We've Implemented

### ✅ **Completed Features:**
1. **Missing A2A Methods**: `tasks/pushNotificationConfig/list` and `tasks/pushNotificationConfig/delete`
2. **Multiple Configurations**: Support for multiple push notification configs per task
3. **Enhanced Push Notifier**: Custom implementation with security validation
4. **Persistent Storage**: Valkey backend support for push notification configurations
5. **Security Validation**: Webhook URL validation and authentication support
6. **Configuration Options**: Full configuration in agent_config.yaml templates

### 🔧 **Architecture:**
- **EnhancedPushNotifier**: In-memory implementation with multiple config support
- **ValkeyPushNotifier**: Valkey-backed persistent storage
- **A2A Compliant**: Full JSON-RPC 2.0 compliance for all methods
- **Security Features**: URL validation, authentication headers, SSRF protection

## 🧪 Testing Scenarios

### **Prerequisites:**
1. Start Valkey server: `valkey-server`
2. Create an agent with push notifications enabled
3. Set up a webhook endpoint to receive notifications

### **Test Environment Setup:**

#### 1. Create Test Agent
```bash
# Create a new agent for testing
agentup agent create push-test-agent --template full

# Navigate to the agent directory
cd push-test-agent

# Start the agent
uv run uvicorn src.agent.main:app --reload --port 8000
```

#### 2. Set Up Test Webhook Endpoint

**Option A: Using requestbin.com (Simple)**
1. Go to https://requestbin.com/
2. Create a new request bin
3. Note the webhook URL (e.g., `https://eo3r8b7n1234567.x.pipedream.net/`)

**Option B: Using ngrok + local server (Advanced)**
```bash
# Terminal 1: Start a simple webhook receiver
python3 -c "
import http.server
import socketserver
import json
from urllib.parse import urlparse, parse_qs

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        print('=== WEBHOOK RECEIVED ===')
        print(f'Headers: {dict(self.headers)}')
        print(f'Body: {post_data.decode()}')
        print('========================')
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{\"status\": \"received\"}')

with socketserver.TCPServer(('', 3001), WebhookHandler) as httpd:
    print('Webhook server running on http://localhost:3001')
    httpd.serve_forever()
"

# Terminal 2: Expose with ngrok
ngrok http 3001
# Note the HTTPS URL (e.g., https://abc123.ngrok.io)
```

### **Test Scenarios:**

## **Scenario 1: Basic Push Notification Setup**

### 1.1 Send Message with Push Notification Config

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: m2qA5najRSPWhv2wiBAyGqy6EA07xll" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Generate a report, this will take a while"}],
        "messageId": "test-msg-001"
      },
      "configuration": {
        "pushNotificationConfig": {
          "url": " https://9cbe-82-69-82-102.ngrok-free.app",
          "token": "test-token-123",
        }
      }
    }
  }'
```

**Expected Result:**
- Task created successfully
- Push notification config set automatically
- Response includes task ID

### 1.2 Verify Push Notification Config Set

```bash
# Replace TASK_ID with the ID from step 1.1
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tasks/pushNotificationConfig/get",
    "params": {
      "id": "TASK_ID"
    }
  }'
```

**Expected Result:**
- Returns the push notification configuration
- URL and token should match what was set
- Sensitive data may be masked

## **Scenario 2: Multiple Push Notification Configurations**

### 2.1 Set Additional Push Notification Config

```bash
# Replace TASK_ID with your task ID
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "TASK_ID",
      "pushNotificationConfig": {
        "url": "https://webhook2.example.com/notify",
        "token": "second-webhook-token",
        "authentication": {
          "schemes": ["ApiKey"],
          "credentials": "api-key-value"
        }
      }
    }
  }'
```

**Expected Result:**
- Second configuration added successfully
- Each config gets a unique internal ID

### 2.2 list All Push Notification Configs

```bash
# Replace TASK_ID with your task ID  
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tasks/pushNotificationConfig/list",
    "params": {
      "id": "TASK_ID"
    }
  }'
```

**Expected Result:**
- Returns array of all push notification configurations
- Should show both configs from steps 2.1 and 1.1

## **Scenario 3: Delete Push Notification Configuration**

### 3.1 Delete Specific Configuration

```bash
# Replace TASK_ID and CONFIG_ID with actual values
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tasks/pushNotificationConfig/delete",
    "params": {
      "id": "TASK_ID",
      "pushNotificationConfigId": "CONFIG_ID"
    }
  }'
```

**Expected Result:**
- Returns success (null result)
- Configuration removed from storage

### 3.2 Verify Deletion

```bash
# list configs again to verify deletion
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 6,
    "method": "tasks/pushNotificationConfig/list",
    "params": {
      "id": "TASK_ID"
    }
  }'
```

**Expected Result:**
- Array should have one fewer configuration
- Deleted config should not appear

## **Scenario 4: Webhook Delivery Testing**

### 4.1 Complete a Task to Trigger Webhook

```bash
# Simulate task completion (this depends on your specific agent implementation)
# The agent should automatically send push notifications when task state changes

# You can monitor your webhook endpoint to see if notifications are received
```

**Expected Result:**
- Webhook endpoint receives POST request
- Headers include `Content-Type: application/json`
- Headers include `X-A2A-Notification-Token` if token was set
- Headers include authentication if configured
- Body contains complete Task object as JSON

### 4.2 Check Webhook Data Structure

The webhook should receive data like this:
```json
{
  "id": "task-id-here",
  "contextId": "context-id-here",
  "status": {
    "state": "completed",
    "timestamp": "2025-01-29T10:30:00Z"
  },
  "artifacts": [...],
  "history": [...],
  "kind": "task"
}
```

## **Scenario 5: Security Validation Testing**

### 5.1 Test Invalid Webhook URLs

```bash
# Test localhost URL (should trigger warning but allow in development)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "TASK_ID",
      "pushNotificationConfig": {
        "url": "http://localhost:3001/webhook",
        "token": "test-token"
      }
    }
  }'
```

**Expected Result:**
- Should succeed but log security warning
- In production mode, might reject localhost URLs

### 5.2 Test Invalid URL Schemes

```bash
# Test invalid URL scheme
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 8,
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "TASK_ID",
      "pushNotificationConfig": {
        "url": "ftp://example.com/webhook",
        "token": "test-token"
      }
    }
  }'
```

**Expected Result:**
- Should return error for invalid URL scheme
- Error code should be appropriate JSON-RPC error

## **Scenario 6: Error Handling Testing**

### 6.1 Test Non-Existent Task

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 9,
    "method": "tasks/pushNotificationConfig/get",
    "params": {
      "id": "non-existent-task-id"
    }
  }'
```

**Expected Result:**
- Should return appropriate error
- Error code -32001 (TaskNotFoundError) or similar

### 6.2 Test Non-Existent Configuration

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 10,
    "method": "tasks/pushNotificationConfig/delete",
    "params": {
      "id": "TASK_ID",
      "pushNotificationConfigId": "non-existent-config-id"
    }
  }'
```

**Expected Result:**
- Should return error indicating configuration not found
- Error should be properly formatted JSON-RPC error

## **Valkey Backend Testing**

### Enable Valkey Backend

Update your `agent_config.yaml`:
```yaml
push_notifications:
  enabled: true
  backend: valkey
  key_prefix: "agentup:push:"
  validate_urls: true
```

Restart your agent and repeat the above tests. The behavior should be identical, but configurations will persist across agent restarts.

### Verify Valkey Storage

```bash
# Check Valkey for stored configurations
valkey-cli
> KEYS agentup:push:*
> GET agentup:push:TASK_ID:CONFIG_ID
```

## **Success Criteria**

### ✅ **All Tests Should Pass If:**
1. All JSON-RPC methods return proper responses
2. Multiple configurations can be stored per task
3. list method returns all configurations
4. Delete method removes specific configurations
5. Webhooks are delivered with correct data and headers
6. Security validation prevents obvious attack vectors
7. Error handling returns appropriate JSON-RPC errors
8. Valkey backend persists data across restarts

### 🐛 **Common Issues to Watch For:**
1. Import errors due to missing dependencies
2. Valkey connection failures
3. Webhook delivery timeouts
4. JSON serialization issues
5. Authentication header formatting
6. URL validation false positives

## **Debugging Tips**

1. **Check Logs**: Monitor agent logs for error messages
2. **Valkey Inspection**: Use Valkey CLI to verify data storage
3. **Webhook Testing**: Use online webhook testing tools
4. **Network Issues**: Ensure webhook URLs are accessible
5. **Configuration**: Verify agent_config.yaml settings

This comprehensive testing guide will help you verify that the push notification implementation is working correctly and is fully A2A compliant!