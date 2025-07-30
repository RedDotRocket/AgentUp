# A2A Streaming Test Guide for AgentUp

!!! warning
    Development is moving fast, and this document may not reflect the latest changes. Once updated, we will remove this warning.

## Overview

This guide covers testing the AgentUp streaming functionality using the `message/stream` endpoint. AgentUp
implements streaming using Server-Sent Events (SSE) to provide real-time responses for long-running AI tasks.

## Streaming Implementation Details

### How AgentUp Streaming Works

1. **Endpoint**: `POST /` with method `message/stream`
2. **Protocol**: JSON-RPC 2.0 over Server-Sent Events (SSE)
3. **Content-Type**: Request uses `application/json`, response uses `text/event-stream`
4. **Authentication**: Same OAuth2/Bearer token auth as regular endpoints
5. **Format**: Each SSE event contains a complete JSON-RPC response

### SSE Event Format

```
data: {"jsonrpc":"2.0","result":{...},"id":"req-123"}

data: {"jsonrpc":"2.0","result":{...},"id":"req-123"}

```

Each event:
- Starts with `data: `
- Contains a complete JSON object
- Ends with double newline (`\n\n`)

## Testing Tools

We provide two comprehensive tools for testing streaming functionality:

### 1. Python CLI Tool (`test_streaming.py`)

**Features:**
- Comprehensive SSE parsing
- Authentication support
- Real-time event display
- Error handling and validation
- Raw data inspection mode

**Usage:**
```bash
# Basic test
python scripts/test_streaming.py

# With authentication
python scripts/test_streaming.py --token gho_xxxx

# Custom message
python scripts/test_streaming.py --message "Tell me a joke"

# Multiple messages with raw output
python scripts/test_streaming.py --token gho_xxxx --raw \
  --message "Hello" --message "Count to 5" --message "Tell me about AI"

# Different server
python scripts/test_streaming.py --url https://my-agent.com --token xxx
```

**Example Output:**
```
🧪 Starting Comprehensive A2A Streaming Tests
==================================================

🔐 Testing authentication...
Authentication successful

🔹 Test 1/1
------------------------------
🚀 Testing streaming endpoint: http://localhost:8000/
📝 Message: Hello, this is a streaming test
🔄 Starting stream...

📡 Response Status: 200
📋 Content-Type: text/event-stream

📨 Event 1:
   🆔 Task ID: task-abc123
   📊 Status: in_progress
   📄 Artifacts (1):
      📎 Agent-result (artifact-xyz)
         💬 Processing your request...

📨 Event 2:
   🆔 Task ID: task-abc123
   📊 Status: completed
   📄 Artifacts (1):
      📎 Agent-result (artifact-xyz)
         💬 Hello! I received your streaming test message. This response demonstrates real-time streaming communication.

Stream completed. Total events: 2

📊 Test Summary
====================
Successful: 1/1
  Failed: 0/1
🎉 All tests passed!
```

### 2. Shell Script (`test_streaming.sh`)

**Features:**
- Pure bash/curl implementation
- No Python dependencies
- Colored output
- Verbose and raw modes
- Connection testing

**Usage:**
```bash
# Basic test
./scripts/test_streaming.sh

# With authentication
./scripts/test_streaming.sh --token gho_xxxx

# Custom message with verbose output
./scripts/test_streaming.sh --verbose --message "Tell me about streaming"

# Raw SSE data inspection
./scripts/test_streaming.sh --raw --token gho_xxxx "Debug streaming"

# Different server and timeout
./scripts/test_streaming.sh --url https://my-agent.com --timeout 60 --token xxx
```

## Manual Testing with curl

For quick manual tests, you can use curl directly:

### Basic Streaming Request

```bash
curl -N -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/stream",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello streaming"}],
        "messageId": "msg-123",
        "kind": "message"
      }
    },
    "id": "req-123"
  }'
```

**Important curl flags:**
- `-N` or `--no-buffer`: Disable output buffering for real-time streaming
- `-H "Accept: text/event-stream"`: Request SSE format
- `-H "Authorization: Bearer TOKEN"`: Include authentication

### Example SSE Response

```
data: {"jsonrpc":"2.0","result":{"id":"task-abc","status":{"state":"in_progress"},"artifacts":[{"name":"Agent-result","parts":[{"kind":"text","text":"Processing..."}]}]},"id":"req-123"}

data: {"jsonrpc":"2.0","result":{"id":"task-abc","status":{"state":"completed"},"artifacts":[{"name":"Agent-result","parts":[{"kind":"text","text":"Hello! This is a streaming response."}]}],"history":[...]},"id":"req-123"}

```

## Testing Scenarios

### 1. Authentication Testing

Test both authenticated and unauthenticated requests:

```bash
# Test without auth (should fail if auth required)
curl -N -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/stream","params":{"message":{"role":"user","parts":[{"kind":"text","text":"test"}],"messageId":"msg-1","kind":"message"}},"id":"req-1"}'

# Test with valid auth token
curl -N -X POST http://localhost:8000/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/stream","params":{"message":{"role":"user","parts":[{"kind":"text","text":"test"}],"messageId":"msg-1","kind":"message"}},"id":"req-1"}'
```

### 2. Long Response Testing

Test with prompts that generate longer responses:

```bash
python scripts/test_streaming.py --token YOUR_TOKEN \
  --message "Please count from 1 to 20 slowly" \
  --message "Tell me a detailed story about a robot" \
  --message "Explain quantum computing in detail"
```

