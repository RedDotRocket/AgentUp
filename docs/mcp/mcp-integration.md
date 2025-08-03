# Model Context Protocol (MCP) Integration

AgentUp provides comprehensive support for the Model Context Protocol (MCP), enabling seamless integration
with MCP-compliant tools and servers. This allows your agents to leverage external tools and services through a standardized protocol.

## Overview

MCP (Model Context Protocol) is an open standard that enables Language Models to interact with external tools and data sources in a secure, controlled manner. AgentUp's MCP integration allows your agents to:

- **Connect to MCP servers** via stdio or HTTP transports
- **Use MCP tools** as native agent capabilities
- **Map MCP tools to AgentUp scopes** for fine-grained access control
- **Serve agent capabilities** as MCP tools for other systems
- **Maintain security** through scope-based authorization

## Configuration

MCP support is configured in the `mcp` section of your `agentup.yml`:

```yaml
mcp:
  enabled: true

  # MCP Client - Connect to external MCP servers
  client_enabled: true
  client_timeout: 30            # Timeout for MCP operations

  # MCP Server - Expose agent capabilities via MCP
  server_enabled: false         # Set to true to expose your agent as MCP server
  server_host: "localhost"
  server_port: 8080

  # MCP Server Connections
  servers: []                   # List of MCP servers to connect to
```

## Connecting to MCP Servers

### stdio-based MCP Servers

Connect to MCP servers that communicate via standard input/output:

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
    - name: "filesystem"
      type: "stdio"
      command: "python"              # Can use python, uvx, npx, or any executable
      args: ["/path/to/mcp_server.py"] # Path to your MCP server script
      env:
        DEBUG: "1"                   # Optional environment variables
      working_dir: "/tmp"            # Optional: Set working directory for the server process

      # REQUIRED: Map MCP tools to AgentUp security scopes
      # Tools are automatically prefixed with server name (e.g., "filesystem:read_file")
      tool_scopes:
        "filesystem:read_file": ["files:read"]
        "filesystem:write_file": ["files:write"]
        "filesystem:list_directory": ["files:read"]
        # Also include unprefixed names for compatibility
        read_file: ["files:read"]
        write_file: ["files:write"]
        list_directory: ["files:read"]
```

### Creating a Python MCP Server

Here's a simple example of a Python-based MCP filesystem server:

```python
#!/usr/bin/env python3
"""Simple MCP Filesystem Server"""

import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server instance
server = Server("filesystem-server")
WORKSPACE_DIR = Path("/workspace")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description="Read contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write contents to a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "read_file":
        file_path = WORKSPACE_DIR / arguments["path"]
        content = file_path.read_text()
        return [TextContent(type="text", text=content)]
    elif name == "write_file":
        file_path = WORKSPACE_DIR / arguments["path"]
        file_path.write_text(arguments["content"])
        return [TextContent(type="text", text="File written successfully")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

### Tool Access Control

Tool access is controlled through the `tool_scopes` configuration. **Only tools with explicit scope mappings are available** - this provides security by default.

```yaml
servers:
  - name: "filesystem"
    type: "stdio"
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

**Key Points:**
- **Security by default**: Tools without explicit `tool_scopes` are automatically denied
- **No separate allow/block lists needed**: Simply configure or comment out tools in `tool_scopes`
- **Clear security intent**: Each tool's required permissions are explicitly documented

### HTTP-based MCP Servers

Connect to MCP servers over HTTP:

```yaml
mcp:
  enabled: true
  client_enabled: true
  servers:
    - name: "github"
      type: "http"
      url: "http://localhost:3000/mcp"
      headers:
        Authorization: "Bearer ${GITHUB_TOKEN}"
      timeout: 30                      # Request timeout in seconds (default: 30)

      # REQUIRED: Map tools to scopes (prefixed with server name)
      tool_scopes:
        "github:create_issue": ["github:write"]
        "github:list_issues": ["github:read"]
        "github:update_issue": ["github:write"]
        "github:search_code": ["github:read"]
        # Include unprefixed for compatibility
        create_issue: ["github:write"]
        list_issues: ["github:read"]
        update_issue: ["github:write"]
        search_code: ["github:read"]
```


## Security and Scopes

### Tool-to-Scope Mapping

Each MCP tool **must** be explicitly mapped to one or more AgentUp security scopes. This ensures:

1. **Explicit security configuration**: No tools are available without deliberate security review
2. **Access control enforcement**: Users must have required scopes to use MCP tools
3. **Comprehensive audit trail**: All MCP tool usage is logged with user context
4. **Principle of least privilege**: Tools only get explicitly granted permissions

### Scope Configuration Requirements

```yaml
servers:
  - name: "database"
    type: "stdio"
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

### Tool Name Prefixing

AgentUp automatically prefixes MCP tool names with the server name to avoid conflicts:

- **Server name**: `filesystem`
- **Tool name**: `read_file`
- **Registered as**: `filesystem:read_file` AND `read_file`

Configure both prefixed and unprefixed names in `tool_scopes` for maximum compatibility.


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
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: admin-key-123" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "list files in /tmp"}],
        "message_id": "msg-001",
        "kind": "message"
      }
    },
    "id": "req-001"
  }'
```

### Testing MCP Integration

Test your MCP configuration by:

1. **Starting your agent**: `uv run agentup agent serve`
2. **Checking logs**: Look for MCP tool registration messages
3. **Making test requests**: Use natural language to invoke tools
4. **Verifying security**: Test with insufficient scopes to ensure access is denied

## Exposing Your Agent as an MCP Server

AgentUp can expose your agent's capabilities as an MCP server:

```yaml
mcp:
  enabled: true
  server_enabled: true
  server_host: "0.0.0.0"  # Listen on all interfaces
  server_port: 8080
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
      type: "stdio"
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

    # GitHub HTTP MCP server
    - name: "github"
      type: "http"
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

## Quick Start

1. **Create an MCP server script** (Python example above)
2. **Configure your `agentup.yml`** with server connection and tool scopes
3. **Start your agent**: `uv run agentup agent serve`
4. **Test with natural language**: "List files in /tmp directory"

That's it! Your agent now has MCP tool capabilities with full security integration.
