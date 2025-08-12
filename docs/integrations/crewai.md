# CrewAI + AgentUp Integration Setup Guide

This guide walks you through setting up and using AgentUp agents as tools within CrewAI workflows. 
The integration enables seamless communication between CrewAI crews and AgentUp agents via the A2A (Agent-to-Agent) protocol.

## Overview

The AgentUp + CrewAI integration allows you to:

- **Use AgentUp agents as CrewAI tools**: Access specialized AgentUp capabilities within CrewAI workflows
- **Automatic discovery**: Discover and configure AgentUp agents automatically via AgentCards
- **Streaming support**: Handle real-time streaming responses from AgentUp agents
- **Multi-agent orchestration**: Coordinate multiple AgentUp agents in complex workflows
- **Protocol compliance**: Full A2A JSON-RPC protocol support with authentication

### Architecture

```
CrewAI Agent → AgentUpTool → A2A Client → JSON-RPC → AgentUp Agent
                    ↓
               Authentication
                    ↓
              Response Processing
```

## Prerequisites

!!! Prerequisites

- Python 3.11 or higher
- AgentUp framework installed (core or with CrewAI extra)
- Network access between CrewAI and AgentUp agents
- CrewAI (optional - can be installed as an extra dependency)


## Installation

### Install AgentUp with CrewAI Support

AgentUp offers flexible installation options. CrewAI is an optional dependency to keep the core package lightweight:

```bash
# Option 1: Install AgentUp with CrewAI integration
pip install agentup[crewai]

# Option 2: Install AgentUp core only (without CrewAI)
pip install agentup

# Option 3: Install from source with CrewAI support
git clone https://github.com/RedDotRocket/agentup.git
cd agentup
pip install -e ".[crewai]"
```

### Install CrewAI Separately (if needed)

If you installed AgentUp without the CrewAI extra, you can add CrewAI later:

```bash
pip install crewai crewai-tools
```

### Core Dependencies

The AgentUp-CrewAI integration requires these core dependencies (automatically installed):

```bash
# Required for A2A protocol communication
httpx         # HTTP client for API calls
pydantic      # Data validation and settings
structlog     # Structured logging

# Optional: For enhanced logging
pip install rich
```

### Verify Installation

Check that the CrewAI integration is available:

```python
# Test import
try:
    from agent.integrations.crewai import AgentUpTool
    print("CrewAI integration is available")
except ImportError:
    print("CrewAI not installed. Install with: pip install agentup[crewai]")
```

### Components Available Without CrewAI

Even without CrewAI installed, you can still use:

- **A2AClient**: Direct communication with AgentUp agents via A2A protocol
- **AgentUpDiscovery**: Discover and query AgentUp agents
- **Models**: Pydantic models for A2A protocol messages

These components are useful for building custom integrations or using AgentUp with other frameworks:

```python
# Works without CrewAI
from agent.integrations.crewai import A2AClient, AgentUpDiscovery

async def use_agentup_directly():
    # IMPORTANT: A2AClient MUST be used as an async context manager
    # This ensures proper resource cleanup and prevents connection leaks
    async with A2AClient(base_url="http://localhost:8000") as client:
        response = await client.send_message("Hello from Python")
        print(response)
    
    # Agent discovery
    discovery = AgentUpDiscovery(["http://localhost:8000"])
    agents = await discovery.discover_agents()
    print(f"Found {len(agents)} agents")
```

## Quick Start

### AgentUp Setup

1. **Create an AgentUp agent**:
   ```bash
   agentup agent create my-specialist-agent
   cd my-specialist-agent
   ```

2. **Configure the agent** (`agentup.yml`):
   ```yaml
   name: "Domain Specialist"
   description: "Specialized agent for domain expertise"
   version: "1.0.0"

   api:
     enabled: true
     host: "0.0.0.0"
     port: 8000

   security:
     enabled: true
     auth:
       api_key:
         keys:
           - key: "crew-integration-key"
             scopes: ["api:read", "api:write"]
   # Populate with your AgentUp plugins
   plugins:
     - plugin_id: "domain_expert"
       name: "Domain Expert"
       enabled: true
   ```