### 3. Error Handling Testing

Test error scenarios:

```bash
# Invalid JSON
curl -N -X POST http://localhost:8000/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"invalid": json}'

# Invalid method
curl -N -X POST http://localhost:8000/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"invalid/method","params":{},"id":"1"}'

# Missing required fields
curl -N -X POST http://localhost:8000/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/stream","id":"1"}'
```

### 4. Load Testing

Test multiple concurrent streams:

```bash
# Run multiple streams in parallel
for i in {1..5}; do
  python scripts/test_streaming.py --token YOUR_TOKEN \
    --message "Concurrent test #$i" &
done
wait
```

## Response Format Validation

### Expected Response Structure

A successful streaming response should contain:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "task-unique-id",
    "kind": "task",
    "status": {
      "state": "in_progress|completed|failed",
      "timestamp": "2025-01-15T10:30:00Z",
      "message": null
    },
    "artifacts": [
      {
        "artifactId": "unique-artifact-id",
        "name": "Agent-result",
        "description": null,
        "parts": [
          {
            "kind": "text",
            "text": "Response content here",
            "metadata": null
          }
        ],
        "metadata": null,
        "extensions": null
      }
    ],
    "history": [
      {
        "role": "user|agent",
        "parts": [...],
        "messageId": "msg-id",
        "kind": "message",
        "contextId": "context-id",
        "taskId": "task-id"
      }
    ],
    "contextId": "context-unique-id",
    "metadata": null
  },
  "id": "request-id"
}
```

### Error Response Structure

Error responses follow JSON-RPC format:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Error description",
    "data": {}
  },
  "id": "request-id"
}
```

## Common Issues and Troubleshooting

### 1. Connection Issues

**Problem**: `Failed to connect to server`
**Solution**: 
- Verify server is running: `curl http://localhost:8000/`
- Check correct URL and port
- Ensure no firewall blocking

### 2. Authentication Issues

**Problem**: `401 Unauthorized` responses
**Solution**:
- Verify token is valid: Test with non-streaming endpoint first
- Check token format: Should be `Bearer TOKEN`
- Ensure proper scopes for GitHub OAuth2

### 3. Streaming Not Working

**Problem**: No SSE events received
**Solution**:
- Verify `Accept: text/event-stream` header
- Use `curl -N` for unbuffered output
- Check agent logs for errors
- Ensure streaming is enabled in agent config

### 4. JSON Parsing Errors

**Problem**: Invalid JSON in SSE events
**Solution**:
- Use `--raw` mode to inspect actual data
- Check for truncated responses
- Verify proper SSE format (`data: {json}\\n\\n`)

### 5. Timeout Issues

**Problem**: Requests timing out
**Solution**:
- Increase timeout: `--timeout 60`
- Check server processing time
- Monitor server resources
- Test with shorter messages

## Integration with Existing Tests

### Adding to Test Suite

To add streaming tests to your existing pytest suite:

```python
import pytest
import httpx
import asyncio

@pytest.mark.asyncio
async def test_streaming_endpoint(auth_token):
    """Test basic streaming functionality."""
    async with httpx.AsyncClient() as client:
        request_data = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "test"}],
                    "messageId": "msg-test",
                    "kind": "message"
                }
            },
            "id": "req-test"
        }
        
        async with client.stream(
            "POST", "http://localhost:8000/",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            },
            json=request_data
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(line[6:])
            
            assert len(events) > 0
            # Validate JSON format of events
            for event_data in events:
                json.loads(event_data)  # Should not raise
```

### CI/CD Integration

Add streaming tests to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Test Streaming Endpoints
  run: |
    # Start agent in background
    agentup agent serve &
    sleep 10
    
    # Run streaming tests
    python scripts/test_streaming.py --timeout 30
    ./scripts/test_streaming.sh --timeout 30
    
    # Kill background agent
    kill %1
```

## Performance Considerations

### 1. Connection Limits

- Monitor concurrent streaming connections
- Implement connection pooling if needed
- Set appropriate timeouts

### 2. Memory Usage

- Long-running streams can accumulate memory
- Monitor server memory during streaming tests
- Implement proper cleanup

### 3. Network Bandwidth

- Streaming responses can be bandwidth-intensive
- Test with various network conditions
- Monitor response times

## Advanced Testing

### Custom SSE Parser

For advanced testing, you can create custom SSE parsers:

```python
import asyncio
import httpx

async def custom_sse_test():
    """Advanced SSE parsing with custom handling."""
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, ...) as response:
            buffer = ""
            async for chunk in response.aiter_bytes():
                buffer += chunk.decode()
                
                while "\\n\\n" in buffer:
                    event, buffer = buffer.split("\\n\\n", 1)
                    
                    for line in event.split("\\n"):
                        if line.startswith("data: "):
                            # Process event
                            handle_sse_event(line[6:])
```

## Summary

The AgentUp streaming functionality provides real-time communication using Server-Sent Events. Use the provided testing tools to:

1. **Validate streaming endpoints** work correctly
2. **Test authentication** with streaming
3. **Monitor performance** under load
4. **Debug issues** with raw data inspection
5. **Integrate** into your test suite

Both Python and shell tools provide comprehensive testing capabilities, while manual curl testing offers quick debugging options.

For production deployments, ensure:
- Proper authentication is configured
- Timeouts are appropriately set
- Error handling is robust
- Performance monitoring is in place