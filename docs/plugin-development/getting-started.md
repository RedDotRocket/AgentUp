# Getting Started with AgentUp Plugins

This guide will walk you through creating your first AgentUp plugin.

In just 5 minutes, you'll have a working plugin with secure capabilities that integrate seamlessly with AI function calling.

## Prerequisites

- AgentUp 2.0+ installed: `uv add agentup` or `pip install agentup`
- Python 3.11 or higher

## Important: Plugin Development Workflow

AgentUp plugins are **standalone Python packages** that can be created anywhere on your system:

```bash
# You can create plugins in any directory
cd ~/my-projects/          # Or any directory you prefer
agentup plugin create time-plugin

# This creates a new plugin directory with the modern decorator system
cd time-plugin/
```

The plugin development workflow is independent of any specific agent project, allowing you to:
- Develop plugins separately from specific agents
- Share plugins across multiple agents
- Publish plugins securely via trusted publishing
- Manage with standard Python tools (uv, pip, poetry)

## New Decorator-Based System

AgentUp introduces a simple, intuitive decorator system

- **@capability decorator**: Define plugin capabilities with a single decorator
- **Type safety**: Full typing support and IDE integration
- **Trusted publishing**: Built-in security with cryptographic verification

## Step 1: Create Your Plugin

Let's create a plugin that provides time and date information:

```bash
# Run this from any directory where you want to create the plugin
agentup plugin create time-plugin
# Note: By default, this creates an AI-enabled plugin. Use --template direct for a basic plugin
```

This creates a new directory with everything you need to get started:

```
time-plugin/
├── .gitignore
├── pyproject.toml
├── README.md
├── src/
│   └── time_plugin/
│       ├── __init__.py
│       └── plugin.py
├── static/
│   └── logo.png
└── tests/
    └── test_time_plugin.py
```

The `pyproject.toml` now includes trusted publishing configuration for secure distribution.

## Step 2: Examine the Generated Code

Open `src/time_plugin/plugin.py`:

```python
"""
Time Plugin plugin for AgentUp with AI capabilities.

A plugin that provides Time Plugin functionality
"""

from typing import Dict, Any

from agent.plugins.base import Plugin
from agent.plugins.decorators import capability
from agent.plugins.models import CapabilityContext


class TimePlugin(Plugin):
    """AI-enabled plugin class for Time Plugin."""

    def __init__(self):
        """Initialize the plugin."""
        super().__init__()
        self.name = "time_plugin"
        self.version = "1.0.0"
        self.llm_service = None

    async def initialize(self, config: Dict[str, Any], services: Dict[str, Any]):
        """Initialize plugin with configuration and services."""
        self.config = config

        # Store LLM service for AI operations
        self.llm_service = services.get("llm")

        # Setup other services as needed
        if "http_client" in services:
            self.http_client = services["http_client"]

    def _get_parameters(self, context: CapabilityContext) -> dict[str, Any]:
        """Extract parameters from context, checking multiple locations for compatibility."""
        params = context.metadata.get("parameters", {})
        if not params and context.task and context.task.metadata:
            params = context.task.metadata
        return params

    @capability(
        id="time_plugin",
        name="Time Plugin",
        description="A plugin that provides Time Plugin functionality",
        scopes=["time-plugin:use", "ai:function"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The input to process with Time Plugin"
                }
            },
            "required": ["input"]
        },
        # A2A AgentSkill metadata (optional - add examples for better AI understanding)
        examples=[
            # Add examples of how to use this capability
            # e.g., "Get the current time",
            # "What's today's date?",
        ]
    )
    async def time_plugin(self, context: CapabilityContext) -> Dict[str, Any]:
        """Execute the time plugin capability."""
        try:
            # Extract parameters for AI functions
            params = self._get_parameters(context)
            input_text = params.get("input", "")

            # If no input in parameters, try to extract from context
            if not input_text:
                input_text = self._extract_task_content(context)

            # Log the start of processing
            self.logger.info("Starting capability execution",
                           capability_id="time_plugin",
                           input_length=len(input_text) if input_text else 0)

            # AI-powered processing
            if self.llm_service and input_text:
                # Example: Use LLM to process time-related queries
                prompt = f"""Process the following time/date related query:

{input_text}

Provide the current time and date information as requested."""

                try:
                    # Call LLM service - adapt to your LLM service interface
                    if hasattr(self.llm_service, 'generate'):
                        response = await self.llm_service.generate(prompt, max_tokens=200)
                    elif hasattr(self.llm_service, 'chat'):
                        response = await self.llm_service.chat(
                            [{"role": "user", "content": prompt}],
                            max_tokens=200
                        )
                    else:
                        # Fallback if LLM service interface is unknown
                        import datetime
                        now = datetime.datetime.now()
                        response = f"Current time: {now.strftime('%I:%M %p')}, Date: {now.strftime('%A, %B %d, %Y')}"

                    result = response.strip() if hasattr(response, 'strip') else str(response)
                except Exception as llm_error:
                    self.logger.warning("LLM processing failed, using fallback", error=str(llm_error))
                    import datetime
                    now = datetime.datetime.now()
                    result = f"Current time: {now.strftime('%I:%M %p')}, Date: {now.strftime('%A, %B %d, %Y')}"
            else:
                # Fallback when no LLM service or no input
                import datetime
                now = datetime.datetime.now()
                result = f"Current time: {now.strftime('%I:%M %p')}, Date: {now.strftime('%A, %B %d, %Y')}"

            # Log successful completion
            self.logger.info("Capability execution completed",
                           capability_id="time_plugin",
                           result_length=len(result) if result else 0)

            return {
                "success": True,
                "content": result,
                "metadata": {
                    "capability": "time_plugin",
                    "ai_powered": bool(self.llm_service),
                    "input_length": len(input_text) if input_text else 0
                }
            }

        except Exception as e:
            # Log the error with structured data
            self.logger.error("Error in capability execution",
                            capability_id="time_plugin",
                            error=str(e),
                            exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "content": f"Error in Time Plugin: {str(e)}"
            }
```

