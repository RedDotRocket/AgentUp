# AgentUp MCP Test Servers

This directory contains MCP (Model Context Protocol) test servers for integration testing with AgentUp.

## Available Servers

### Weather Server (`weather_server.py`)

A unified MCP server that provides weather tools using the National Weather Service API. Supports all three MCP transport types.

**Features:**
- Weather alerts by US state
- Weather forecasts by coordinates
- Authentication token support for testing config expansion
- Comprehensive error handling and validation

**Transport Support:**
- `stdio` - Standard input/output transport for subprocess execution
- `sse` - Server-Sent Events transport over HTTP
- `streamable_http` - Streamable HTTP transport

**Tools:**
- `get_alerts(state: str)` - Get weather alerts for a US state code
- `get_forecast(latitude: float, longitude: float)` - Get weather forecast for coordinates

## Usage Examples

### Command Line

```bash
# Run with stdio transport (for AgentUp subprocess execution)
python weather_server.py --transport stdio

# Run with SSE transport on custom port
python weather_server.py --transport sse --port 8123

# Run with streamable HTTP and authentication
python weather_server.py --transport streamable_http --port 8123 --auth-token test-token-123

# Test environment variable expansion
export WEATHER_TOKEN=my-secret-token
python weather_server.py --transport sse --auth-token $WEATHER_TOKEN
```

### AgentUp Configuration

Add to your `agentup.yml`:

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
    # stdio transport
    - name: "weather"
      transport: "stdio"
      command: "python"
      args: ["scripts/mcp/weather_server.py", "--transport", "stdio"]
      tool_scopes:
        get_alerts: ["weather:read"]
        get_forecast: ["weather:read"]
    
    # SSE transport with authentication
    - name: "weather"
      transport: "sse"
      url: "http://localhost:8123/sse"
      headers:
        Authorization: "Bearer ${WEATHER_TOKEN}"
      tool_scopes:
        get_alerts: ["weather:read"]
        get_forecast: ["weather:read"]
    
    # Streamable HTTP transport
    - name: "weather"
      transport: "streamable_http"
      url: "http://localhost:8123/mcp"
      headers:
        Authorization: "Bearer ${WEATHER_TOKEN}"
      tool_scopes:
        get_alerts: ["weather:read"]
        get_forecast: ["weather:read"]
```

## Testing Integration

1. **Start the server:**
   ```bash
   python scripts/mcp/weather_server.py --transport sse --auth-token test-token-123
   ```

2. **Configure AgentUp** with the appropriate transport settings

3. **Test via AgentUp API:**
   ```bash
   curl -X POST http://localhost:8000/ \
     -H "Content-Type: application/json" \
     -H "X-API-Key: admin-key-123" \
     -d '{
       "jsonrpc": "2.0",
       "method": "message/send",
       "params": {
         "message": {
           "role": "user",
           "parts": [{"kind": "text", "text": "Get weather alerts for California"}],
           "message_id": "msg-001",
           "kind": "message"
         }
       },
       "id": "req-001"
     }'
   ```

## Authentication

For HTTP-based transports (SSE and streamable_http), the server supports Bearer token authentication:

- **Header Format:** `Authorization: Bearer <token>`
- **Environment Variable Testing:** Use `${WEATHER_TOKEN}` in AgentUp config to test variable expansion
- **Token Validation:** Server validates the token and returns 401/403 for invalid/missing tokens

## Dependencies

The weather server requires:
- `mcp>=1.0.0` - Official MCP SDK
- `httpx` - HTTP client for NWS API requests
- `uvicorn` - ASGI server for HTTP transports
- `starlette` - Web framework for middleware

Install with:
```bash
uv add "mcp>=1.0.0" httpx uvicorn starlette
```

## Development

To create additional MCP test servers:

1. Import `FastMCP` from `mcp.server.fastmcp`
2. Define tools using the `@mcp.tool()` decorator
3. Support multiple transports using the patterns in `weather_server.py`
4. Include authentication middleware for HTTP transports
5. Add comprehensive error handling and validation
6. Update this README with new server documentation