# Model Context Protocol (MCP) Integration

AgentUp provides comprehensive support for the Model Context Protocol (MCP), enabling integration
with MCP-compliant tools and servers. This allows your agents to leverage external tools and services through a standardized protocol.

## Overview

MCP (Model Context Protocol) is an open standard that enables Language Models to interact with external tools and data sources in a secure, controlled manner. AgentUp's MCP integration allows your agents to:

- **Connect to MCP servers** via stdio, SSE or Streamable HTTP
- **Use MCP tools** as native agent capabilities
- **Map MCP tools to AgentUp scopes** for fine-grained access control
- **Serve agent capabilities** as MCP tools for other systems

## Configuration

MCP support is configured in the `mcp` section of your `agentup.yml`:

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
    # SSE weather server
    - name: "sse"
      enabled: false
      transport: "sse"
      url: "http://example.com/sse"
      timeout: 30
      headers:
        Authorization: "Bearer ${MCP_API_KEY}"
      tool_scopes:
        # Unprefixed tool names (for compatibility)
        get_alerts: ["alerts:read"]
        get_forecast: ["weather:read"]
```

## Connecting to MCP Servers

### stdio-based MCP Servers

Connect to MCP servers that communicate via standard input/output:

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
    - name: "stdio"
      enabled: true
      transport: "stdio"
      command: "python"
      args: ["path/to/weather_server.py", "--transport", "stdio"]
      timeout: 30
      tool_scopes:
        # Tools to Scope Mapping
        get_alerts: ["alerts:read"]
        get_forecast: ["weather:read"]
```

!!! Note "Command"
    The `command` field specifies the executable to run. This provides polyglot support for MCP servers written in any language, e.g. 'uvx', 'npx', etc.

### SSE-based MCP Servers

Connect to MCP servers that communicate via Server-Sent Events (SSE):

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
  - name: "sse"
        enabled: false
        transport: "sse"
        url: "http://localhost:8123/sse"
        timeout: 30
        headers:
          Authorization: "Bearer ${MCP_API_KEY}"
        tool_scopes:
          # Tools to Scope Mapping
          get_alerts: ["alerts:read"]
          get_forecast: ["weather:read"]
```

!!! Note "Token Authentication"
    The `Authorization` header is used for token-based authentication. Replace `${MCP_API_KEY}` with your actual API key or token or better still, use environment variables to keep sensitive information secure.


### Streamable HTTP-based MCP Servers

Connect to MCP servers that support streaming HTTP responses:

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
    - name: "streamable_http"
      enabled: true
      transport: "streamable_http"
      url: "http://example.com/mcp"
      headers:
        Authorization: "Bearer ${MCP_API_KEY}"
      timeout: 30
      tool_scopes:
        # Tools to Scope Mapping
        get_alerts: ["alerts:read"]
        get_forecast: ["weather:read"]
```

### Authentication

Authentication is handled via the `Authorization` header, which can include API keys or tokens. Use environment variables to keep sensitive information secure.

```yaml
headers:
        Authorization: "Bearer ${MCP_API_KEY}"
```

####   Current MCP Authentication Support

  | Authentication Type | Status | Description |
  |---------------------|--------|-------------|
  | Bearer Token Authentication | ✅ Supported | Simple `Authorization: Bearer <token>` headers |
  | Custom Headers | ✅ Supported | Any HTTP headers can be configured |
  | Environment Variable Expansion | ✅ Supported | Tokens can be loaded from env vars like `${AUTH_TOKEN}` |
  | OAuth2 flows | ❌ Not Supported | Authorization code, client credentials, etc. |
  | Token refresh logic | ❌ Not Supported | Automatic token renewal |
  | Dynamic token acquisition | ❌ Not Supported | Runtime token fetching |
  | JWT token validation | ❌ Not Supported | Token signature verification |

Current unsupported features include OAuth2 flows, token refresh logic, dynamic token acquisition, and JWT validation,
which will be added in future releases. For now, use static tokens or API keys configured via environment variables.

## MCP Tool Configuration

