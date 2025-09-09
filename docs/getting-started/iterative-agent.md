# Iterative Agents

Iterative agents are one of AgentUp's two execution strategies, designed for complex, multi-step goals that require autonomous problem-solving and self-directed execution.

## Overview

Unlike reactive agents that handle simple request/response interactions, iterative agents are designed for tasks that require:

- **Goal decomposition** into actionable subtasks
- **Multi-turn execution** with continuous progress tracking
- **Self-reflection** and adaptive planning
- **Autonomous completion detection** with confidence scoring

## How Iterative Agents Work

Iterative agents implement a continuous 5-step execution loop:

### 1. **Decompose Goal**
The agent uses LLM reasoning to break down the user's high-level goal into specific, actionable tasks.

### 2. **Execute Task**
Using available tools and capabilities, the agent executes the next planned action.

### 3. **Observe Results**
The agent captures and analyzes the results of its actions, recording success or failure.

### 4. **Reflect on Progress**
Through LLM-powered reflection, the agent assesses:
- Current progress toward the goal
- Whether the goal is achieved, partially achieved, or requires more work
- What insights were learned from this iteration
- What challenges were encountered

### 5. **Decide Next Action**
Based on reflection, the agent decides whether to:
- Continue with more iterations
- Mark the goal as complete (using the `mark_goal_complete` capability)
- Adapt the plan based on new information

## Agent Type Selection

When creating a new agent project with `agentup init`, you'll be prompted to select the execution type:

```
Select agent execution type:
❯ Iterative (self-directed multi-turn loops)
  Reactive (single-shot request/response)
```

**Choose Iterative for:**
- Complex research tasks
- Multi-step workflows
- Goals requiring tool orchestration
- Tasks needing adaptive problem-solving

**Choose Reactive for:**
- Simple API responses
- Single-shot information requests
- Stateless interactions

## Configuration

### Basic Configuration

Add iterative agent settings to your `agentup.yml`:

```yaml
agent_type: iterative

iterative_config:
  max_iterations: 50                      # Maximum iterations per task (1-100)
  reflection_interval: 1                  # Reflect every N iterations
  require_explicit_completion: true       # Require explicit completion signal
  timeout_minutes: 30                     # Task timeout in minutes
  completion_confidence_threshold: 0.8    # Minimum confidence for completion (0.0-1.0)

memory:
  persistence: true                       # Enable memory for learning
  max_entries: 1000                      # Maximum memory entries
  ttl_hours: 24                          # Memory TTL in hours
```

### Configuration Options

| Setting | Default | Range | Description |
|---------|---------|--------|-------------|
| `max_iterations` | 10 | 1-100 | Maximum number of iterations per task before timeout |
| `reflection_interval` | 1 | ≥1 | How often to perform deep reflection (every N iterations) |
| `require_explicit_completion` | true | boolean | Whether agents must explicitly signal completion |
| `timeout_minutes` | 30 | ≥1 | Maximum time allowed for task execution |
| `completion_confidence_threshold` | 0.8 | 0.0-1.0 | Minimum confidence required to accept goal completion |

### Memory Integration

Iterative agents leverage AgentUp's memory system for:

- **Context Preservation**: Maintaining conversation history across iterations
- **Learning Insights**: Storing successful patterns and error experiences
- **Progress Tracking**: Remembering what has been accomplished
- **Goal Continuity**: Resuming interrupted tasks

## Goal Completion

### The mark_goal_complete Capability

Iterative agents use a special system capability called `mark_goal_complete` to signal when a goal has been achieved. This capability accepts:

```json
{
  "summary": "Comprehensive summary of what was accomplished",
  "result_content": "The actual substantive result or answer",
  "confidence": 0.95,
  "tasks_completed": [
    "Task 1 description", 
    "Task 2 description"
  ],
  "remaining_issues": [
    "Known limitation 1",
    "Future improvement 2"
  ]
}
```

### Confidence Threshold Enforcement

The `completion_confidence_threshold` setting enforces quality standards:

- **High Confidence (0.8-1.0)**: Goals must be substantially complete
- **Lower Threshold for Stuck Agents**: If an agent is detected in a loop, the threshold automatically reduces by 20%
- **Security Enforcement**: Completion below threshold is rejected, forcing continued iterations

