# MCP Streamable HTTP Client Test Scripts

This directory contains test scripts for testing the AgentUp MCP server implementation using the official MCP Python SDK with streamable HTTP transport.

## Prerequisites

1. **Install the MCP Python SDK:**
   ```bash
   pip install mcp
   ```

2. **Start the AgentUp server:**
   ```bash
   # From the AgentUp directory
   agentup agent serve --port 8000
   ```

   Make sure your `agent_config.yaml` has MCP server enabled:
   ```yaml
   mcp:
     enabled: true
     server:
       enabled: true
       expose_handlers: true
       expose_resources: ["agent_status", "agent_capabilities"]
   ```

## Test Scripts

### 1. Simple MCP Test (`simple_mcp_test.py`)

**Quick and focused test of basic MCP functionality.**

```bash
python simple_mcp_test.py
```

This script tests:
- Connection to MCP server
- Tool listing
- Echo tool functionality
- Resource listing and reading
- System info tool

### 2. Comprehensive Test Client (`test_mcp_client.py`)

**Full-featured test client with extensive testing capabilities.**

```bash
# Run full test suite
python test_mcp_client.py

# List available tools
python test_mcp_client.py --list-tools

# List available resources
python test_mcp_client.py --list-resources

# Test specific tool
python test_mcp_client.py --tool echo --args '{"message": "Hello MCP!"}'

# Test with different server
python test_mcp_client.py --url http://localhost:3000 --endpoint /mcp
```

**Features:**
- Comprehensive test suite
- Individual tool testing
- Resource management
- Server information retrieval
- Command-line interface

### 3. Practical Usage Example (`mcp_usage_example.py`)

**Real-world file management demonstration.**

```bash
python mcp_usage_example.py
```

This script demonstrates:
- File creation and management
- Directory exploration
- File reading and analysis
- File hash calculation
- Cleanup operations

## Expected Output

### Successful Connection
```
✅ MCP SDK available
🔗 Testing MCP Streamable HTTP at: http://localhost:8000/mcp
✅ Connected to MCP server
✅ Client session created
✅ Session initialized
```

### Tool Listing
```
🔧 Listing available tools...
Found 12 tools:
  • echo: Echo back user messages with optional modifications
  • read_file: Read file contents
  • write_file: Write content to a file
  • file_exists: Check if file exists
  • get_file_info: Get file information
  • list_directory: List directory contents
  • create_directory: Create a directory
  • delete_file: Delete a file
  • get_system_info: Get system information
  • get_working_directory: Get current working directory
  • execute_command: Execute system command
  • get_file_hash: Get file hash
```

### Tool Execution
```
🔊 Testing echo tool...
Echo result: [{'type': 'text', 'text': 'Echo: Hello from MCP client!'}]
```

## Troubleshooting

### MCP SDK Not Available
```bash
❌ MCP SDK not available: No module named 'mcp'
Install with: pip install mcp
```

**Solution:** Install the MCP Python SDK:
```bash
pip install mcp
```

### Connection Failed
```bash
❌ Connection failed: Connection refused
```

**Solutions:**
1. Make sure AgentUp server is running: `agentup agent serve --port 8000`
2. Check the server URL and port
3. Verify MCP is enabled in your `agent_config.yaml`
4. Check firewall settings

### Tool Not Found
```bash
❌ Tool 'some_tool' not available
```

**Solution:** Use `--list-tools` to see available tools, or check your AgentUp plugin configuration.

### Resource Not Supported
```bash
⚠️  Resources not supported or failed: Method not found
```

**Solution:** Ensure `expose_resources` is configured in your MCP server settings.

## MCP Protocol Details

These scripts use the **Streamable HTTP transport**, which is the recommended transport for production MCP deployments. Key features:

- **Single endpoint**: All MCP communication flows through `/mcp`
- **JSON-RPC 2.0**: Standard protocol for request/response
- **Chunked transfer**: Supports streaming responses
- **Session management**: Maintains connection state
- **Error handling**: Proper error reporting and recovery

## Configuration

The test scripts default to:
- **Server URL**: `http://localhost:8000`
- **MCP Endpoint**: `/mcp`
- **Protocol**: Streamable HTTP

You can customize these values using command-line arguments or by modifying the scripts.

## Integration Notes

These scripts demonstrate how to integrate MCP clients with AgentUp servers. Key patterns:

1. **Connection Management**: Use context managers for proper cleanup
2. **Error Handling**: Graceful handling of network and protocol errors
3. **Tool Discovery**: Dynamic discovery of available tools and resources
4. **Session Lifecycle**: Proper initialization and cleanup of MCP sessions

## Next Steps

After running these tests successfully, you can:

1. **Extend the tests** to cover your specific use cases
2. **Integrate MCP clients** into your applications
3. **Build custom tools** that leverage MCP for agent communication
4. **Deploy MCP servers** in production environments

For more information about MCP, visit the [Model Context Protocol documentation](https://modelcontextprotocol.io/).