Let's break down the key aspects of the simplified template:

- **Single @capability decorator**: One main capability that can handle various inputs
- **_get_parameters() helper**: Extracts parameters from context reliably (pattern from production plugins)
- **Simplified AI integration**: Direct LLM service usage with fallback logic
- **Clean structure**: Essential methods only - no complex processing modes
- **Flexible input handling**: Works with both AI function parameters and direct context
- **Production patterns**: Based on real working plugins like agentup-systools

## Step 3: Extending Your Plugin

To add more capabilities to your plugin, simply add more @capability decorated methods:

```python
@capability(
    id="get_timezone_info",
    name="Get Timezone Information",
    description="Get timezone information for a location",
    scopes=["time:read"],
    ai_function=True,
    ai_parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name (optional)",
                "default": "local"
            },
            "include_weekday": {
                "type": "boolean",
                "description": "Include day of the week",
                "default": True
            }
        }
    }
)
async def get_datetime(self, timezone: str = "local", include_weekday: bool = True, **kwargs) -> Dict[str, Any]:
    """Get current date and time together."""
    try:
        now = datetime.datetime.now()

        if include_weekday:
            datetime_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
        else:
            datetime_str = now.strftime("%B %d, %Y at %I:%M %p")

        if timezone != "local":
            datetime_str += f" ({timezone})"

        return {
            "success": True,
            "content": f"Current date and time: {datetime_str}",
            "metadata": {
                "timestamp": now.isoformat(),
                "timezone": timezone,
                "include_weekday": include_weekday
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": f"Error getting datetime: {e}"
        }
```

## Step 4: Understanding Automatic Routing

With the new decorator system, routing is handled automatically:

- **AI Function Calling**: When `ai_function=True`, the LLM can directly call your capabilities
- **Scope-Based Security**: Each capability declares required permissions via `scopes`
- **Automatic Discovery**: The plugin registry discovers all @capability decorated methods
- **Parameter Validation**: AI function parameters are automatically validated

No manual routing logic needed! The system intelligently matches user requests to appropriate capabilities based on:

- Function descriptions and parameters
- LLM semantic understanding
- Permission scopes
- Plugin trust levels

## Step 5: Install and Test Your Plugin

```bash
# Install your plugin in development mode
cd time-plugin
uv add -e .     # or pip install -e .

# Verify it's installed and trusted
agentup plugin list
```

You should see your plugin listed with trust information:

```
📦 Installed AgentUp Plugins (1)
================================================================================
Name                           Version    Trust        Publisher
--------------------------------------------------------------------------------
time-plugin                    1.0.0      🟡 community agentup-community
--------------------------------------------------------------------------------
Summary: 🟡 1 community
```

## Step 6: Test in an Agent

Create a simple test agent or use an existing one:

```bash
# Create a test agent
agentup init time-agent

cd time-agent
```

Your plugin is automatically discovered! Just enable it in `agentup.yml`:

