# {{ project_name_title }}

{{ description }}

## Quick Start

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Configure your agent:
   - Copy `.env.example` to `.env` (if using services)
   - Edit `agent_config.yaml` to customize skills

3. Start the development server:
   ```bash
   uv run uvicorn {{ project_name_snake }}.main:app --reload --port 8000
   ```

4. Test your agent:
   ```bash
   uv run python example_client.py
   ```

## A2A Compliance Features

This agent is **fully A2A-specification compliant** and includes:

### 🔄 **Core A2A Protocol**
- ✓ **JSON-RPC 2.0 API** - Standard A2A communication protocol
- ✓ **Official A2A Types** - Uses `a2a.types` models (`Task`, `Message`, `AgentCard`) 
- ✓ **Agent Discovery Card** - Proper `/.well-known/agent.json` endpoint
- ✓ **TaskState Lifecycle** - Complete SUBMITTED → WORKING → COMPLETED flow

### 📡 **Advanced Communication**
- ✓ **Server-Sent Events** - Real-time streaming communication
- ✓ **Message-Based Conversations** - Multi-turn conversation support
- ✓ **Context Awareness** - Remembers users and conversation history
- ✓ **Task Management** - Full lifecycle tracking with state validation

### **Enterprise Security**
- ✓ **Multi-Scheme Authentication** - API Key, Bearer Token, OAuth2
- ✓ **Request Validation** - Comprehensive parameter and format checking
- ✓ **Error Handling** - A2A-compliant JSON-RPC error responses
- ✓ **Permission Management** - Task-level access control

### 🏗️ **Advanced Architecture**
- ✓ **TaskManager** - Enterprise-grade task lifecycle management
- ✓ **MessageProcessor** - Advanced message chain processing
- ✓ **ConversationContext** - Persistent conversation state
- ✓ **State History** - Complete audit trail of all operations

### **Testing & Monitoring**
- ✓ **A2A Test Client** - Full protocol testing with streaming support
- ✓ **Error Testing** - Comprehensive JSON-RPC error scenario validation
- ✓ **Task Monitoring** - Real-time task status and history tracking
- ✓ **Health Endpoints** - Agent health and capability reporting

### **Template-Specific Features**
This agent was created with the **{{ template_name }}** template and includes:

{{ if }} has_middleware
- ✓ Middleware system (rate limiting, caching, validation)
{{ endif }}
{{ if }} has_services  
- ✓ External service integrations
{{ endif }}
{{ if }} has_multimodal
- ✓ Multi-modal processing (images, documents)
{{ endif }}
{{ if }} has_state_management
- ✓ Enhanced state management and conversation persistence
{{ endif }}
{{ if }} has_auth
- ✓ Advanced authentication and security schemes
{{ endif }}
{{ if }} has_testing
- ✓ Comprehensive A2A-compliant test suite
{{ endif }}
{{ if }} has_deployment
- ✓ Deployment tools (Docker, Kubernetes)
{{ endif }}

## Development

### A2A Development Workflow

#### 1. Adding New Skills

**Using AgentUp CLI (Recommended):**
```bash
# Interactive skill generator with A2A compliance checks
agentup add-skill

# Generate with specific template
agentup add-skill --skill-id my_skill --template conversational
```

**Manual A2A-Compliant Skill Development:**

1. **Define Skill in Configuration** (`agent_config.yaml`):
```yaml
skills:
  - skill_id: my_new_skill
    name: My New Skill
    description: A2A-compliant skill that processes user requests
    input_mode: text
    output_mode: text
    config:
      max_context_length: 4096
      response_format: conversational
```

2. **Implement A2A Handler** (`src/agent/handlers.py`):
```python
@register_handler("my_new_skill")
async def handle_my_new_skill(task: Task) -> str:
    \"\"\"A2A-compliant skill handler with full message processing.\"\"\"
    
    # Extract A2A messages using MessageProcessor
    messages = MessageProcessor.extract_messages(task)
    latest_message = MessageProcessor.get_latest_user_message(messages)
    
    if not latest_message:
        return "No message content provided."
    
    # Get message content
    content = latest_message.get('content', '') if isinstance(latest_message, dict) else getattr(latest_message, 'content', '')
    
    # Update conversation context
    ConversationContext.increment_message_count(task.id)
    
    # Process with your skill logic
    processed_content = your_processing_logic(content)
    
    return f"Processed: {processed_content}"
```

3. **Test A2A Compliance:**
```bash
# Test individual skill
uv run python example_client.py --test-skill my_new_skill

# Full A2A protocol test
uv run python example_client.py --comprehensive
```

#### 2. A2A Message Processing Patterns

