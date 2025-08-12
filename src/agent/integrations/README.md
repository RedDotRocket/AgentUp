# AgentUp Integrations

This directory contains integrations for AgentUp with external agent frameworks.

## Current Integrations

### CrewAI Integration

Complete integration allowing CrewAI crews to use AgentUp agents as tools via the A2A protocol.

**Key Features:**
- AgentUp agents as CrewAI tools
- Automatic agent discovery via AgentCards
- Streaming response support
- Multi-agent orchestration
- Full A2A protocol compliance
- Authentication and security

**Files:**
- `crewai/agentup_tool.py` - Main CrewAI tool implementation
- `crewai/a2a_client.py` - A2A protocol client
- `crewai/discovery.py` - Agent discovery functionality
- `crewai/models.py` - Pydantic models

**Examples:**
- `examples/basic_crew.py` - Simple integration example
- `examples/multi_agent_flow.py` - Complex workflow example
- `examples/streaming_example.py` - Streaming capabilities demo

**Documentation:**
- `../docs/integrations/crewai-setup-guide.md` - Complete setup guide

## Configuration

Set these environment variables:

```bash
# Enable/disable CrewAI integration
export AGENTUP_CREWAI_ENABLED=true

# Default AgentUp agent URL
export AGENTUP_URL=http://localhost:8000

# API key for authentication
export AGENTUP_API_KEY=your-api-key

# Multiple agent URLs for discovery
export AGENTUP_URLS=http://localhost:8000,http://localhost:8001

# Request timeout (seconds)
export AGENTUP_TIMEOUT=30

# Maximum retries
export AGENTUP_MAX_RETRIES=3

# Auto-discovery settings
export AGENTUP_AUTO_DISCOVERY=false
export AGENTUP_HEALTH_CHECK_INTERVAL=300
```

## Quick Start

### 1. Basic Usage

```python
from agent.integrations.crewai import AgentUpTool
from crewai import Agent, Task, Crew

# Create AgentUp tool
tool = AgentUpTool(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# Use in CrewAI agent
agent = Agent(
    role="Analyst",
    goal="Analyze data using specialized tools",
    tools=[tool]
)

# Create and run crew
task = Task(
    description="Analyze market trends",
    agent=agent
)
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

### 2. Discovery-Based Setup

```python
from agent.integrations.crewai import discover_local_agents

# Automatically discover local AgentUp agents
tools = await discover_local_agents(
    ports=[8000, 8001, 8002],
    api_key="your-api-key"
)

# Use discovered tools in your crew
agent = Agent(tools=tools, ...)
```

## Testing

### Unit Tests

```bash
# Run unit tests
pytest src/agent/integrations/tests/ -v

# Run with coverage
pytest src/agent/integrations/tests/ --cov=src/agent/integrations --cov-report=html
```

### Integration Tests

Requires running AgentUp agents:

```bash
# Start AgentUp agent
agentup agent serve

# Run integration tests
pytest src/agent/integrations/tests/ --run-integration -v
```

## Architecture

```
CrewAI Agent → AgentUpTool → A2AClient → JSON-RPC → AgentUp Agent
                    ↓              ↓
               Tool Interface  Protocol Layer
                    ↓              ↓
              CrewAI Workflow   Authentication
```

## Contributing

When adding new integrations:

1. Create directory: `integrations/[framework]/`
2. Implement core classes and client
3. Add configuration support
4. Create comprehensive examples
5. Write thorough tests
6. Document setup guide

### Integration Checklist

- [ ] Core tool/client implementation
- [ ] A2A protocol support
- [ ] Authentication handling
- [ ] Error handling and retries
- [ ] Async/sync compatibility
- [ ] Discovery functionality
- [ ] Configuration management
- [ ] Unit tests (>90% coverage)
- [ ] Integration tests
- [ ] Usage examples
- [ ] Setup documentation

## Troubleshooting

### Common Issues

1. **Import Errors**: Framework not installed
   ```bash
   pip install crewai  # for CrewAI
   ```

2. **Connection Refused**: AgentUp agent not running
   ```bash
   agentup agent serve
   ```

3. **Authentication Errors**: Check API keys and scopes

4. **Timeout Issues**: Increase timeout or check network

See individual integration documentation for framework-specific troubleshooting.

## Future Integrations

Planned integrations:
- LangGraph
- Microsoft Autogen
- LlamaIndex Agents

## Support

- Documentation: [docs.agentup.dev](https://docs.agentup.dev)
- Issues: [GitHub Issues](https://github.com/RedDotRocket/AgentUp/issues)
- Community: [Discord](https://discord.gg/pPcjYzGvbS)