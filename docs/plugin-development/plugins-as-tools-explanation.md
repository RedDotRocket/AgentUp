# Skills as Tools: LLM Function Calling and MCP Integration

This document explains how AgentUp's "skills" work as tools for LLMs and MCP servers, enabling AI systems to discover and call agent capabilities.

## What Are Skills in AgentUp?

In AgentUp, **skills** are the fundamental units of functionality that agents can perform. They can be:

1. **Built-in handlers** - Provided by the framework (e.g., `analyze_image`, `process_document`)
2. **Plugin skills** - Contributed by installed plugins

## Skills as LLM Tools (Function Calling)

### The @ai_function Decorator

Skills can be exposed as LLM-callable functions using the `@ai_function` decorator:

```python
@ai_function(
    description="Echo back user messages with optional modifications",
    parameters={
        "message": {"type": "string", "description": "Message to echo back"},
        "format": {"type": "string", "description": "Format style (uppercase, lowercase, title)"},
    },
)
@register_handler("echo")
async def handle_echo(task: Task) -> str:
    # Handler implementation
    return "Echoed message"
```

### How It Works

1. **Decoration Phase**: The `@ai_function` decorator creates a JSON schema and marks the function:
   ```python
   func._ai_function_schema = {
       "name": "echo",
       "description": "Echo back user messages...",
       "parameters": {
           "type": "object",
           "properties": {
               "message": {"type": "string", "description": "Message to echo back"},
               "format": {"type": "string", "description": "Format style..."}
           },
           "required": ["message", "format"]
       }
   }
   ```

2. **Registration Phase**: During startup, the framework discovers all `@ai_function` decorated handlers and registers them in the `FunctionRegistry`.

3. **LLM Integration**: When an LLM needs to call functions:
   ```python
   # Get all available function schemas
   function_schemas = self.function_registry.get_function_schemas()
   
   # LLM decides which functions to call
   response = await LLMManager.llm_with_functions(llm, messages, function_schemas, function_executor)
   ```

4. **Execution**: When the LLM calls a function, the `FunctionExecutor` routes it to the appropriate handler:
   ```python
   handler = self.function_registry.get_handler(function_name)
   result = await handler(task)
   ```

## Skills as MCP Tools

### MCP Server Mode

AgentUp agents can expose their skills as MCP (Model Context Protocol) tools, making them discoverable by other MCP clients:

```yaml
# agent_config.yaml
mcp:
  enabled: true
  server:
    enabled: true
    name: my-agent-mcp-server
    expose_handlers: true  # Expose skills as MCP tools
```

When `expose_handlers: true`, AgentUp automatically creates MCP tool definitions for all registered skills.

### MCP Client Mode

AgentUp can also consume tools from external MCP servers:

```yaml
# agent_config.yaml
mcp:
  enabled: true
  client:
    enabled: true
    servers:
      - name: filesystem
        command: npx
        args: ['-y', '@modelcontextprotocol/server-filesystem', '/']
      - name: github
        command: npx
        args: ['-y', '@modelcontextprotocol/server-github']
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: '${GITHUB_TOKEN}'
```

### MCP Tool Discovery and Integration

1. **Discovery**: On startup, AgentUp connects to configured MCP servers and discovers available tools:
   ```python
   mcp_tools = await mcp_client.get_available_tools()
   # Returns: [{"name": "read_file", "description": "Read file contents", ...}, ...]
   ```

2. **Registration**: MCP tools are registered alongside local skills in the `FunctionRegistry`:
   ```python
   for tool_schema in mcp_tools:
       function_name = f"mcp_{tool_schema['name']}"
       self._mcp_tools[function_name] = tool_schema
   ```

3. **Unified Access**: LLMs see both local skills and MCP tools as available functions:
   ```python
   def get_function_schemas(self) -> list[dict[str, Any]]:
       all_schemas = list(self._functions.values())      # Local skills
       all_schemas.extend(self._mcp_tools.values())      # MCP tools
       return all_schemas
   ```

4. **Execution Routing**: The framework automatically routes calls to the appropriate backend:
   ```python
   if self.function_registry.is_mcp_tool(function_name):
       result = await self.function_registry.call_mcp_tool(function_name, arguments)
   else:
       handler = self.function_registry.get_handler(function_name)
       result = await handler(task)
   ```

## Practical Example: Complete Flow

Here's how it all works together:

### 1. Agent Configuration
```yaml
# agent_config.yaml
mcp:
  enabled: true
  client:
    enabled: true
    servers:
      - name: filesystem
        command: npx
        args: ['-y', '@modelcontextprotocol/server-filesystem', '/tmp']
  server:
    enabled: true
    expose_handlers: true

skills:
  - plugin_id: analyze_image  # Built-in skill
  - plugin_id: ai_assistant   # AI-powered skill that can call tools
```

### 2. Available Tools to LLM
When the AI assistant processes a request, it sees these functions:
- `analyze_image` - From AgentUp's built-in multi-modal handler
- `mcp_read_file` - From the filesystem MCP server  
- `mcp_write_file` - From the filesystem MCP server
- Any plugin skills that are registered

### 3. LLM Function Calling
```
User: "Please analyze the image in /tmp/chart.png and save a summary to /tmp/analysis.txt"

LLM thinks: I need to read the file, analyze it, and write results
1. Calls: mcp_read_file(path="/tmp/chart.png") 
2. Calls: analyze_image(image_data=<binary data>)
3. Calls: mcp_write_file(path="/tmp/analysis.txt", content="Chart shows...")
```

### 4. Routing and Execution
```python
# Step 1: MCP tool call
await mcp_client.call_tool("read_file", {"path": "/tmp/chart.png"})

# Step 2: Local skill call  
analyze_handler = get_handler("analyze_image")
result = await analyze_handler(task_with_image_data)

# Step 3: MCP tool call
await mcp_client.call_tool("write_file", {"path": "/tmp/analysis.txt", "content": result})
```

## Configuration-Driven Tool Exposure

### Skill Definitions in Agent Config

```yaml
skills:
  - plugin_id: weather_lookup
    name: Weather Lookup
    description: Get current weather for a location
    tags: [weather, external_api]
    # This skill can be called by LLMs when AI routing is enabled
    
  - plugin_id: file_processor  
    name: File Processor
    description: Process uploaded files
    tags: [file, processing, multimodal]
    # This skill handles file uploads and can be called via function calling
```

### AI Routing Mode

```yaml
# agent_config.yaml
routing:
  default_mode: ai  # Skills available as LLM tools

# OR per-skill
skills:
  - plugin_id: data_analysis
    routing_mode: ai  # Available as LLM tool
    
  - plugin_id: simple_greeting
    routing_mode: direct  # Direct keyword matching only
    keywords: [hello, hi]
```

## Benefits of Skills as Tools

1. **Unified Interface**: LLMs see all capabilities (local skills + MCP tools) as a single set of functions
2. **Automatic Discovery**: No manual tool registration - skills are automatically exposed
3. **A2A Compliance**: All tool calls go through the standard A2A task execution pipeline
4. **Middleware Inheritance**: Tool calls get all configured middleware (caching, rate limiting, etc.)
5. **Multi-modal Support**: Tools can process images, documents, and mixed content
6. **Cross-Agent Composition**: Agents can call each other's skills via MCP

## Real-World Scenarios

### 1. Content Processing Pipeline
```
User uploads image + asks for analysis
→ LLM calls analyze_image(image_data)
→ LLM calls mcp_search_web(query="similar charts")  
→ LLM calls summarize_findings(data=[...])
→ Returns comprehensive analysis
```

### 2. Development Assistant
```
User: "Check the status of my GitHub repo and update the README"
→ LLM calls mcp_github_get_repo_status()
→ LLM calls mcp_github_get_file(path="README.md")
→ LLM calls generate_documentation(repo_data=...)
→ LLM calls mcp_github_update_file(path="README.md", content=...)
```

### 3. Multi-Agent Workflow
```
Agent A exposes: code_analysis, security_scan
Agent B exposes: documentation_generation  
Agent C (orchestrator) can call tools from both A and B via MCP
```

## Summary

AgentUp's skills system creates a seamless bridge between:
- **A2A protocol messages** (how agents communicate)
- **LLM function calling** (how AI systems invoke capabilities)  
- **MCP tools** (how agents share capabilities)

This architecture enables:
- AI systems to discover and use agent capabilities automatically
- Agents to expose their skills to other agents and AI systems
- Complex workflows that span multiple agents and external tools
- Consistent middleware application regardless of how skills are invoked

The key insight is that **skills are not just handlers** - they're discoverable, callable, composable units of functionality that can be orchestrated by AI systems and shared across agent networks.