Tool access is controlled through the `tool_scopes` configuration. **Only tools with explicit scope mappings are available** - this provides security by default.

```yaml
servers:
  - name: "filesystem"
    transport: "stdio"
    command: "python"
    args: ["/path/to/mcp_server.py"]
    tool_scopes:
      # ✅ These tools will be available
      "filesystem:read_file": ["files:read"]
      "filesystem:write_file": ["files:write"]

      # ❌ This tool is disabled (commented out)
      # "filesystem:delete_file": ["files:delete"]

      # ✅ Include unprefixed names for compatibility
      read_file: ["files:read"]
      write_file: ["files:write"]
```

#### Tool Name Prefixing

AgentUp automatically prefixes MCP tool names with the server name to avoid conflicts:

- **Server name**: `fileserver`
- **Tool name**: `read_file`
- **Registered as**: `fileserver:read_file` AND `read_file`

```bash
2025-08-04T10:44:31.801840Z [DEBUG    ] Registered MCP tool 'fileserver_read_file:read_file' -> 'fileserver_read_file' with scope enforcement: ['alerts:read'] [agent.mcp_support.mcp_integration]
```

## Security and Scopes

Each MCP tool **must** be explicitly mapped to one or more AgentUp security scopes. This ensures:

1. **Explicit security configuration**: No tools are available without deliberate security review
2. **Access control enforcement**: Users must have required scopes to use MCP tools
3. **Comprehensive audit trail**: All MCP tool usage is logged with user context
4. **Principle of least privilege**: Tools only get explicitly granted permissions

### Scope Configuration Requirements

```yaml
servers:
  - name: "database"
    transport: "stdio"
    command: "mcp-server-postgres"
    args: ["--connection-string", "${DATABASE_URL}"]
    tool_scopes:
      # REQUIRED: Both prefixed and unprefixed tool names
      "database:query": ["db:read"]
      "database:insert": ["db:write"]
      "database:delete": ["db:write", "db:delete"]

      # Include unprefixed for compatibility
      query: ["db:read"]
      insert: ["db:write"]
      delete: ["db:write", "db:delete"]

      # Tools without scope configuration are automatically blocked
      # create_table: ["db:admin"]  # ❌ Disabled by commenting out
```

## Using MCP Tools in Your Agent

Once configured, MCP tools are automatically available to your agent and can be invoked through natural language:

### Natural Language Interface

Users can request MCP tool operations using natural language:

```bash
# File operations
"List the files in the /tmp directory"
"Read the contents of config.json"
"Create a file called notes.txt with the content 'Hello World'"

# Database operations
"Show me all users from the database"
"Insert a new user with email john@example.com"

# GitHub operations
"Create an issue titled 'Bug: Login not working'"
"List all open pull requests"
```

### API Integration

MCP tools can be called via the AgentUp API:

```bash
curl -s -vvv -X POST http://localhost:8000/ \
    -H "Content-Type: application/json" \
    -H "X-API-Key: admin-key-123" \
    -d '{
      "jsonrpc": "2.0",
      "method": "message/send",
      "params": {
        "message": {
          "role": "user",
          "parts": [{"kind": "text", "text": "What is the weather today in New York?"}],
          "message_id": "msg-001",
          "kind": "message"
        }
      },
      "id": "req-001"
    }'
```

## Troubleshooting

### Common Issues

1. **MCP Tool Not Available**
   ```
   INFO: 0 tools available for user
   WARNING: Failed to filter MCP tools by scopes
   ```
   - **Cause**: Tool missing from `tool_scopes` configuration
   - **Fix**: Add tool to `tool_scopes` with required permissions
   - **Example**: `"filesystem:read_file": ["files:read"]`

2. **MCP Server Connection Failed**
   ```
   ERROR: Failed to connect to MCP server filesystem
   ```
   - Check the command path is correct and executable
   - Verify environment variables are set properly
   - Ensure MCP server script has correct permissions (`chmod +x`)
   - Test server independently: `python /path/to/mcp_server.py`

