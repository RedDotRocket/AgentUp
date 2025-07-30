# Getting Started with AgentUp Plugins

This guide will walk you through creating your first AgentUp plugin from scratch.

In just 5 minutes, you'll have a working plugin that can handle user requests
and integrate with AI function calling.

## Prerequisites

- AgentUp installed: `pip install agentup`
- Python 3.10 or higher
- Basic familiarity with Python

## Important: Plugin Development Workflow

AgentUp plugins are **standalone Python packages** that can be created anywhere on your system:

```bash
# You can create plugins in any directory
cd ~/my-projects/          # Or any directory you prefer
agentup plugin create time-plugin --template direct

# This creates a new plugin directory
cd time-plugin/
```

The plugin development workflow is independent of any specific agent project, allowing you to:
- Develop plugins separately from specific agents
- Share plugins across multiple agents
- Publish plugins for community use

You can of course also create plugins directly within an agent project, but this is not required.

The benefits of this approach, mean plugins can be listed in existing Python tooling
and managed with pip, uv, poetry, or any other Python package manager.

## Step 1: Create Your Plugin

Let's create a plugin that provides time and date information:

```bash
# Run this from any directory where you want to create the plugin
agentup plugin create time-plugin --template direct
```

This creates a new directory with everything you need to get started:

```
time-plugin/
├── pyproject.toml          # Package configuration
├── README.md               # Documentation
├── src/
│   └── time_plugin/
│       ├── __init__.py
│       └── plugin.py       # Your plugin code
└── tests/
    └── test_time_plugin.py # Tests
```

## Step 2: Examine the Generated Code

Open `src/time_plugin/plugin.py` to see the basic plugin structure:

```python
"""
Time Plugin plugin for AgentUp.

A plugin that provides Time Plugin functionality
"""

import pluggy
from agent.plugins import PluginDefinition, CapabilityContext, CapabilityResult, PluginValidationResult, CapabilityType

hookimpl = pluggy.HookimplMarker("agentup")

class Plugin:
    """Main plugin class for Time Plugin."""

    def __init__(self):
        """Initialize the plugin."""
        self.name = "time-plugin"

    @hookimpl
    def register_capability(self) -> PluginDefinition:
        """Register the capability with AgentUp."""
        return PluginDefinition(
            id="time_plugin",
            name="Time Plugin",
            version="0.1.0",
            description="A plugin that provides Time Plugin functionality",
            capabilities=[CapabilityType.TEXT],
            tags=["time-plugin", "custom"],
        )

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Execute the capability logic."""
        # Extract user input from the task
        user_input = self._extract_user_input(context)

        # Your skill logic here
        response = f"Processed by Time Plugin: {user_input}"

        return CapabilityResult(
            content=response,
            success=True,
            metadata={"skill": "time_plugin"},
        )

    def _extract_user_input(self, context: CapabilityContext) -> str:
        """Extract user input from the task."""
        if hasattr(context.task, "history") and context.task.history:
            last_msg = context.task.history[-1]
            if hasattr(last_msg, "parts") and last_msg.parts:
                return last_msg.parts[0].text if hasattr(last_msg.parts[0], "text") else ""
        return ""

    # ... more methods
```

## Step 3: Implement Time Functionality

Let's replace the basic logic with actual time functionality. Update the `execute_capability` method:

```python
import datetime
import re

@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    """Execute the time skill logic."""
    # Extract user input from the task
    user_input = self._extract_user_input(context).lower()

    try:
        # Get current time once for consistency
        now = datetime.datetime.now()

        if any(word in user_input for word in ['time', 'clock', 'hour']):
            response = f"The current time is {now.strftime('%I:%M %p')}"

        elif any(word in user_input for word in ['date', 'today', 'day']):
            response = f"Today is {now.strftime('%A, %B %d, %Y')}"

        elif any(word in user_input for word in ['datetime', 'both']):
            response = f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"

        else:
            # Default response
            response = f"Current time: {now.strftime('%I:%M %p on %A, %B %d, %Y')}"

        return CapabilityResult(
            content=response,
            success=True,
            metadata={"capability": "time_plugin", "timestamp": now.isoformat()},
        )

    except Exception as e:
        return CapabilityResult(
            content=f"Sorry, I couldn't get the time information: {str(e)}",
            success=False,
            error=str(e),
        )
```