3. **Start the AgentUp agent**:

```bash
agentup agent serve
```


### 1. Basic Integration Example

```python
from crewai import Agent, Task, Crew
from agent.integrations.crewai import AgentUpTool

# Create AgentUp tool
agentup_tool = AgentUpTool(
    base_url="http://localhost:8000",
    api_key="crew-integration-key",
    agent_name="Domain Specialist"
)

# Create CrewAI agent with AgentUp tool
analyst = Agent(
    role="Data Analyst",
    goal="Analyze complex data using specialized tools",
    backstory="Expert analyst with access to domain specialists",
    tools=[agentup_tool],
    verbose=True
)

# Define task
task = Task(
    description="Analyze market trends for renewable energy sector",
    expected_output="Comprehensive market analysis report",
    agent=analyst
)

# Create and run crew
crew = Crew(agents=[analyst], tasks=[task])
result = crew.kickoff()
print(result)
```

### 2. Test the Integration

Run this script to verify everything is working:

```python
#!/usr/bin/env python3
import asyncio
from agent.integrations.crewai import A2AClient

async def test_connection():
    async with A2AClient(
        base_url="http://localhost:8000",
        api_key="crew-integration-key"
    ) as client:
        # Test basic connection
        agent_card = await client.get_agent_card()
        print(f"✅ Connected to: {agent_card.get('name')}")

        # Test message sending
        response = await client.send_message("Hello, can you help me?")
        print(f"📄 Response: {client.extract_text_from_response(response)}")

if __name__ == "__main__":
    asyncio.run(test_connection())
```

## Configuration

### Environment Variables

Set these environment variables for easier configuration:

```bash
# AgentUp agent URL
export AGENTUP_URL="http://localhost:8000"

# API key for authentication
export AGENTUP_API_KEY="crew-integration-key"

# Multiple agent URLs (comma-separated)
export AGENTUP_URLS="http://localhost:8000,http://localhost:8001,http://localhost:8002"

# Logging level
export LOG_LEVEL="INFO"
```

### AgentUp Configuration

#### Security Configuration

For production environments, configure proper security:

```yaml
# agentup.yml
security:
  enabled: true
  auth:
    # API Key Authentication
    api_key:
      keys:
        - key: "your-secure-api-key"
          scopes: ["api:read", "api:write"]
          description: "CrewAI integration key"

    # Or OAuth2 Authentication
    oauth2:
      required_scopes: ["agent:read", "agent:execute"]

  # Scope hierarchy for fine-grained access
  scope_hierarchy:
    admin: ["*"]
    agent:admin: ["agent:read", "agent:execute"]
    api:write: ["api:read"]
```

#### API Configuration

```yaml
api:
  enabled: true
  host: "0.0.0.0"  # Allow external connections
  port: 8000
  cors_enabled: true
  cors_origins: ["*"]  # Configure appropriately for production
  request_timeout: 60
  max_request_size: 16777216  # 16MB
```

### CrewAI Tool Configuration

Configure the AgentUpTool for your specific needs:

```python
from agent.integrations.crewai import AgentUpTool

# Basic configuration
tool = AgentUpTool(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    timeout=30,
    max_retries=3,
    agent_name="Specialist"
)

# Advanced configuration
tool = AgentUpTool(
    base_url="http://your-agent.example.com",
    api_key="secure-api-key",
    timeout=60,
    max_retries=5,
    agent_name="Financial Analysis Expert",
    name="Financial Analyzer",
    description="Specialized tool for financial data analysis and market research"
)
```

## Usage Examples

### 1. Multiple AgentUp Agents