### Automatic Termination

Iterative agents will automatically terminate when:

- **Goal Completed**: Agent calls `mark_goal_complete` with sufficient confidence
- **Max Iterations Reached**: Configured limit exceeded (logged for monitoring)
- **Timeout Exceeded**: Task duration exceeds `timeout_minutes`
- **Stuck Loop Detected**: Agent repeats similar actions without progress

## Example Workflow

Here's how an iterative agent might handle the goal "Research and summarize the latest trends in AI agents":

### Iteration 1: Planning
```
Goal: Research and summarize the latest trends in AI agents
Plan: [
  "Search for recent articles on AI agent trends",
  "Identify key themes and technologies", 
  "Compile findings into structured summary"
]
Action: Search for recent AI agent research papers
```

### Iteration 2: Data Collection
```
Previous: Found 15 relevant papers from 2024
Action: Extract key themes from the research papers
Result: Identified trends in multimodal agents, tool use, and reasoning
```

### Iteration 3: Analysis
```
Previous: Collected data on agent trends
Action: Analyze patterns and synthesize insights
Result: Grouped trends into categories with examples
```

### Iteration 4: Completion
```
Previous: Analysis complete, comprehensive findings ready
Action: mark_goal_complete({
  "summary": "Researched and analyzed 15 recent papers on AI agent trends",
  "result_content": "# AI Agent Trends 2024\n\n## Key Findings...",
  "confidence": 0.9,
  "tasks_completed": ["Literature search", "Trend analysis", "Report generation"],
  "remaining_issues": ["Could expand to include industry reports"]
})
```

## Best Practices

### For Users

1. **Clear Goals**: Provide specific, measurable objectives
2. **Tool Access**: Ensure agents have necessary capabilities for the task
3. **Reasonable Scope**: Match goals to iteration limits and timeouts
4. **Monitor Progress**: Watch iteration outputs for progress signals

### For Configuration

1. **Appropriate Iteration Limits**: Set `max_iterations` based on task complexity
2. **Quality Thresholds**: Adjust `completion_confidence_threshold` for your quality standards
3. **Memory Settings**: Enable persistence for learning and context retention
4. **Timeout Management**: Set realistic `timeout_minutes` for your use cases

## Debugging and Monitoring

### Progress Tracking

Iterative agents provide detailed progress information:

- **Iteration Count**: Current iteration number
- **Action History**: Record of all actions taken
- **Reflection Data**: Agent's self-assessment of progress
- **Completion Metadata**: Confidence scores and timing information

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Stuck in Loop** | Repeating similar actions | Agent will auto-detect and lower completion threshold |
| **Premature Completion** | Low confidence threshold | Increase `completion_confidence_threshold` |
| **Timeout Reached** | Complex task, insufficient time | Increase `timeout_minutes` or `max_iterations` |
| **Never Completes** | Unclear goals or missing tools | Provide clearer objectives and required capabilities |

### Security Considerations

- **Confidence Enforcement**: Completion thresholds prevent low-quality results
- **Input Validation**: All completion data is sanitized and validated
- **Audit Logging**: All completion events are logged for security monitoring
- **Timeout Protection**: Prevents runaway iterations consuming resources

## Performance Characteristics

### Resource Usage

- **Memory**: Grows with iteration history and reflection data
- **Compute**: Each iteration involves LLM calls for planning and reflection
- **Storage**: Conversation history and state preserved between iterations

### Scaling Considerations

- **Iteration Limits**: Higher limits increase completion rates but use more resources
- **Memory Management**: Configure appropriate TTL for memory cleanup
- **Parallel Execution**: Multiple iterative agents can run concurrently
- **Quality vs Speed**: Higher confidence thresholds improve quality but may increase iteration count

## Migration from Reactive Agents

To convert a reactive agent to iterative:

1. **Update Configuration**:
   ```yaml
   agent_type: iterative
   ```

2. **Add Iterative Settings**:
   ```yaml
   iterative:
     max_iterations: 10
     completion_confidence_threshold: 0.8
   ```

3. **Enable Memory** (optional but recommended):
   ```yaml
   memory:
     persistence: true
   ```

4. **Test with Complex Goals**: Iterative agents excel with multi-step objectives

The agent will automatically begin using the iterative execution strategy on the next request.