```yaml
# agentup.yml
name: "Test Agent"
version: "0.1.0"
description: "A test agent for plugin development"

plugins:
  - plugin_id: time_plugin
    name: Time Plugin
    description: Provides time and date information
    enabled: true
    capabilities:
      - capability_id: get_time
        enabled: true
        required_scopes: ["time:read"]
      - capability_id: get_date
        enabled: true
        required_scopes: ["time:read"]
      - capability_id: get_datetime
        enabled: true
        required_scopes: ["time:read"]
```

Start the agent:

```bash
agentup run
```

Now test your plugin by sending requests:

```bash
# In another terminal - test AI function calling
curl -s -X POST http://localhost:8000/api/chat \
      -H "Content-Type: application/json" \
      -H "X-API-Key: YOUR_KEY" \
      -d '{
        "message": "What time is it in 24-hour format?",
        "conversation_id": "test-001"
      }'
```

Response:
```json
{
  "conversation_id": "test-001",
  "message_id": "msg-789",
  "response": "Current time: 14:25",
  "function_calls": [
    {
      "function": "get_current_time",
      "parameters": {"format": "24hour"},
      "result": {
        "success": true,
        "content": "Current time: 14:25",
        "metadata": {
          "timestamp": "2025-07-31T14:25:33.123456",
          "format": "24hour"
        }
      }
    }
  ],
  "plugin_trust": {
    "plugin_id": "time_plugin",
    "trust_level": "community",
    "publisher": "agentup-community",
    "trusted_publishing": false
  }
}
```

## Step 7: Understanding AI Function Integration

With the new decorator system, AI functions are automatically generated from your @capability decorated methods when `ai_function=True`:

**Automatic AI Function Generation:**
- Method signature becomes function parameters
- `ai_parameters` provides OpenAI function schema
- Return values are automatically formatted
- Type hints provide additional validation

**Example AI function call:**
```python
# This capability:
@capability(
    id="get_time",
    ai_function=True,
    ai_parameters={...}
)
async def get_current_time(self, format: str = "12hour", **kwargs):
    # Your implementation

# Becomes this AI function:
{
    "name": "get_current_time",
    "description": "Get the current time in various formats",
    "parameters": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["12hour", "24hour"],
                "default": "12hour"
            }
        }
    }
}
```

The LLM can directly call your method with proper parameters and receive structured responses.

## Step 8: Test AI Functions

With an AI-enabled agent, your functions are automatically available:

```bash
# Create an AI-enabled agent
agentup init ai-test-agent

cd ai-test-agent

# Configure your AI provider
export OPENAI_API_KEY="your-key-here"
# or export ANTHROPIC_API_KEY="your-key-here"
```

Update `agentup.yml` to configure AI and plugin settings:

```yaml
ai_provider:
  provider: openai  # or anthropic
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}

plugins:
  - plugin_id: time_plugin
    enabled: true
    default_scopes: ["time:read"]
```

Start the agent:

```bash
agentup run
```

Test AI function calling:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-123" \
  -d '{
    "message": "What time is it in 24-hour format?"
  }'
```

The LLM will:
1. Understand the request semantically
2. Call your `get_current_time` function with `format: "24hour"`
3. Return the formatted response to the user

## Step 9: Add Tests

Your plugin already has a test file. Let's add tests for the decorator system:

```python
"""Tests for Time Plugin."""

import pytest
import datetime
from time_plugin.plugin import TimePlugin


@pytest.mark.asyncio
async def test_plugin_capabilities_discovery():
    """Test that capabilities are automatically discovered."""
    plugin = TimePlugin()

    # Capabilities should be auto-discovered from @capability decorators
    assert len(plugin._capabilities) == 3

    capability_ids = [cap.id for cap in plugin._capabilities.values()]
    assert "get_time" in capability_ids
    assert "get_date" in capability_ids
    assert "get_datetime" in capability_ids


@pytest.mark.asyncio
async def test_get_time_capability():
    """Test the get_time capability."""
    plugin = TimePlugin()

    # Test 12-hour format
    result = await plugin.get_current_time(format="12hour")

    assert result["success"] is True
    assert "Current time:" in result["content"]
    assert "AM" in result["content"] or "PM" in result["content"]
    assert result["metadata"]["format"] == "12hour"

    # Test 24-hour format
    result = await plugin.get_current_time(format="24hour")

    assert result["success"] is True
    assert "Current time:" in result["content"]
    assert ":" in result["content"]
    assert result["metadata"]["format"] == "24hour"


@pytest.mark.asyncio
async def test_get_date_capability():
    """Test the get_date capability."""
    plugin = TimePlugin()

    # Test long format
    result = await plugin.get_current_date(format="long")

    assert result["success"] is True
    assert "Current date:" in result["content"]
    assert result["metadata"]["format"] == "long"

    # Test ISO format
    result = await plugin.get_current_date(format="iso")

    assert result["success"] is True
    assert "-" in result["content"]  # ISO format has dashes
    assert result["metadata"]["format"] == "iso"