```python
from agent.integrations.crewai import create_agentup_tools

# Configure multiple agents
agent_configs = [
    {
        "name": "Research Specialist",
        "base_url": "http://localhost:8000",
        "api_key": "research-key",
        "description": "Expert in market research and data analysis"
    },
    {
        "name": "Content Creator",
        "base_url": "http://localhost:8001",
        "api_key": "content-key",
        "description": "Specialized in content creation and writing"
    },
    {
        "name": "Technical Analyst",
        "base_url": "http://localhost:8002",
        "api_key": "tech-key",
        "description": "Expert in technical analysis and system design"
    }
]

# Create tools
tools = create_agentup_tools(agent_configs)

# Create CrewAI agent with all tools
coordinator = Agent(
    role="Project Coordinator",
    goal="Coordinate complex projects using specialized agents",
    tools=tools,  # All AgentUp tools available
    verbose=True,
    allow_delegation=True
)
```

### 2. Automatic Agent Discovery

```python
import asyncio
from agent.integrations.crewai import AgentUpDiscovery

async def setup_crew_with_discovery():
    # Discover agents on multiple URLs
    discovery = AgentUpDiscovery(
        base_urls=["http://localhost:8000", "http://localhost:8001"],
        api_key="your-api-key"
    )

    # Get all available tools
    tools = await discovery.create_tools_from_agents()

    # Or get skill-specific tools
    skill_tools = await discovery.create_skill_specific_tools()

    # Find agents by capability
    research_agents = await discovery.find_agents_by_capability("research")

    print(f"Found {len(tools)} general tools")
    print(f"Found {len(skill_tools)} skill-specific tools")
    print(f"Found {len(research_agents)} research agents")

    return tools

# Use in your crew
tools = asyncio.run(setup_crew_with_discovery())
```

### 3. Streaming Responses

```python
from agent.integrations.examples.streaming_example import StreamingAgentUpTool

# Create streaming tool
streaming_tool = StreamingAgentUpTool(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# Use with callback for real-time updates
def progress_callback(chunk: str, chunk_num: int, is_complete: bool):
    if is_complete:
        print(f"\n✅ Completed after {chunk_num} chunks")
    else:
        print(f"Chunk {chunk_num}: {chunk}", end="", flush=True)

# Stream response
result = await streaming_tool.stream_with_callback(
    "Analyze the current state of AI in healthcare",
    callback=progress_callback
)
```

### 4. Complex Multi-Agent Workflow

```python
from agent.integrations.examples.multi_agent_flow import MultiAgentWorkflow

# Define agent configurations
agentup_configs = [
    {"name": "Market Researcher", "base_url": "http://localhost:8000"},
    {"name": "Financial Analyst", "base_url": "http://localhost:8001"},
    {"name": "Strategy Consultant", "base_url": "http://localhost:8002"},
]

# Create workflow
workflow = MultiAgentWorkflow(
    agentup_configs=agentup_configs,
    global_api_key="your-api-key"
)

# Execute complex workflow
result = await workflow.execute_workflow(
    "Develop a market entry strategy for renewable energy in Southeast Asia"
)
```

## Advanced Features

### 1. Context Management

Maintain conversation context across multiple interactions:

```python
# Initialize with context
context_id = "project-alpha-analysis"

# First interaction
result1 = await tool._arun(
    "What are the key market trends in renewable energy?",
    context_id=context_id
)

# Follow-up interaction with context
result2 = await tool._arun(
    "Based on that analysis, what are the investment opportunities?",
    context_id=context_id
)
```

### 2. Health Monitoring

Monitor the health of your AgentUp agents:

```python
# Check individual tool health
is_healthy = tool.health_check()
print(f"Agent health: {'✅' if is_healthy else '❌'}")

# Check all discovered agents
discovery = AgentUpDiscovery(base_urls=agent_urls)
health_status = await discovery.get_agent_health_status()

for url, status in health_status.items():
    print(f"{url}: {'✅' if status else '❌'}")
```

### 3. Capability-Based Routing

Automatically route tasks to appropriate agents:

```python
# Find agents with specific capabilities
nlp_agents = await discovery.find_agents_by_capability("natural language processing")
vision_agents = await discovery.find_agents_by_capability("computer vision")
data_agents = await discovery.find_agents_by_capability("data analysis")

# Create specialized crews
nlp_crew = Crew(
    agents=[Agent(tools=[tool]) for tool in nlp_agents],
    process=Process.sequential
)
```

