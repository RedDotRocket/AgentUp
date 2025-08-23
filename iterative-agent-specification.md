# Self-Directed Iterative Agent Architecture for AgentUp

## Executive Summary

This specification defines a complete architecture for self-directed, iterative agents within the AgentUp framework. The design prioritizes clean architecture, strong Pydantic typing, LLM-driven decision making, and comprehensive memory integration while maintaining extensibility for future agent types.

## Design Principles

### 1. Pydantic-First Architecture
- **Zero dict access patterns**: All data structures use Pydantic models with dot notation
- **Strong typing throughout**: Complete type safety from configuration to execution
- **Model-driven validation**: Comprehensive data validation using Pydantic v2 features

### 2. LLM-Driven Decision Making  
- **Semantic reasoning**: LLM makes ALL semantic decisions (continue/stop, next action, tool selection)
- **No hardcoded routing**: Eliminated keyword filtering and pattern matching logic
- **Structured responses**: LLM outputs conform to Pydantic schemas for reliability

### 3. Memory Integration
- **Persistent state**: Iteration state and learning insights stored across sessions
- **Cross-session learning**: Agents learn from past interactions and outcomes
- **Context restoration**: Full conversation and state recovery on agent restart

### 4. No Legacy Support
- **Clean break**: Complete removal of backward compatibility code
- **Modern patterns**: Fresh implementation using current best practices
- **Pre-release philosophy**: No migration paths or deprecated functionality

### 5. Extensible Architecture
- **Strategy pattern**: Clean separation enabling easy addition of new agent types
- **Shared primitives**: Common A2A, auth, and streaming logic in base classes
- **Future-ready**: Graph orchestration and other patterns can be added later

## Core Architecture

### Agent Type Taxonomy

```
AgentExecutorBase (Abstract)
├── Core A2A protocol integration
├── Authentication context management
├── Event queue and streaming infrastructure
└── Shared error handling and validation

ReactiveStrategy (AgentExecutorBase)
├── Single-shot request/response pattern
├── Direct plugin routing via configuration
├── AI routing through function dispatcher
└── Streaming support for real-time responses

IterativeStrategy (AgentExecutorBase)
├── Self-directed multi-turn loops
├── LLM-driven goal decomposition and planning
├── Reflection and progress evaluation
├── Memory integration for learning
└── Configurable termination conditions
```

### Execution Flow

#### Reactive Agent Flow
```
User Request → Validate → Direct Plugin Match? → Execute Plugin : Use AI Router → Create Response → Complete
```

#### Iterative Agent Flow  
```
User Request → Initialize State → Decompose Goal → 
LOOP:
  Execute Task → Observe Results → Reflect on Progress → Goal Achieved? → Complete : Continue
→ Handle Completion → Store Learning Insights
```

## Implementation Architecture

### Directory Structure
```
src/agent/core/
├── base.py                   # AgentExecutorBase with shared primitives
├── executor.py               # Main factory and AgentUpExecutor
├── memory_integration.py     # Memory management for iterative agents
├── models/
│   ├── __init__.py
│   ├── configuration.py      # Agent configuration models
│   ├── iteration.py          # Iteration state and reflection models
│   └── memory.py             # Learning insights and memory models
└── strategies/
    ├── __init__.py
    ├── protocol.py           # ExecutionStrategy interface
    ├── reactive.py           # Single-shot execution strategy
    └── iterative.py          # Self-directed loop strategy
```

### Key Pydantic Models

#### Agent Configuration
```python
class AgentType(str, Enum):
    REACTIVE = "reactive"
    ITERATIVE = "iterative"

class AgentConfiguration(BaseModel):
    agent_type: AgentType = AgentType.REACTIVE
    memory: MemoryConfig = Field(default_factory=MemoryConfig) 
    iterative: IterativeConfig = Field(default_factory=IterativeConfig)
```