**Basic Message Extraction:**
```python
# Get all messages in conversation
messages = MessageProcessor.extract_messages(task)

# Get latest user input
latest_message = MessageProcessor.get_latest_user_message(messages)

# Get conversation history with context
history = MessageProcessor.get_conversation_history(messages, limit=5)
```

**Advanced Context Management:**
```python
# Access conversation context
context = ConversationContext.get_context(task.id)

# Store user preferences
ConversationContext.update_context(task.id, {
    'user_name': extracted_name,
    'preferences': user_preferences,
    'session_data': custom_data
})

# Track conversation flow
ConversationContext.increment_message_count(task.id)
```

**Parameter Extraction with A2A:**
```python
# Extract structured parameters from natural language
name = extract_parameter(content, "name", "Guest")
action = extract_parameter(content, "action", "default")

# Handle multi-modal content (if enabled)
{{ if }} has_multimodal
images = MultiModalProcessor.extract_image_parts(task.messages[0].parts)
if images:
    image_info = MultiModalProcessor.process_image(images[0].data, images[0].mimeType)
{{ endif }}
```

#### 3. A2A Testing & Validation

**Comprehensive A2A Testing:**
```bash
# Run full A2A compliance test suite
uv run python run_tests.py --a2a-compliance

# Test specific A2A scenarios
uv run pytest tests/test_a2a_protocol.py -v

# Test error handling compliance
uv run pytest tests/test_jsonrpc_errors.py -v
```

**Manual A2A Testing:**
```bash
# Test JSON-RPC protocol
curl -X POST http://localhost:8000/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method": "send_message",
    "params": {
      "messages": [{"role": "user", "content": "Test message"}]
    },
    "id": "test-123"
  }'

# Test agent discovery
curl http://localhost:8000/.well-known/agent.json

# Test streaming capabilities
curl -N -H "Accept: text/event-stream" http://localhost:8000/stream
```

**A2A Error Testing:**
```python
# Test JSON-RPC error scenarios
test_cases = [
    {"invalid": "jsonrpc version"},  # Should return -32600
    {"method": "nonexistent"},       # Should return -32601
    {"params": "invalid"},           # Should return -32602
]

for case in test_cases:
    result = await client.make_jsonrpc_request(**case)
    assert "error" in result
```

#### 4. A2A Performance & Monitoring

**Task Lifecycle Monitoring:**
```python
# Monitor task states in production
task_manager = TaskManager()

# Track task performance
history = task_manager.get_task_history(task_id)
processing_time = calculate_processing_time(history)

# Monitor conversation context usage
context_size = len(ConversationContext.get_context(task_id))
```

**A2A Metrics Collection:**
```bash
# Enable detailed A2A metrics
export A2A_METRICS=true
export A2A_TRACE_LEVEL=debug

# Monitor JSON-RPC performance
uv run python -m {{ project_name_snake }}.main --enable-metrics
```

### Running Tests

**Standard Testing:**
```bash
# Run all tests
uv run python run_tests.py

# With coverage reporting
uv run python run_tests.py --coverage

# Watch mode for development
uv run python run_tests.py --watch
```

**A2A-Specific Testing:**
```bash
# A2A protocol compliance
uv run pytest tests/test_a2a_protocol.py

# JSON-RPC error handling
uv run pytest tests/test_jsonrpc_errors.py

# Message processing validation
uv run pytest tests/test_message_processing.py

# Task state management
uv run pytest tests/test_task_lifecycle.py
```

### Deployment

**Development Deployment:**
```bash
# Start development server with A2A debugging
uv run uvicorn {{ project_name_snake }}.main:app --reload --port 8000 --log-level debug

# Enable A2A protocol tracing
A2A_DEBUG=true uv run uvicorn {{ project_name_snake }}.main:app --reload --port 8000
```

**Production Deployment:**
```bash
# Generate Docker files with A2A optimization
uv run python deploy.py --type docker --a2a-optimized

# Build and run
docker build -t {{ project_name_snake }} .
docker run -p 8000:8000 -e A2A_METRICS=true {{ project_name_snake }}

# Kubernetes deployment with A2A monitoring
uv run python deploy.py --type k8s --enable-monitoring
kubectl apply -f k8s-manifests/
```

**A2A Production Checklist:**
-  Agent card (`/.well-known/agent.json`) returns valid JSON
-  All skills properly registered and tested
-  JSON-RPC error handling covers all edge cases
-  Task state transitions follow A2A specification
-  Streaming endpoints handle disconnections gracefully
-  Authentication schemes properly configured
-  Performance metrics and monitoring enabled

## Documentation

- [Configuration Guide](docs/configuration.md)
- [Skills Development](docs/skills.md)
- [API Reference](docs/api-reference.md)

## License

MIT

---
Created with [AgentUp](https://github.com/your-org/agentup)