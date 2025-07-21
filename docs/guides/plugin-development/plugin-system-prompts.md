# Plugin System Prompts

AgentUp supports skill-specific system prompts that allow plugins to customize the AI behavior for their specific domain. This enables more specialized and effective AI interactions tailored to each skill's requirements.

## Overview

By default, AgentUp uses a global system prompt defined in `agent_config.yaml`. However, plugins can override this with their own specialized system prompts that are automatically used when their skills are invoked.

## How It Works

When a plugin skill is executed:

1. **Plugin Registration**: Plugin defines a custom system prompt in its `SkillInfo`
2. **Skill Invocation**: AgentUp identifies which skill is being used
3. **System Prompt Selection**: Framework uses the plugin's system prompt instead of the global one
4. **Specialized Behavior**: The LLM receives domain-specific instructions

## Defining Custom System Prompts

### In Plugin Code

Add a `system_prompt` field to your `SkillInfo` during registration:

```python
from agentup.plugins.hookspecs import hookimpl
from agentup.plugins.models import SkillInfo, SkillCapability

class MyPlugin:
    @hookimpl
    def register_skill(self) -> SkillInfo:
        return SkillInfo(
            id="my_plugin.specialized_skill",
            name="Specialized Assistant",
            version="1.0.0",
            description="A specialized AI assistant for my domain",
            capabilities=[SkillCapability.TEXT, SkillCapability.AI_FUNCTION],
            system_prompt="""You are a specialized assistant for [your domain].

Your role:
- Provide expert guidance in [your domain]
- Follow [specific standards/guidelines]
- Focus on [key aspects of your domain]
- Always consider [domain-specific factors]

When helping users:
1. [Domain-specific instruction 1]
2. [Domain-specific instruction 2]
3. [Domain-specific instruction 3]

Maintain a [tone/style] while being [characteristics].""",
        )
```

### System Prompt Best Practices

1. **Be Specific**: Clearly define the assistant's role and expertise
2. **Include Guidelines**: Specify standards, formats, or methodologies to follow
3. **Set Expectations**: Describe the type of responses users should expect
4. **Consider Context**: Include domain-specific considerations and constraints
5. **Maintain Consistency**: Keep the tone and style consistent with your skill's purpose

## Complete Example

Here's a complete plugin demonstrating system prompt customization:

```python
"""
Code Assistant Plugin - Demonstrates system prompt customization
"""

import logging
from typing import Any

from agentup.plugins.hookspecs import hookimpl
from agentup.plugins.models import SkillCapability, SkillContext, SkillInfo, SkillResult

logger = logging.getLogger(__name__)


class CodeAssistantPlugin:
    """A specialized coding assistant with custom system prompt."""

    @hookimpl
    def register_skill(self) -> SkillInfo:
        """Register the code assistant skill with a custom system prompt."""
        return SkillInfo(
            id="code_assistant.python_helper",
            name="Python Code Assistant",
            version="1.0.0",
            description="A specialized Python coding assistant",
            capabilities=[SkillCapability.TEXT, SkillCapability.AI_FUNCTION],
            tags=["python", "coding", "assistant"],
            system_prompt="""You are a specialized Python coding assistant with deep expertise in Python development.

Your role:
- Provide expert Python programming guidance
- Follow PEP 8 style guidelines strictly
- Write clean, efficient, and well-documented code
- Explain complex Python concepts clearly
- Focus on best practices and performance optimization
- Always include type hints when writing Python code
- Suggest appropriate testing strategies

When helping with Python code:
1. Always consider code readability and maintainability
2. Recommend appropriate Python libraries and frameworks
3. Explain the reasoning behind your suggestions
4. Provide examples with proper error handling
5. Consider security implications of the code

Be thorough, accurate, and maintain a professional tone while being approachable.""",
        )

    @hookimpl
    def execute_skill(self, context: SkillContext) -> SkillResult:
        """Execute the Python helper skill."""
        # Your skill implementation here
        return SkillResult(
            content="Python coding assistance with specialized system prompt",
            success=True,
            metadata={"system_prompt_used": True},
        )

    @hookimpl
    def can_handle_task(self, context: SkillContext) -> float:
        """Check if this skill can handle the task."""
        # Your task routing logic here
        return 0.8  # High confidence for Python-related tasks
```

## Usage in Agent Configuration

Configure the plugin skill in your agent's `agent_config.yaml`:

```yaml
skills:
  - skill_id: code_assistant.python_helper
    handler: plugin
    priority: 60
    config:
      # Any plugin-specific configuration
```

## System Prompt Hierarchy

AgentUp uses the following priority order for system prompts:

1. **Plugin System Prompt** (highest priority) - Used when a plugin skill defines one
2. **Global System Prompt** - From `agent_config.yaml` under `ai.system_prompt`
3. **Default System Prompt** - Built-in fallback prompt

## Examples of Effective System Prompts

### Data Analysis Assistant
```python
system_prompt="""You are a specialized data analysis assistant with expertise in statistical analysis and data visualization.

Your role:
- Analyze datasets and identify patterns, trends, and insights
- Recommend appropriate statistical methods and tests
- Create clear, informative visualizations
- Validate data quality and identify potential issues
- Explain findings in business terms

When working with data:
1. Always start by understanding the data structure and quality
2. Use appropriate statistical methods for the data type
3. Visualize data to support your analysis
4. Provide actionable insights and recommendations
5. Document your methodology and assumptions

Focus on accuracy, clarity, and practical applicability."""
```

### API Integration Assistant
```python
system_prompt="""You are a specialized API integration assistant with expertise in REST APIs, webhooks, and service integrations.

Your role:
- Design robust API integration patterns
- Handle authentication, rate limiting, and error scenarios
- Implement proper retry logic and circuit breakers
- Follow RESTful principles and industry standards
- Ensure secure handling of credentials and sensitive data

When building integrations:
1. Always validate input parameters and API responses
2. Implement comprehensive error handling
3. Use appropriate HTTP methods and status codes
4. Include proper logging and monitoring
5. Consider rate limits and implement backoff strategies

Prioritize reliability, security, and maintainability."""
```

## Testing System Prompts

To test your plugin's system prompt:

1. **Install the plugin** in development mode
2. **Create a test agent** that uses your skill
3. **Interact with the skill** and observe the AI behavior
4. **Compare responses** with and without the custom system prompt

## Troubleshooting

### System Prompt Not Applied

If your custom system prompt isn't being used:

1. **Check Plugin Registration**: Ensure your plugin is properly registered and the skill is loaded
2. **Verify Skill ID**: Confirm the skill ID in your agent config matches the plugin
3. **Check Logs**: Look for warning messages about skill information retrieval
4. **Test Plugin Loading**: Use `agentup plugin list` to verify your plugin is loaded

### Common Issues

- **Import Errors**: Ensure all required dependencies are installed
- **Skill Not Found**: Check that the skill ID is correctly configured
- **System Prompt Too Long**: Very long prompts may be truncated by LLM providers
- **Conflicting Prompts**: Multiple plugins with overlapping capabilities may cause conflicts

## Performance Considerations

- **Prompt Length**: Longer system prompts use more tokens and may increase response time
- **Context Window**: Very long prompts may limit conversation history that can be included
- **Caching**: System prompts are used for every interaction, so keep them optimized

## Migration Guide

### From Global to Plugin-Specific Prompts

If you're migrating from global system prompts to plugin-specific ones:

1. **Identify Skill Domains**: Group your skills by domain or functionality
2. **Extract Relevant Instructions**: Move domain-specific instructions to plugin prompts
3. **Maintain General Instructions**: Keep general behavior instructions in the global prompt
4. **Test Thoroughly**: Verify that the specialized prompts work as expected

### Backward Compatibility

The system prompt feature is fully backward compatible:
- Existing plugins without system prompts continue to work unchanged
- Global system prompts are still used when plugins don't specify their own
- No changes required to existing agent configurations

## Best Practices Summary

1. **Be Specific**: Tailor system prompts to your skill's exact domain and requirements
2. **Include Context**: Provide domain-specific guidelines and constraints
3. **Set Clear Expectations**: Define the assistant's role and behavior clearly
4. **Test Thoroughly**: Validate that your system prompt produces the desired behavior
5. **Keep It Focused**: Avoid overly broad or generic instructions
6. **Document Well**: Include examples and explanations in your plugin documentation
7. **Consider Token Usage**: Balance specificity with prompt length efficiency

## Related Documentation

- [Plugin Development Guide](plugin-development.md)
- [Agent Configuration](agent-configuration.md)
- [Skill System](skill-system.md)
- [AI Provider Configuration](ai-providers.md)