@pytest.mark.asyncio
async def test_get_datetime_capability():
    """Test the get_datetime capability."""
    plugin = TimePlugin()

    result = await plugin.get_datetime(timezone="local", include_weekday=True)

    assert result["success"] is True
    assert "Current date and time:" in result["content"]
    assert "at" in result["content"]  # Should contain "at" separator
    assert result["metadata"]["timezone"] == "local"
    assert result["metadata"]["include_weekday"] is True


def test_ai_function_schemas():
    """Test that AI function schemas are properly generated."""
    plugin = TimePlugin()

    # Get capability with AI function enabled
    time_capability = None
    for cap in plugin._capabilities.values():
        if cap.id == "get_time":
            time_capability = cap
            break

    assert time_capability is not None
    assert time_capability.ai_function is True
    assert "properties" in time_capability.ai_parameters
    assert "format" in time_capability.ai_parameters["properties"]


def test_scopes_configuration():
    """Test that scopes are properly configured."""
    plugin = TimePlugin()

    for capability in plugin._capabilities.values():
        assert "time:read" in capability.scopes

        # Verify security isolation
        assert "admin" not in capability.scopes
        assert "write" not in capability.scopes[0]  # No write permissions
```

Run your tests:

```bash
# Using uv (recommended)
uv run pytest tests/ -v

# Or using pytest directly
pytest tests/ -v
```

## Step 10: Secure Publishing with Trusted Publishing

Your plugin is ready for secure distribution! The generated `pyproject.toml` includes trusted publishing configuration:

```toml
[project.entry-points."agentup.plugins"]
time_plugin = "time_plugin.plugin:TimePlugin"

# Trusted publishing configuration
[tool.agentup.trusted-publishing]
publisher = "your-github-username"
repository = "your-username/time-plugin"
workflow = "publish.yml"
trust_level = "community"

[tool.agentup.plugin]
capabilities = ["time:current", "date:current"]
scopes = ["time:read"]
min_agentup_version = "2.0.0"
```

**Secure Publishing with GitHub Actions:**

```bash
# Set up trusted publishing (one-time setup)
# 1. Configure PyPI trusted publisher at https://pypi.org/manage/account/publishing/
# 2. Add your GitHub repo: your-username/time-plugin
# 3. Set workflow: publish.yml

# Build and publish via GitHub Actions
git add .
git commit -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags

# GitHub Actions will automatically:
# - Run security scans
# - Validate plugin structure
# - Build and publish to PyPI
# - Create cryptographic attestations
```

**Installation with Trust Verification:**

```bash
# Users can install with trust verification
agentup plugin install time-plugin --require-trusted

# Or verify after installation
agentup plugin verify time-plugin
```

The trusted publishing system provides:
- ✅ Cryptographic verification
- ✅ Publisher identity validation
- ✅ Automatic security scanning
- ✅ Tamper-proof distribution

## Troubleshooting

**Plugin not loading?**
- Check `agentup plugin list` to see if it's discovered
- Verify your entry point in `pyproject.toml` points to the correct class
- Make sure you installed with `uv add -e .` or `pip install -e .`
- Check that your plugin class inherits from `Plugin`

**Capabilities not discovered?**
- Ensure methods are decorated with `@capability`
- Verify the plugin class calls `super().__init__()`
- Check that capability IDs are unique
- Import the decorators: `from agent.plugins.decorators import capability`

**AI functions not working?**
- Set `ai_function=True` in the @capability decorator
- Verify `ai_parameters` follows OpenAI function schema format
- Ensure method signatures match the parameters schema
- Check agent has AI provider configured

**Security/scope errors?**
- Verify required scopes match capability declarations
- Check agent configuration grants necessary permissions
- Use `agentup plugin status` to see trust information
- Ensure plugin is from trusted publisher if required

**Trust verification failing?**
- Check publisher configuration in `pyproject.toml`
- Verify GitHub repository settings for trusted publishing
- Use `agentup plugin verify <plugin-name>` for detailed info
- Ensure PyPI trusted publisher is properly configured

Congratulations! You've built your first AgentUp plugin using the modern decorator system. The new architecture provides:
- ✅ Simple, intuitive development
- ✅ Automatic capability discovery
- ✅ Built-in security and trust verification
- ✅ Seamless AI function integration
- ✅ Production-ready packaging and distribution
