# AgentUp Demo Quick Reference

## Quick Setup Commands

```bash
# Environment setup
export OPENAI_API_KEY="your-key-here"
mkdir -p ~/agentup-demo && cd ~/agentup-demo

# Create Research Coordinator (Advanced)
agentup agent create research-coordinator --template advanced --output-dir ./research-coordinator

# Create Data Analyst (Standard)  
agentup agent create data-analyst --template standard --output-dir ./data-analyst

# Start agents (in separate terminals)
cd research-coordinator && agentup agent serve --port 8001
cd data-analyst && agentup agent serve --port 8002
```

## Test Commands

### Authentication Test
```bash
# Valid auth
curl -X GET http://localhost:8001/agentcard -H "X-API-Key: research-coordinator-key-12345"

# Invalid auth (should fail)
curl -X GET http://localhost:8001/agentcard
```

### AgentCard Discovery
```bash
curl -X GET http://localhost:8001/agentcard -H "X-API-Key: research-coordinator-key-12345" | jq
curl -X GET http://localhost:8002/agentcard -H "X-API-Key: data-analyst-key-67890" | jq
```

### LLM Routing Test
```bash
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: research-coordinator-key-12345" \
  -d '{"jsonrpc":"2.0","method":"send_message","params":{"messages":[{"role":"user","content":"I need help analyzing sales trends"}]},"id":"1"}'
```

### Keyword Routing Test
```bash
curl -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: data-analyst-key-67890" \
  -d '{"jsonrpc":"2.0","method":"send_message","params":{"messages":[{"role":"user","content":"calculate statistics for 10 20 30 40 50"}]},"id":"1"}'
```

### MCP Direct Call
```bash
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"calculate_statistics","arguments":{"data":[100,200,150,175,125],"metrics":["mean","median","std"]}},"id":"1"}'
```

### Memory/Context Test
```bash
# First message
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: research-coordinator-key-12345" \
  -d '{"jsonrpc":"2.0","method":"send_message","params":{"context_id":"session_1","messages":[{"role":"user","content":"Start research on customer satisfaction"}]},"id":"1"}'

# Follow-up (should remember context)
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: research-coordinator-key-12345" \
  -d '{"jsonrpc":"2.0","method":"send_message","params":{"context_id":"session_1","messages":[{"role":"user","content":"Add survey analysis"}]},"id":"2"}'
```

## Key Configuration Snippets

### MCP Client Configuration
```yaml
mcp:
  enabled: true
  client:
    enabled: true
    servers:
      - name: "data_analyst"
        transport: "http"
        endpoint: "http://localhost:8082/mcp"
        streaming: true
```

### MCP Server Configuration  
```yaml
mcp:
  enabled: true
  server:
    enabled: true
    expose_handlers: true
    port: 8082
    tools:
      - name: "calculate_statistics"
        description: "Calculate statistical measures"
        input_schema:
          type: object
          properties:
            data:
              type: array
              items:
                type: number
```

### Authentication Configuration
```yaml
security:
  strategies:
    - type: api_key
      header: X-API-Key
      enabled: true
      keys:
        - "your-api-key-here"
```

### AI Routing Configuration
```yaml
ai:
  enabled: true
  llm_service: "openai"
  model: "gpt-4o-mini"
  system_prompt: "You are an AI assistant..."
  fallback_to_routing: true
```

### Middleware Configuration
```yaml
middleware:
  - type: "caching"
    enabled: true
    ttl: 600
  - type: "rate_limiting"
    enabled: true
    requests_per_minute: 60
  - type: "timing"
    enabled: true
```

## Validation Commands

```bash
# Validate configuration
agentup validate --check-env --check-handlers

# Add skill
agentup add-skill --name "Skill Name" --id "skill_id"

# Deploy
agentup deploy --type docker
```

## Features Demonstrated

✓ CLI Usage (agent create, add-skill, validate)  
✓ Templates (Advanced, Standard)  
✓ MCP (Client & Server)  
✓ Authentication (API Key)  
✓ Routing (LLM & Keyword)  
✓ Skills (Custom handlers)  
✓ AgentCard (Discovery)  
✓ Memory (Context persistence)  
✓ Middleware (Caching, Rate limiting, Timing)  
✓ Services (LLM integration)  
✓ Validation (Config checking)

## Troubleshooting

- **Port conflicts**: Use different ports if 8001/8002 are busy
- **Auth errors**: Check API key in headers
- **MCP connection**: Start Data Analyst before Research Coordinator  
- **Missing deps**: Run `pip install -e .` in AgentUp root
- **Config errors**: Use `validate` command to check syntax

## Useful Endpoints

- **AgentCard**: GET `/agentcard`
- **Health**: GET `/health`  
- **Status**: GET `/status`
- **Metrics**: GET `/metrics`
- **MCP**: POST `/mcp` (for MCP servers)
- **Main API**: POST `/` (JSON-RPC)