## Step 4: Improve the Routing Logic

Update the `can_handle_task` method to better detect time-related requests:

```python
@hookimpl
def can_handle_task(self, context: CapabilityContext) -> float:
    """Check if this capability can handle the task."""
    user_input = self._extract_user_input(context).lower()

    # Define time-related keywords with their confidence scores
    time_keywords = {
        'time': 1.0,
        'clock': 0.9,
        'hour': 0.8,
        'minute': 0.8,
        'date': 1.0,
        'today': 0.9,
        'day': 0.7,
        'datetime': 1.0,
        'when': 0.6,
        'now': 0.8,
    }

    # Calculate confidence based on keyword matches
    confidence = 0.0
    for keyword, score in time_keywords.items():
        if keyword in user_input:
            confidence = max(confidence, score)

    # Boost confidence for specific phrases
    if any(phrase in user_input for phrase in [
        'what time', 'current time', 'what date', 'what day'
    ]):
        confidence = 1.0

    return confidence
```

## Step 5: Install and Test Your Plugin

```bash
# Install your plugin in development mode
cd time-plugin
pip install -e .

# Verify it's installed
agentup plugin list
```

You should see your plugin listed:

```
┌─────────────────────────────── Loaded Plugins ───────────────────────────────┐
│ Plugin      │ Version │ Status │ Skills │ Source    │ Author │
├─────────────┼─────────┼────────┼────────┼───────────┼────────┤
│ time_plugin │ 0.1.0   │ loaded │ 1      │ entry_point │ Your Name │
└─────────────┴─────────┴────────┴────────┴───────────┴────────┘

┌─────────────────────────────── Available Skills ─────────────────────────────┐
│ Skill ID    │ Name        │ Plugin      │ Capabilities │
├─────────────┼─────────────┼─────────────┼──────────────┤
│ time_plugin │ Time Plugin │ time_plugin │ text         │
└─────────────┴─────────────┴─────────────┴──────────────┘
```

## Step 6: Test in an Agent

Create a simple test agent or use an existing one:

```bash
# Create a test agent
agentup agent create test-agent --template minimal

cd test-agent
```

Now you need to register your plugin in the agent's configuration. Edit `agent_config.yaml` and add your plugin to the skills section:

```yaml
# agent_config.yaml
agent:
  name: "Test Agent"
  version: "0.1.0"
  description: "A test agent for plugin development"

skills:
  - skill_id: time_plugin
    name: Echo
    description: Echo back the input text
    tags: [time, basic, simple]
    input_mode: text
    output_mode: text
    keywords: [what, time, now]
    patterns: ['.time']  # Catch-all for minimal template
    routing_mode: direct  # Use direct routing for keyword-based matching
    priority: 50
```

Start the agent:

```bash
agentup agent serve
```

Now test your plugin by sending requests:

```bash
# In another terminal
curl -s -X POST http://localhost:8000/ \
      -H "Content-Type: application/json" \
      -H "X-API-Key: YOUR_KEY" \ # change to your agent's API key
      -d '{
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
          "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "What time is it?"}],
            "messageId": "msg-001",
            "contextId": "context-001",
            "kind": "message"
          }
        },
        "id": "req-001"
      }'
```

Response:
```json
{
  "id": "req-001",
  "jsonrpc": "2.0",
  "result": {
    "artifacts": [
      {
        "artifactId": "7d3efd3a-a00c-4967-86ac-6d2059a304f6",
        "description": null,
        "extensions": null,
        "metadata": null,
        "name": "test-agent-result",
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Current time: 06:44 AM on Thursday, July 03, 2025"
          }
        ]
      }
    ],
    "contextId": "context-001",
    "history": [
      {
        "contextId": "context-001",
        "extensions": null,
        "kind": "message",
        "messageId": "msg-005",
        "metadata": null,
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "What time is it?"
          }
        ],
        "referenceTaskIds": null,
        "role": "user",
        "taskId": "ddbc8dfb-b56e-4fa2-9285-45778756ed3c"
      },
      {
        "contextId": "context-001",
        "extensions": null,
        "kind": "message",
        "messageId": "006a1538-6e9a-4080-b6ec-470207e2557d",
        "metadata": null,
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Processing request with for task ddbc8dfb-b56e-4fa2-9285-45778756ed3c using test-agent."
          }
        ],
        "referenceTaskIds": null,
        "role": "agent",
        "taskId": "ddbc8dfb-b56e-4fa2-9285-45778756ed3c"
      }
    ],
    "id": "ddbc8dfb-b56e-4fa2-9285-45778756ed3c",
    "kind": "task",
    "metadata": null,
    "status": {
      "message": null,
      "state": "completed",
      "timestamp": "2025-07-03T05:44:18.406491+00:00"
    }
  }
}
```