#### Iteration State Management
```python
class IterationState(BaseModel):
    iteration_count: int = 0
    goal: str
    current_plan: list[str] = Field(default_factory=list)
    completed_tasks: list[str] = Field(default_factory=list)
    action_history: list[ActionResult] = Field(default_factory=list)
    reflection_data: Optional[ReflectionData] = None
    should_continue: bool = True
    context_id: str
    task_id: str
```

#### LLM Reflection Framework
```python
class ReflectionData(BaseModel):
    progress_assessment: str = Field(description="LLM assessment of current progress")
    goal_achievement_status: GoalStatus
    next_action_reasoning: str = Field(description="LLM reasoning for next action")
    learned_insights: list[str] = Field(default_factory=list)
    challenges_encountered: list[str] = Field(default_factory=list)
```

## Memory System Integration

### Architecture
The memory system extends AgentUp's existing `ConversationContext` infrastructure to support iterative agent-specific data:

```python
class IterativeMemoryManager:
    """Memory manager for iterative agents using AgentUp's context system"""
    
    async def store_iteration_state(context_id: str, state: IterationState) -> None
    async def load_iteration_state(context_id: str) -> IterationState | None
    async def add_learning_insight(context_id: str, insight: LearningInsight) -> None
    async def get_learning_insights(context_id: str, learning_type: str = None) -> list[LearningInsight]
```

### Learning Insights
```python
class LearningInsight(BaseModel):
    insight: str
    learning_type: LearningType  # SUCCESS_PATTERN, ERROR_PATTERN, OPTIMIZATION, etc.
    context: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0) 
    usage_count: int = 0
```

### Storage Backends
- **Memory**: In-memory storage for development and testing
- **File**: Local filesystem persistence for single-instance deployments  
- **Valkey/Redis**: Distributed storage for production multi-instance deployments

## LLM Decision Framework

### Goal Decomposition
```python
# LLM prompt structure for goal breakdown
decomposition_prompt = f\"\"\"
Please analyze this goal and break it down into specific, actionable tasks:

Goal: {goal}

Provide your response as a JSON object with this structure:
{{
    "tasks": ["task1", "task2", "task3"],
    "reasoning": "explanation of your decomposition approach" 
}}

Make each task specific, measurable, and achievable using available tools.
\"\"\"
```

### Progress Reflection
```python
# LLM prompt for progress evaluation
reflection_prompt = f\"\"\"
Reflect on the current progress and determine if the goal is achieved:

{context}

Provide your response as a JSON object:
{{
    "progress_assessment": "detailed assessment of current progress",
    "goal_achievement_status": "not_started|in_progress|partially_achieved|fully_achieved|failed|requires_clarification",
    "next_action_reasoning": "reasoning for what to do next",
    "learned_insights": ["insight1", "insight2"],
    "challenges_encountered": ["challenge1", "challenge2"]
}}
\"\"\"
```

### Action Determination
```python
# LLM prompt for next action selection  
action_prompt = f\"\"\"
Based on the current progress, determine the next action to take:

{context}

Provide your response as a JSON object:
{{
    "next_action": "specific action to take",
    "reasoning": "why this action was chosen",
    "tool_needed": "name of tool to use (if any)"
}}
\"\"\"
```

## Configuration Integration

### YAML Configuration Schema
```yaml
# Agent execution configuration
agent_type: iterative  # or reactive
memory_config:
  enabled: true
  persistence: true
  max_entries: 1000
  ttl_hours: 24

iterative_config:
  max_iterations: 10
  reflection_interval: 1
  require_explicit_completion: true
  timeout_minutes: 30

# Existing AgentUp configuration continues unchanged...
api:
  enabled: true
  host: "127.0.0.1"
  port: 8000

security:
  enabled: true
  auth:
    api_key:
      keys:
        - key: "admin-key-123"
          scopes: ["system:read", "api:read"]
```

### Environment Variables
- `AGENTUP_AGENT_TYPE` → Override agent type
- `AGENTUP_MAX_ITERATIONS` → Override iteration limit
- `AGENTUP_MEMORY_ENABLED` → Enable/disable memory
- Existing environment variables remain unchanged