3. **Tool Requires Explicit Scope Configuration**
   ```
   ERROR: MCP tool 'read_file' requires explicit scope configuration
   ```
   - **Cause**: Tool discovered but missing from `tool_scopes`
   - **Fix**: Add both prefixed and unprefixed tool names:
     ```yaml
     tool_scopes:
       "filesystem:read_file": ["files:read"]
       read_file: ["files:read"]
     ```

4. **Permission Denied**
   ```
   ERROR: Insufficient permissions for MCP tool
   ```
   - Check the user's API key has the required scopes
   - Verify `tool_scopes` mapping matches user permissions
   - Review scope hierarchy in security configuration

5. **No MCP Client Registered**
   ```
   ERROR: MCP tool call failed: No MCP client registered
   ```
   - **Cause**: MCP client initialization failed
   - **Fix**: Check MCP server is running and accessible
   - Enable debug logging to see detailed error messages

### Debug Mode

Enable debug logging for MCP to see detailed initialization and tool registration:

```yaml
logging:
  enabled: true
  level: "DEBUG"
  modules:
    "agent.mcp_support": "DEBUG"
    "agent.services.mcp": "DEBUG"
    "agent.core.dispatcher": "DEBUG"
```

**Key debug messages to look for:**
- `✓ MCP clients initialized: 1`
- `✓ Registered MCP tool as capability: filesystem_read_file`
- `✓ Registered MCP client with function registry`
- `✓ AI tool filtering completed: 3 tools available`

## Best Practices

1. **Explicit Security Configuration**: Always configure `tool_scopes` for every tool you want to expose
2. **Include Both Prefixed and Unprefixed Names**: Configure `"server:tool"` and `tool` for maximum compatibility
3. **Scope Hierarchy**: Leverage AgentUp's scope inheritance (e.g., `files:admin` → `files:write` → `files:read`)
4. **Test Security**: Verify tools are blocked when scopes are missing or insufficient
5. **Debug Logging**: Enable debug logging during setup to verify tool registration
6. **Environment Variables**: Use `${VAR}` syntax for sensitive configuration like API keys

## Example: Complete MCP Configuration

```yaml
# Complete MCP configuration example
mcp:
  enabled: true
  client_enabled: true
  client_timeout: 30
  client_retry_attempts: 3

  # Optional: Expose agent as MCP server
  server_enabled: true
  server_host: "0.0.0.0"
  server_port: 8001

  # Connected MCP servers
  servers:
    # Python-based filesystem server
    - name: "filesystem"
      transport: "stdio"
      command: "python"
      args: ["/path/to/filesystem_mcp_server.py"]
      env:
        DEBUG: "1"
      working_dir: "/tmp"
      tool_scopes:
        # REQUIRED: Both prefixed and unprefixed tool names
        "filesystem:read_file": ["files:read"]
        "filesystem:write_file": ["files:write"]
        "filesystem:list_directory": ["files:read"]
        # Include unprefixed for compatibility
        read_file: ["files:read"]
        write_file: ["files:write"]
        list_directory: ["files:read"]

    # GitHub MCP server
    - name: "github"
      transport: "sse"
      url: "http://localhost:3000/mcp"
      headers:
        Authorization: "Bearer ${GITHUB_TOKEN}"
      timeout: 30
      tool_scopes:
        # Prefixed tool names (required)
        "github:create_issue": ["github:write"]
        "github:list_issues": ["github:read"]
        "github:update_issue": ["github:write"]
        # Unprefixed for compatibility
        create_issue: ["github:write"]
        list_issues: ["github:read"]
        update_issue: ["github:write"]
        # Disabled tool (commented out)
        # "github:delete_repo": ["github:admin"]

# Security configuration for MCP tool access
security:
  enabled: true
  scope_hierarchy:
    admin: ["*"]
    files:admin: ["files:write", "files:read"]
    files:write: ["files:read"]
    github:admin: ["github:write", "github:read"]
    github:write: ["github:read"]
  auth:
    api_key:
      header_name: "X-API-Key"
      keys:
        - key: "admin-key-123"
          scopes: ["files:write", "github:read"]
```