## Step 7: Add AI Function Support

Let's make your plugin AI-enabled by adding LLM-callable functions. Add this method to your plugin:

```python
@hookimpl
def get_ai_functions(self) -> list[AIFunction]:
    """Provide AI functions for LLM function calling."""
    return [
        AIFunction(
            name="get_current_time",
            description="Get the current time in a specified timezone",
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (e.g., 'US/Eastern', 'UTC')",
                        "default": "local"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["12hour", "24hour"],
                        "description": "Time format preference",
                        "default": "12hour"
                    }
                }
            },
            handler=self._get_time_function,
        ),
        AIFunction(
            name="get_current_date",
            description="Get the current date in various formats",
            parameters={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["short", "long", "iso"],
                        "description": "Date format preference",
                        "default": "long"
                    }
                }
            },
            handler=self._get_date_function,
        )
    ]

async def _get_time_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Handle the get_current_time AI function."""
    params = context.metadata.get("parameters", {})
    timezone = params.get("timezone", "local")
    format_type = params.get("format", "12hour")

    try:
        now = datetime.datetime.now()

        if format_type == "24hour":
            time_str = now.strftime("%H:%M")
        else:
            time_str = now.strftime("%I:%M %p")

        if timezone != "local":
            time_str += f" ({timezone})"

        return CapabilityResult(
            content=f"Current time: {time_str}",
            success=True,
        )
    except Exception as e:
        return CapabilityResult(
            content=f"Error getting time: {str(e)}",
            success=False,
            error=str(e),
        )

async def _get_date_function(self, task, context: CapabilityContext) -> CapabilityResult:
    """Handle the get_current_date AI function."""
    params = context.metadata.get("parameters", {})
    format_type = params.get("format", "long")

    try:
        now = datetime.datetime.now()

        if format_type == "short":
            date_str = now.strftime("%m/%d/%Y")
        elif format_type == "iso":
            date_str = now.strftime("%Y-%m-%d")
        else:  # long
            date_str = now.strftime("%A, %B %d, %Y")

        return CapabilityResult(
            content=f"Current date: {date_str}",
            success=True,
        )
    except Exception as e:
        return CapabilityResult(
            content=f"Error getting date: {str(e)}",
            success=False,
            error=str(e),
        )
```

Don't forget to import `AIFunction`:

```python
from agent.plugins import PluginDefinition, CapabilityContext, CapabilityResult, PluginValidationResult, CapabilityType, AIFunction
```

## Step 8: Test AI Functions

With an AI-enabled agent, your functions will now be available to the LLM:

```bash
# Create an AI-enabled agent
agentup agent create ai-test-agent --template standard

cd ai-test-agent

# Configure your OpenAI API key
export OPENAI_API_KEY="your-key-here"
```

Update the `agent_config.yaml` to register your plugin with AI routing:

```yaml
skills:
  - skill_id: time_plugin
    routing_mode: ai  # Let AI decide when to use this skill
```

Start the agent:

```bash
agentup agent serve
```

Now when users ask time-related questions without specifying a skill_id, the LLM can ly route to your plugin and call your functions:

```bash
curl -X POST http://localhost:8000/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "history": [{
        "role": "user",
        "parts": [{
          "text": "What time is it in 24-hour format?"
        }]
      }]
    },
    "id": 1
  }'
```