### 4. Error Handling and Retries

Implement robust error handling:

```python
from agent.integrations.crewai.models import AgentUpConfig

# Configure with retry settings
config = AgentUpConfig(
    base_url="http://localhost:8000",
    api_key="your-key",
    timeout=60,
    max_retries=5
)

tool = AgentUpTool(
    base_url=config.base_url,
    api_key=config.api_key,
    timeout=config.timeout,
    max_retries=config.max_retries
)

# The tool will automatically retry on failures
try:
    result = tool._run("Complex analysis query")
except Exception as e:
    print(f"Failed after {config.max_retries} retries: {e}")
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused
```
Error: Connection refused to http://localhost:8000
```

**Solutions:**
- Verify AgentUp agent is running: `curl http://localhost:8000/health`
- Check firewall settings
- Ensure correct port configuration

#### 2. Authentication Errors
```
Error: HTTP 401 Unauthorized
```

**Solutions:**
- Verify API key is correct
- Check AgentUp security configuration
- Ensure API key has required scopes

#### 3. Timeout Issues
```
Error: Request timeout after 30 seconds
```

**Solutions:**
- Increase timeout in tool configuration
- Optimize AgentUp agent performance
- Check network latency

#### 4. JSON-RPC Errors
```
Error: A2A Error: {'code': -32002, 'message': 'Task not cancelable'}
```

**Solutions:**
- Check A2A protocol compatibility
- Verify AgentUp agent supports requested operations
- Review error codes in logs

### Debugging

Enable detailed logging:

```python
import logging
import structlog

# Configure structured logging
logging.basicConfig(level=logging.DEBUG)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
)

# Now run your integration with detailed logs
```

Check AgentUp agent logs:
```bash
# View AgentUp agent logs
tail -f logs/agent.log

# Or increase logging level
export LOG_LEVEL=DEBUG
agentup agent serve
```

### Performance Optimization

1. **Connection Pooling**: Use async context managers for multiple requests
2. **Caching**: Cache AgentCard responses for discovery
3. **Parallel Processing**: Use asyncio for concurrent agent calls
4. **Timeout Tuning**: Adjust timeouts based on agent response times

## Best Practices

### 1. Security

- **Use environment variables** for API keys
- **Implement least privilege** access with scopes
- **Enable HTTPS** in production
- **Rotate API keys** regularly
- **Monitor access logs** for suspicious activity

```python
import os
from agent.integrations.crewai import AgentUpTool

# Secure configuration
tool = AgentUpTool(
    base_url=os.getenv("AGENTUP_URL"),
    api_key=os.getenv("AGENTUP_API_KEY"),
    agent_name="Secure Agent"
)
```

### 2. Error Handling

```python
import asyncio
from agent.integrations.crewai import AgentUpTool

async def robust_agent_call(tool: AgentUpTool, query: str) -> str:
    """Make a robust call to AgentUp agent with proper error handling."""
    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            result = await tool._arun(query)
            return result
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            raise Exception(f"Agent call timed out after {max_retries} attempts")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(retry_delay)
                continue
            raise Exception(f"Agent call failed after {max_retries} attempts: {e}")
```

### 3. Resource Management

```python
# ALWAYS use async context managers for A2AClient to prevent resource leaks
async def process_multiple_queries(queries: list[str]):
    async with A2AClient(base_url="http://localhost:8000") as client:
        results = []
        for query in queries:
            result = await client.send_message(query)
            results.append(result)
        return results

# Batch process for efficiency
from agent.integrations.crewai import discover_and_filter_tools

tools = await discover_and_filter_tools(
    base_urls=["http://localhost:8000", "http://localhost:8001"],
    required_capabilities=["analysis", "research"]
)
```

### 4. Monitoring and Observability