## CLI Integration

### Agent Creation
```bash
# Interactive agent creation with type selection
agentup init

# Select agent execution type:
# → Reactive (single-shot request/response)
#   Iterative (self-directed multi-turn loops)

# If iterative selected:
# Maximum iterations per task (1-100): 10
# Enable memory for learning and context preservation? (Y/n): Y
```

### Configuration Management
```bash
# Validate agent configuration
agentup validate

# Run with specific agent type
agentup run --agent-type iterative

# View current configuration
agentup config show
```

## A2A Protocol Integration

### Conversation Management
```python
# Native A2A conversation handling
iteration_state = IterationState(
    goal=extract_user_message(task),
    context_id=task.context_id,
    task_id=task.id,
)

# Use A2A task.history for conversation continuity
for message in task.history:
    if message.role == "user":
        content = ConversationManager.extract_text_from_parts(message.parts)
```

### Streaming Support  
```python
# Real-time progress updates via A2A streaming
await updater.update_status(
    TaskState.working,
    new_agent_text_message(
        f"Iteration {state.iteration_count + 1}: Working on goal - {state.goal}",
        task.context_id,
        task.id,
    ),
    final=False,
)
```

### Event-Driven Architecture
```python
# Task completion with artifacts
parts = [
    Part(root=TextPart(text=completion_message)),
    Part(root=DataPart(data={
        "goal": state.goal,
        "iterations_completed": state.iteration_count,
        "tasks_completed": state.completed_tasks,
        "final_status": state.reflection_data.goal_achievement_status.value,
    }))
]

artifact = new_artifact(parts, name=f"{agent_name}-iterative-result")
await updater.add_artifact(parts, name=artifact.name)
```

## Security and Scalability

### Security Framework
- **Scope-based authorization**: Iterative agents require same scopes as underlying tools
- **Audit logging**: All iterations, reflections, and actions logged with correlation IDs
- **Memory isolation**: Context-based memory separation prevents cross-agent data leakage

### Scalability Considerations
- **Stateless execution**: All state persisted externally, enabling horizontal scaling
- **Memory backends**: Valkey/Redis clustering support for distributed deployments
- **Async processing**: Full async/await support throughout execution pipeline

### Performance Optimization
- **Memory cleanup**: Configurable TTL and cleanup policies for old iteration data
- **Efficient storage**: Compressed JSON serialization for iteration state
- **Connection pooling**: Shared database connections across agent instances

## Testing Strategy

### Unit Testing
```python
# Model validation testing
def test_iteration_state_validation():
    state = IterationState(
        goal="test goal",
        context_id="ctx-123", 
        task_id="task-456"
    )
    assert state.iteration_count == 0
    assert state.should_continue == True

# Memory integration testing  
async def test_memory_manager():
    manager = IterativeMemoryManager("memory")
    await manager.store_iteration_state("ctx-123", state)
    loaded = await manager.load_iteration_state("ctx-123") 
    assert loaded.goal == state.goal
```

### Integration Testing
```python
# End-to-end iterative execution
async def test_iterative_agent():
    config = AgentConfiguration(agent_type=AgentType.ITERATIVE)
    executor = AgentUpExecutor(agent, config)
    
    # Mock A2A context and event queue
    result = await executor.execute(context, event_queue)
    
    # Verify iteration state persisted
    memory_manager = IterativeMemoryManager()
    state = await memory_manager.load_iteration_state(context.current_task.context_id)
    assert state.iteration_count > 0
```

### Performance Testing
- **Iteration latency**: Measure time per iteration cycle
- **Memory growth**: Monitor memory usage across long-running iterations
- **Concurrent agents**: Test multiple iterative agents running simultaneously

## Future Extensibility

### Graph Agent Integration
The strategy-based architecture enables easy integration of graph-based agents:

```python
class GraphStrategy(AgentExecutorBase):
    """Graph-based workflow execution strategy"""
    
    def __init__(self, agent, config, graph_definition):
        super().__init__(agent)
        self.graph = parse_graph_definition(graph_definition)
        self.state_machine = GraphStateMachine(self.graph)
    
    async def execute(self, context, event_queue):
        # Execute nodes in graph order with state transitions
        current_node = self.state_machine.get_start_node()
        while current_node:
            result = await self.execute_node(current_node, context)
            current_node = self.state_machine.get_next_node(current_node, result)
```

### Multi-Agent Orchestration
```python
class OrchestrationStrategy(AgentExecutorBase):
    """Multi-agent coordination strategy"""
    
    async def execute(self, context, event_queue):
        # Decompose task across multiple specialized agents
        subtasks = await self.decompose_for_agents(context.current_task)
        results = await asyncio.gather(*[
            self.delegate_to_agent(agent_type, subtask) 
            for agent_type, subtask in subtasks
        ])
        return self.synthesize_results(results)
```

### External Integration Points
- **Workflow engines**: Integration with Temporal, Celery, or other orchestration systems
- **Event streaming**: Apache Kafka or AWS Kinesis for distributed event processing
- **Monitoring**: OpenTelemetry instrumentation for observability
- **API gateways**: Rate limiting and request routing at infrastructure level

## Migration and Deployment

### Deployment Configurations

#### Development
```yaml
agent_type: iterative
memory_config:
  enabled: true
  persistence: false  # In-memory for fast development
iterative_config:
  max_iterations: 5   # Lower limits for testing
```

#### Production
```yaml
agent_type: iterative  
memory_config:
  enabled: true
  persistence: true
  max_entries: 10000
  ttl_hours: 168      # 1 week retention
iterative_config:
  max_iterations: 50  # Higher limits for complex tasks
  timeout_minutes: 120
```

### Monitoring and Observability
```python
# Structured logging with correlation IDs
logger.info(
    "iteration_completed",
    extra={
        "context_id": state.context_id,
        "iteration": state.iteration_count,
        "goal_status": state.reflection_data.goal_achievement_status,
        "actions_taken": len(state.action_history),
    }
)

# Metrics collection
metrics.increment("agent.iterations.completed")
metrics.histogram("agent.iteration.duration", duration_ms)
metrics.gauge("agent.active_contexts", active_count)
```

## Success Criteria

### Technical Success Metrics
1. **Clean Architecture**: Zero legacy code, strong typing throughout
2. **LLM Integration**: All decisions made via structured LLM prompts
3. **Memory Persistence**: Cross-session state and learning preservation
4. **Extensibility**: Easy addition of new agent types via strategy pattern
5. **A2A Compliance**: Native integration with A2A protocol patterns

### Performance Success Metrics  
1. **Iteration Latency**: < 2 seconds per iteration cycle
2. **Memory Efficiency**: < 10MB state storage per active context
3. **Concurrent Capacity**: Support 100+ concurrent iterative agents
4. **Success Rate**: > 95% goal achievement for well-defined tasks

### User Experience Success Metrics
1. **Configuration Simplicity**: Single YAML field to enable iterative mode
2. **CLI Integration**: Seamless agent type selection during project creation
3. **Debugging Clarity**: Clear iteration progress and decision reasoning
4. **Documentation Quality**: Complete usage examples and troubleshooting guides

## Conclusion

This specification defines a comprehensive, production-ready architecture for self-directed iterative agents within AgentUp. The design emphasizes clean code principles, strong typing, LLM-driven intelligence, and comprehensive memory integration while maintaining the flexibility needed for future enhancements.

The modular strategy-based architecture ensures that reactive agents continue working unchanged while enabling powerful new iterative capabilities. The extensive use of Pydantic models provides type safety and validation throughout the system, and the integration with AgentUp's existing memory and A2A infrastructure ensures compatibility with the broader ecosystem.

By following this specification, AgentUp will provide a robust foundation for building intelligent, self-directed agents that can handle complex, multi-step tasks while learning from their experiences and improving over time.