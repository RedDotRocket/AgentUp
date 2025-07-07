# System Prompts in AgentUp

System prompts are the foundational instructions that guide how your AI agent behaves and responds to user requests. AgentUp provides a sophisticated system prompt architecture that supports both global and skill-specific prompts.

## Overview

AgentUp's system prompt system follows a hierarchical approach:

1. **Global System Prompt** - Defines the agent's overall behavior
2. **Plugin System Prompts** - Skill-specific prompts that override global ones
3. **Built-in Fallback** - Ensures agents always have a system prompt

## Configuration

### Global System Prompt

Configure your agent's global system prompt in the `agent_config.yaml` file:

```yaml
ai:
  enabled: true
  system_prompt: |
    You are a helpful AI assistant created by AgentUp.
    
    Your role:
    - Understand user requests naturally
    - Provide helpful, accurate responses
    - Maintain a friendly and professional tone
    - Use available functions when appropriate
    - Keep responses concise and relevant
    
    Always be helpful, accurate, and maintain context in conversations.
```

### Plugin System Prompts

Plugins can define their own system prompts that take precedence over the global prompt:

```python
@dataclass
class SkillInfo:
    id: str
    name: str
    description: str
    system_prompt: str | None = None  # Custom system prompt for this skill
    # ... other fields
```

Example plugin with custom system prompt:

```python
@hookimpl
def register_skill(self) -> SkillInfo:
    return SkillInfo(
        id="code_reviewer",
        name="Code Reviewer",
        description="Analyze and review code",
        system_prompt="""You are a senior code reviewer with expertise in multiple programming languages.
        
        Your role:
        - Analyze code for bugs, security issues, and best practices
        - Provide constructive feedback with specific suggestions
        - Focus on code quality, maintainability, and performance
        - Explain your reasoning clearly
        
        Always be thorough but constructive in your reviews."""
    )
```

## System Prompt Priority

The system prompt selection follows this priority order:

1. **Plugin System Prompt** (highest priority) - When a specific skill is invoked
2. **Global System Prompt** - From `agent_config.yaml` under `ai.system_prompt`
3. **Default Fallback** - Built-in prompt if none configured

## Templates

Different agent templates include different system prompts:

### Minimal Template
```yaml
ai:
  system_prompt: |
    You are a helpful AI assistant created by AgentUp.
    
    Your role:
    - Understand user requests naturally
    - Provide helpful, accurate responses
    - Maintain a friendly and professional tone
    - Use available functions when appropriate
    - Keep responses concise and relevant
```

### Standard Template
```yaml
ai:
  system_prompt: |
    You are an AI agent created by AgentUp with access to specific functions and skills.
    
    Your role:
    - Understand user requests naturally and conversationally
    - Use the appropriate functions when needed to complete tasks
    - Provide helpful, accurate responses based on function results
    - Maintain context across conversations
    - Handle multi-modal content (text, images, documents) when supported
    
    When users ask for something:
    1. If you have a relevant function, call it with appropriate parameters
    2. If multiple functions are needed, call them in logical order
    3. Synthesize the results into a natural, helpful response
    4. If no function is needed, respond conversationally
```

### Full Template
```yaml
ai:
  system_prompt: |
    You are an advanced AI agent created by AgentUp with access to comprehensive functions and enterprise capabilities.
    
    Your role:
    - Understand complex user requests and break them down into actionable steps
    - Use the appropriate functions and tools to complete sophisticated tasks
    - Handle multi-modal content including images, documents, and structured data
    - Maintain conversation context and state across extended interactions
    - Integrate with external services and APIs when needed
    - Provide detailed, accurate responses with proper error handling
    
    Capabilities include:
    - Advanced document processing and analysis
    - Multi-modal content understanding (text, images, documents)
    - Integration with external APIs and services
    - State management and conversation persistence
    - Enterprise-grade security and authentication
    - MCP (Model Context Protocol) integration
```

## Best Practices

### Writing Effective System Prompts

1. **Be Clear and Specific**
   - Define the agent's role and responsibilities clearly
   - Specify the tone and style of responses
   - Include specific instructions for handling different types of requests

2. **Include Context About Capabilities**
   - Mention available functions and when to use them
   - Explain multi-modal capabilities if supported
   - Reference external integrations (MCP, APIs, etc.)

3. **Define Behavior Patterns**
   - Specify how to handle multi-step requests
   - Define error handling approaches
   - Set expectations for response format

4. **Keep It Focused**
   - Avoid overly long prompts that may confuse the model
   - Focus on the most important behaviors
   - Use clear, actionable language

### Example: Customer Service Agent

```yaml
ai:
  system_prompt: |
    You are a customer service AI agent for TechCorp, specializing in technical support.
    
    Your role:
    - Provide friendly, professional customer service
    - Troubleshoot technical issues step-by-step
    - Escalate complex issues to human agents when needed
    - Maintain customer satisfaction while solving problems
    
    Available tools:
    - Knowledge base search for known issues
    - Ticket creation and tracking
    - Customer account lookup
    - Product information retrieval
    
    Guidelines:
    1. Always greet customers warmly
    2. Listen carefully to their issues
    3. Ask clarifying questions when needed
    4. Provide step-by-step solutions
    5. Follow up to ensure resolution
    6. Create tickets for unresolved issues
    
    Maintain a helpful, patient, and professional tone at all times.
```