The LLM will:
1. Recognize this is a time-related request
2. Route to your `time_plugin` skill
3. Call your `get_current_time` function with `format: "24hour"`

## Step 9: Add Tests

Your plugin already has a test file. Let's add some real tests:

```python
"""Tests for Time Plugin plugin."""

import pytest
import datetime
from agent.plugins.models import CapabilityContext, PluginDefinition
from time_plugin.plugin import Plugin


def test_plugin_registration():
    """Test that the plugin registers correctly."""
    plugin = Plugin()
    plugin_def = plugin.register_capability()

    assert isinstance(plugin_def, PluginDefinition)
    assert plugin_def.id == "time_plugin"
    assert plugin_def.name == "Time Plugin"


def test_time_request():
    """Test time request handling."""
    plugin = Plugin()

    # Create a mock context
    from unittest.mock import Mock
    task = Mock()
    task.history = [Mock()]
    task.history[0].parts = [Mock()]
    task.history[0].parts[0].text = "What time is it?"

    context = CapabilityContext(task=task)

    result = plugin.execute_capability(context)

    assert result.success
    assert "time" in result.content.lower()


def test_date_request():
    """Test date request handling."""
    plugin = Plugin()

    from unittest.mock import Mock
    task = Mock()
    task.history = [Mock()]
    task.history[0].parts = [Mock()]
    task.history[0].parts[0].text = "What's today's date?"

    context = CapabilityContext(task=task)

    result = plugin.execute_capability(context)

    assert result.success
    assert "today" in result.content.lower() or "date" in result.content.lower()


def test_routing_confidence():
    """Test routing confidence scoring."""
    plugin = Plugin()

    # High confidence cases
    from unittest.mock import Mock

    # Test "what time" - should be high confidence
    task = Mock()
    task.history = [Mock()]
    task.history[0].parts = [Mock()]
    task.history[0].parts[0].text = "what time is it?"

    context = CapabilityContext(task=task)
    confidence = plugin.can_handle_task(context)

    assert confidence == 1.0  # Should be maximum confidence

    # Test unrelated query - should be low confidence
    task.history[0].parts[0].text = "what's the weather like?"
    context = CapabilityContext(task=task)
    confidence = plugin.can_handle_task(context)

    assert confidence == 0.0  # Should be no confidence


@pytest.mark.asyncio
async def test_ai_functions():
    """Test AI function calls."""
    plugin = Plugin()
    ai_functions = plugin.get_ai_functions()

    assert len(ai_functions) == 2
    assert any(f.name == "get_current_time" for f in ai_functions)
    assert any(f.name == "get_current_date" for f in ai_functions)

    # Test time function
    from unittest.mock import Mock
    task = Mock()
    context = CapabilityContext(
        task=task,
        metadata={"parameters": {"format": "24hour"}}
    )

    time_func = next(f for f in ai_functions if f.name == "get_current_time")
    result = await time_func.handler(task, context)

    assert result.success
    assert ":" in result.content  # Should contain time separator
```

Run your tests:

```bash
pytest tests/ -v
```

## Step 10: Package and Share

Your plugin is now ready to share! The generated `pyproject.toml` includes everything needed:

```toml
[project.entry-points."agentup.skills"]
time_plugin = "time_plugin.plugin:Plugin"
```

To publish to PyPI:

```bash
# Build the package
python -m build

# Upload to PyPI (requires account and twine)
python -m twine upload dist/*
```

Others can now install your plugin:

```bash
pip install time-plugin
```

And it will automatically work with any AgentUp agent!


## Troubleshooting

**Plugin not loading?**
- Check `agentup plugin list` to see if it's discovered
- Verify your entry point in `pyproject.toml`
- Make sure you installed with `pip install -e .`

**Functions not available to AI?**
- Ensure your agent has AI capabilities enabled
- Check that your plugin returns AI functions from `get_ai_functions()`
- Verify the function schemas are valid OpenAI format

**Routing not working?**
- Check your `can_handle_task` logic
- Use `agentup plugin info time_plugin` to see plugin details
- Test with simple keywords first

Congratulations! You've built your first AgentUp plugin and learned the fundamentals of the plugin system. The possibilities are endless - from simple utilities to complex AI-powered workflows.