```python
import time
import structlog
from agent.integrations.crewai import AgentUpTool

logger = structlog.get_logger(__name__)

class MonitoredAgentUpTool(AgentUpTool):
    """AgentUpTool with monitoring capabilities."""

    async def _arun(self, query: str, context_id: str = None) -> str:
        start_time = time.time()

        try:
            logger.info("Agent call started",
                       agent=self.agent_name,
                       query_length=len(query))

            result = await super()._arun(query, context_id)

            duration = time.time() - start_time
            logger.info("Agent call completed",
                       agent=self.agent_name,
                       duration=duration,
                       result_length=len(result))

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error("Agent call failed",
                        agent=self.agent_name,
                        duration=duration,
                        error=str(e))
            raise
```

## API Reference

### AgentUpTool

```python
class AgentUpTool(BaseTool):
    def __init__(
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        agent_name: Optional[str] = None,
        **kwargs
    )

    def _run(query: str, context_id: Optional[str] = None) -> str
    async def _arun(query: str, context_id: Optional[str] = None) -> str
    async def stream_response(query: str, context_id: Optional[str] = None)
    async def get_capabilities() -> dict[str, Any]
    def health_check() -> bool
```

### A2AClient

```python
class A2AClient:
    def __init__(
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    )

    # Context manager methods - handles httpx.AsyncClient lifecycle
    async def __aenter__(self) -> A2AClient
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None

    # All methods require proper context manager usage
    async def send_message(
        message: str,
        context_id: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> dict[str, Any]  # Raises RuntimeError if not in context

    async def stream_message(
        message: str,
        context_id: Optional[str] = None
    ) -> AsyncGenerator[dict[str, Any], None]  # Raises RuntimeError if not in context

    async def get_agent_card() -> dict[str, Any]  # Raises RuntimeError if not in context
    async def get_task_status(task_id: str) -> dict[str, Any]  # Raises RuntimeError if not in context
    def extract_text_from_response(response: dict[str, Any]) -> str  # Safe utility method
```


### AgentUpDiscovery

```python
class AgentUpDiscovery:
    def __init__(
        base_urls: list[str] | str,
        api_key: Optional[str] = None,
        timeout: int = 30
    )

    async def discover_agents() -> list[dict[str, Any]]
    async def create_tools_from_agents() -> list[AgentUpTool]
    async def create_skill_specific_tools() -> list[AgentUpTool]
    async def get_agent_health_status() -> dict[str, bool]
    async def find_agents_by_capability(capability: str) -> list[dict[str, Any]]
```

### Utility Functions

```python
# Standalone query function
async def query_agentup_agent(
    query: str,
    base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None,
    context_id: Optional[str] = None
) -> str

# Multi-tool factory
def create_agentup_tools(agents: list[dict[str, Any]]) -> list[AgentUpTool]

# Local discovery
async def discover_local_agents(
    ports: list[int] = None,
    api_key: Optional[str] = None
) -> list[AgentUpTool]

# Filtered discovery
async def discover_and_filter_tools(
    base_urls: list[str],
    required_capabilities: list[str] = None,
    api_key: Optional[str] = None
) -> list[AgentUpTool]
```

---

## Next Steps

After completing the setup:

1. **Explore the examples** in `src/agent/integrations/examples/`
2. **Run the test scripts** to verify your setup
3. **Customize the integration** for your specific use case
4. **Deploy to production** with proper security configuration
5. **Monitor performance** and optimize as needed

For additional support, check the AgentUp documentation at [docs.agentup.dev](https://docs.agentup.dev) or join the community discussions.

## Testing

### Running Tests

The CrewAI integration tests can be run with or without CrewAI installed:

```bash
# With CrewAI installed (full test suite)
pip install agentup[crewai]
pytest tests/thirdparty/ -v

# Without CrewAI (tests graceful degradation)
pip install agentup
pytest tests/thirdparty/ -v -k "not test_agentup_tool"
```

### Development Testing

For development, you can test both configurations:

```bash
# Test with all extras (including CrewAI)
uv sync --all-extras --dev
uv run pytest tests/thirdparty/ -v

# Test minimal installation
uv sync --dev
uv run pytest tests/test_core/ tests/test_cli/ -v

# Test specific CrewAI integration
uv sync --extra crewai --dev
uv run pytest tests/thirdparty/test_agentup_tool.py -v
```