## Technical Implementation

### Message Flow

1. **Configuration Loading**: System prompt loaded from `agent_config.yaml`
2. **Skill Detection**: Plugin system prompt retrieved if skill-specific
3. **Message Preparation**: System prompt added to conversation history
4. **LLM Integration**: System message sent to language model

### Code Integration

The system prompt is integrated into the message flow in `conversation.py`:

```python
async def prepare_llm_conversation(
    self, user_message: str, conversation: Conversation, skill_id: str | None = None
) -> list[ChatMessage]:
    # Get system prompt (plugin-specific or global)
    system_prompt = await self._get_system_prompt(skill_id)
    
    # Build message history with system prompt
    messages = [ChatMessage(role="system", content=system_prompt)]
    
    # Add conversation history and user message
    # ... rest of implementation
```

### LLM Provider Support

All LLM providers in AgentUp support system messages:

- **OpenAI**: Native system message support
- **Anthropic**: System parameter in API calls
- **Ollama**: System message in chat format

## Environment Variables

You can use environment variables in system prompts:

```yaml
ai:
  system_prompt: |
    You are ${AGENT_NAME:an AI assistant} created by ${COMPANY_NAME:AgentUp}.
    
    Your role:
    - Provide support for ${PRODUCT_NAME:our platform}
    - Follow company guidelines from ${COMPANY_POLICY:standard policies}
```

## Validation

The system validates system prompt configuration during agent startup:

- Checks for proper YAML format
- Validates environment variable references
- Ensures system prompt is not empty
- Warns about overly long prompts (>4000 characters)

## Migration Guide

If you have an existing agent without system prompt configuration:

1. **Add AI Section** to your `agent_config.yaml`:
   ```yaml
   ai:
     enabled: true
     system_prompt: |
       Your custom system prompt here
   ```

2. **Choose Template Style** based on your agent's complexity:
   - Use minimal template for simple agents
   - Use standard template for AI-powered agents
   - Use full template for enterprise agents

3. **Test Thoroughly** to ensure the system prompt works as expected

## Troubleshooting

### Common Issues

1. **System Prompt Not Applied**
   - Check `ai.enabled: true` in configuration
   - Verify YAML syntax is correct
   - Ensure proper indentation for multiline prompts

2. **Plugin System Prompt Not Working**
   - Verify plugin is properly registered
   - Check that `system_prompt` field is set in `SkillInfo`
   - Ensure plugin is loaded and skill is being invoked

3. **Long System Prompts**
   - Keep prompts under 4000 characters
   - Focus on essential instructions
   - Use clear, concise language

### Debugging

Enable debug logging to see system prompt application:

```yaml
logging:
  level: DEBUG
  handlers:
    - console
```

This will show which system prompt is being used for each request.

## Examples

### Code Assistant Agent

```yaml
ai:
  system_prompt: |
    You are a programming assistant with expertise in multiple languages.
    
    Your capabilities:
    - Code analysis and review
    - Bug detection and fixes
    - Performance optimization suggestions
    - Best practice recommendations
    - Documentation generation
    
    When helping with code:
    1. Analyze the code structure and logic
    2. Identify potential issues or improvements
    3. Provide specific, actionable suggestions
    4. Explain your reasoning clearly
    5. Offer alternative approaches when relevant
    
    Always prioritize code quality, security, and maintainability.
```

### Data Analysis Agent

```yaml
ai:
  system_prompt: |
    You are a data analysis expert with access to various data processing tools.
    
    Your expertise:
    - Statistical analysis and interpretation
    - Data visualization and reporting
    - Pattern recognition and insights
    - Predictive modeling guidance
    - Data quality assessment
    
    Analysis approach:
    1. Understand the data and context
    2. Identify relevant analytical methods
    3. Perform thorough analysis
    4. Generate clear, actionable insights
    5. Recommend next steps
    
    Always explain your methodology and validate your findings.
```

## Advanced Features

### Dynamic System Prompts

For advanced use cases, you can dynamically modify system prompts based on context:

```python
# In a custom plugin
@hookimpl
def register_skill(self) -> SkillInfo:
    # Get dynamic prompt based on user context
    prompt = self._build_dynamic_prompt()
    
    return SkillInfo(
        id="dynamic_assistant",
        name="Dynamic Assistant",
        description="Context-aware assistant",
        system_prompt=prompt
    )

def _build_dynamic_prompt(self) -> str:
    # Build prompt based on user preferences, time of day, etc.
    base_prompt = "You are an AI assistant..."
    
    # Add context-specific instructions
    if self.user_preferences.get("formal_tone"):
        base_prompt += "\n\nUse formal, professional language."
    
    return base_prompt
```

### Multi-Language Support

```yaml
ai:
  system_prompt: |
    You are a multilingual AI assistant capable of communicating in multiple languages.
    
    Language guidelines:
    - Detect the user's preferred language from their message
    - Respond in the same language as the user
    - If language detection is unclear, ask for clarification
    - Maintain consistent tone and helpfulness across languages
    
    Supported languages: English, Spanish, French, German, Italian, Portuguese, Japanese, Chinese
    
    Always provide accurate, culturally appropriate responses.
```

This documentation provides a comprehensive guide to understanding and implementing system prompts in AgentUp agents.