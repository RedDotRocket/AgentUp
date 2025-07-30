# Model Context Protocol (MCP) Integration

!!! warning
    Development is moving fast, and this document may not reflect the latest changes. Once updated, we will remove this warning.

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
      command: "uvx"
      args: ["mcp-server-filesystem", "/workspace"]
      env:
        WORKSPACE_ROOT: "/workspace"
      working_dir: "/project"          # Optional: Set working directory for the server process
      # Map MCP tools to AgentUp security scopes
      tool_scopes:
        read_file: ["files:read"]
        write_file: ["files:write"]
        list_directory: ["files:read"]
        delete_file: ["files:write", "files:delete"]
```

### Tool Filtering

You can control which MCP tools are available from a server using `allowed_tools` and `blocked_tools`:

```yaml
servers:
  - name: "filesystem"
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-filesystem", "/workspace"]
    # Only allow specific tools (if specified, all others are blocked)
    allowed_tools: ["read_file", "list_directory"]
    # Or block specific tools (these are excluded even if in allowed_tools)
    blocked_tools: ["delete_file", "write_file"]
    tool_scopes:
      read_file: ["files:read"]
      list_directory: ["files:read"]
```

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
      # Map tools to scopes
      tool_scopes:
        create_issue: ["github:write"]
        list_issues: ["github:read"]
        update_issue: ["github:write"]
        search_code: ["github:read"]
```


## Security and Scopes

### Tool-to-Scope Mapping

Each MCP tool can be mapped to one or more AgentUp security scopes. This ensures that:

1. **Access control is enforced**: Users must have the required scopes to use MCP tools
2. **Audit trail is maintained**: All MCP tool usage is logged
3. **Principle of least privilege**: Tools only get the permissions they need

Example scope mapping:

```yaml
servers:
  - name: "database"
    type: "stdio"
    command: "mcp-server-postgres"
    args: ["--connection-string", "${DATABASE_URL}"]
    tool_scopes:
      # Read operations
      query: ["db:read"]
      list_tables: ["db:read"]
      describe_table: ["db:read"]

      # Write operations
      insert: ["db:write"]
      update: ["db:write"]
      delete: ["db:write", "db:delete"]

      # Admin operations
      create_table: ["db:admin"]
      drop_table: ["db:admin", "db:delete"]
      backup: ["db:admin", "db:backup"]
```


## Using MCP Tools in Your Agent

Once configured, MCP tools are automatically available to your agent. They can be invoked through:

### 1. AI Routing

The LLM can automatically select and use MCP tools based on user requests:

```yaml
# User: "Read the config.json file"
# Agent automatically uses the filesystem MCP server's read_file tool
```

### 2. Direct Invocation in Plugins

```python
# In your plugin code
async def handle_file_operation(task, mcp_tools):
    # MCP tools are injected when available
    if 'filesystem.read_file' in mcp_tools:
        content = await mcp_tools['filesystem.read_file'](
            path="/workspace/config.json"
        )
        return f"File content: {content}"
```

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

1. **MCP Server Not Found**
   ```
   Error: Failed to start MCP server 'filesystem'
   ```
   - Ensure the command is installed: `pip install mcp-server-filesystem`
   - Check the command path is correct
   - Verify environment variables are set

2. **Permission Denied**
   ```
   Error: User lacks required scope 'files:write' for tool 'write_file'
   ```
   - Check the user's API key has the required scopes
   - Verify tool_scopes mapping is correct
   - Review scope hierarchy in security configuration

3. **Connection Timeout**
   ```
   Error: MCP server 'github' connection timeout
   ```
   - Increase `client_timeout` value
   - Check network connectivity
   - Verify server URL and authentication

### Debug Mode

Enable debug logging for MCP:

```yaml
logging:
  modules:
    agent.mcp_support: "DEBUG"
    agent.services.mcp: "DEBUG"
```

## Best Practices

1. **Scope Design**: Create a logical scope hierarchy that matches your security model
2. **Tool Naming**: Use descriptive names that indicate the tool's purpose and required permissions
3. **Error Handling**: MCP tools should gracefully handle errors and provide meaningful messages
4. **Documentation**: Document required scopes and tool parameters for each MCP server
5. **Testing**: Test MCP integrations with reduced permissions to ensure security

## Example: Complete MCP Configuration

```yaml
# Complete MCP configuration example
mcp:
  enabled: true
  client_enabled: true
  client_timeout: 30
  client_retry_attempts: 3             # Client retry attempts (default: 3)

  # Optional: Expose agent as MCP server
  server_enabled: true
  server_host: "localhost"
  server_port: 8080

  # Connected MCP servers
  servers:
    # Filesystem access
    - name: "filesystem"
      type: "stdio"
      command: "uvx"
      args: ["mcp-server-filesystem", "/workspace"]
      env:
        WORKSPACE_ROOT: "/workspace"
        READONLY: "false"
      tool_scopes:
        read_file: ["files:read"]
        write_file: ["files:write"]
        list_directory: ["files:read"]
        create_directory: ["files:write"]
        delete_file: ["files:delete"]

    # GitHub integration
    - name: "github"
      type: "http"
      url: "https://api.github.com/mcp"
      headers:
        Authorization: "Bearer ${GITHUB_TOKEN}"
        Accept: "application/vnd.github.v3+json"
      timeout: 30
      tool_scopes:
        # Repository operations
        list_repos: ["github:read"]
        create_repo: ["github:write"]
        delete_repo: ["github:admin"]

        # Issue operations
        list_issues: ["github:read"]
        create_issue: ["github:write"]
        update_issue: ["github:write"]
        close_issue: ["github:write"]

        # PR operations
        list_prs: ["github:read"]
        create_pr: ["github:write"]
        merge_pr: ["github:write", "github:merge"]

    # Database access
    - name: "postgres"
      type: "stdio"
      command: "mcp-server-postgres"
      args: ["--connection-string", "${DATABASE_URL}"]
      tool_scopes:
        query: ["db:connect", "db:read"]
        insert: ["db:connect", "db:write"]
        update: ["db:connect", "db:write"]
        delete: ["db:connect", "db:write", "db:delete"]
        execute_ddl: ["db:connect", "db:admin"]
```
