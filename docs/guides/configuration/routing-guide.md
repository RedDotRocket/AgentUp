# AgentUp Routing System Guide

The AgentUp routing system determines how incoming user messages are processed and which skills handle them. This guide explains the different routing modes, when to use each, and how to configure them effectively.

## Overview

AgentUp supports three distinct routing approaches:

1. **AI Routing** - Uses Large Language Models (LLMs) to ly understand user requests and call appropriate functions
2. **Direct Routing** - Uses keyword matching and pattern recognition to route messages to specific skills
3. **Mixed Routing** - Combines both approaches, allowing different skills to use different routing methods

## Routing Flow Diagram

```
User Message
     |
     v
┌────────────────┐
│ Message Router │
└────────┬───────┘
         |
         v
    ┌─────────┐
    │ Skill?  │
    └────┬────┘
         |
    ┌────v────┐      ┌──────────────┐
    │ Direct  │ Yes  │ Pattern/     │
    │ Mode?   ├─────→│ Keyword      │
    │         │      │ Matching     │
    └────┬────┘      └──────┬───────┘
         │ No               │
         v                  │
    ┌────────────┐          │
    │ AI Routing │          │
    │ (Function  │          │
    │ Calling)   │          │
    └────┬───────┘          │
         │                  │
         v                  v
    ┌────────────────────────┐
    │    Execute Skill       │
    │     Handler            │
    └────────────────────────┘
```

## Configuration Structure

### New Consolidated Format

```yaml
# Global routing configuration
routing:
  default_mode: ai           # Default routing mode for skills
  default_skill: ai_assistant # Fallback skill when no match found
  fallback_enabled: true     # Allow AI→Direct fallback if LLM fails

# Skills with integrated routing configuration
skills:
  - skill_id: weather_bot
    name: Weather Assistant
    description: Get weather information for any location
    input_mode: text
    output_mode: text
    routing_mode: ai         # This skill uses AI routing

  - skill_id: echo
    name: Echo Skill
    description: Echo back user messages
    input_mode: text
    output_mode: text
    routing_mode: direct     # This skill uses direct routing
    keywords: [echo, repeat, say]
    patterns: ['echo.*', 'repeat.*', 'say.*']

  - skill_id: calculator
    name: Calculator
    description: Perform mathematical calculations
    input_mode: text
    output_mode: text
    # Uses default_mode (ai) since routing_mode not specified
```

## Routing Modes Explained

### 1. AI Routing Mode

**How it works:**
AI routing leverages Large Language Models to understand user intent naturally. When a message arrives,the LLM analyzes it and determines which function (skill) to call based on function descriptions and parameters.

**Characteristics:**
- Natural language understanding
- Context-aware routing decisions
- Can handle complex, multi-step requests
- Requires LLM service configuration
- More flexible but resource-intensive (requires inference costs for LLM calls)

**Best for:**
- Conversational interfaces
- Complex user requests
- When you want natural language interaction
- Skills that need parameter extraction from natural language

**Example Configuration:**
```yaml
skills:
  - skill_id: travel_planner
    name: Travel Planning Assistant
    description: Help users plan trips, find flights, hotels, and activities
    routing_mode: ai
    input_mode: text
    output_mode: text

# AI configuration required
ai:
  enabled: true
  llm_service: openai
  model: gpt-4o-mini
  system_prompt: |
    You are a helpful travel planning assistant. When users ask about travel,
    use the travel_planner function to help them find flights, hotels, and activities.
```

**Example User Interactions:**
```
User: "I want to plan a trip to Paris for next week"
→ AI understands intent and calls travel_planner function

User: "Find me a hotel in downtown Tokyo under $200"
→ AI extracts location, price, and type parameters automatically
```

### 2. Direct Routing Mode

**How it works:**
Direct routing uses predefined keywords and regular expression patterns to match user messages to specific skills. It's fast, predictable, and doesn't require AI services.

**Characteristics:**
- Fast, lightweight processing
- Predictable routing behavior
- No external dependencies
- Limited to exact keyword/pattern matches

**Best for:**
- Utility functions
- When you want more deterministic behavior
- Resource-constrained environments
- Skills with clear command patterns

**Example Configuration:**
```yaml
skills:
  - skill_id: system_status
    name: System Status
    description: Check system health and status
    routing_mode: direct
    keywords: [status, health, system, ping]
    patterns: ['system.*status', 'health.*check', 'ping']

  - skill_id: file_manager
    name: File Manager
    description: Manage files and directories
    routing_mode: direct
    keywords: [file, directory, folder, ls, mkdir]
    patterns: ['file.*', 'dir.*', 'folder.*', 'ls.*', 'mkdir.*']
```

**Example User Interactions:**
```
User: "status"
→ Matches 'status' keyword, routes to system_status

User: "system health check"
→ Matches 'system.*status' pattern, routes to system_status

User: "list files in documents"
→ Matches 'file.*' pattern, routes to file_manager
```

### 3. Mixed Routing Mode

**How it works:**
Mixed routing allows different skills to use different routing methods within the same agent. Some skills can use AI routing for natural interaction, while others use direct routing for precise commands.
It could be argued why the need, you could just write your own APIs or functions to handle traditional logic?
With this sort of system, it allows for a gradual migration eitherway from direct routing to AI routing, with one of the other being the fallback.
Everything is caputred in the same configuration, making it easy to manage and optimize and stay on top of your routing logic.

**Best for:**
- Hybrid interfaces (conversational + command-based)
- Gradual migration from direct to AI routing
- Optimizing performance per skill type
- Complex agents with varied interaction patterns

**Example Configuration:**
```yaml
routing:
  default_mode: ai
  fallback_enabled: true

skills:
  # AI-routed conversational skills
  - skill_id: customer_support
    name: Customer Support Assistant
    description: Help customers with questions and issues
    routing_mode: ai

  - skill_id: product_recommender
    name: Product Recommender
    description: Recommend products based on user preferences
    routing_mode: ai

  # Direct-routed utility skills
  - skill_id: system_admin
    name: System Administration
    description: Administrative commands and system control
    routing_mode: direct
    keywords: [admin, system, restart, shutdown, logs]
    patterns: ['admin.*', 'system.*', 'restart.*', 'shutdown.*']

  - skill_id: debug_tools
    name: Debug Tools
    description: Debugging and diagnostic tools
    routing_mode: direct
    keywords: [debug, trace, profile, benchmark]
    patterns: ['debug.*', 'trace.*', 'profile.*']
```

## Use Case Scenarios

### Scenario 1: Customer Service Bot

**Requirements:**
- Natural conversation for support queries
- Quick access to order status and account info
- Integration with knowledge base

**Recommended Approach:** Primarily AI routing with some direct shortcuts

```yaml
routing:
  default_mode: ai
  default_skill: customer_support

skills:
  - skill_id: customer_support
    name: Customer Support
    description: General customer support and question answering
    routing_mode: ai

  - skill_id: order_status
    name: Order Status Checker
    description: Check order status by order number
    routing_mode: direct
    keywords: [order, status, tracking]
    patterns: ['order.*\d+', 'tracking.*\d+']

  - skill_id: account_info
    name: Account Information
    description: Access account details and settings
    routing_mode: direct
    keywords: [account, profile, settings]
```

**Why this works:**
- Most conversations flow naturally through AI routing
- Power users can use direct commands for quick access
- Order lookups with numbers work better with pattern matching

### Scenario 2: Development Tools Agent

**Requirements:**
- Command-line style interface
- Precise control over development tools
- Fast execution of common commands

**Recommended Approach:** Primarily direct routing

```yaml
routing:
  default_mode: direct
  default_skill: help

skills:
  - skill_id: git_manager
    name: Git Operations
    description: Git repository management
    routing_mode: direct
    keywords: [git, commit, push, pull, branch]
    patterns: ['git.*', 'commit.*', 'push.*', 'pull.*']

  - skill_id: test_runner
    name: Test Runner
    description: Run tests and check results
    routing_mode: direct
    keywords: [test, pytest, unittest, coverage]
    patterns: ['test.*', 'pytest.*', 'coverage.*']
```

### Scenario 3: Smart Home Assistant

**Requirements:**
- Natural language for complex scenarios
- Quick commands for common actions
- Context awareness for automation

**Recommended Approach:** Mixed routing optimized per use case

```yaml
routing:
  default_mode: ai
  fallback_enabled: true

skills:
  - skill_id: home_automation
    name: Home Automation
    description: Control smart home devices and create automations
    routing_mode: ai

  - skill_id: quick_controls
    name: Quick Device Controls
    description: Direct device control commands
    routing_mode: direct
    keywords: [lights, temperature, music, tv]
    patterns: ['turn.*on', 'turn.*off', 'set.*to.*']

  - skill_id: scene_manager
    name: Scene Manager
    description: Activate predefined scenes and modes
    routing_mode: direct
    keywords: [scene, mode, movie, sleep, party]
    patterns: ['.*scene', '.*mode']
```

## Performance Considerations

### AI Routing Performance
- **Latency:** 100-2000ms depending on LLM provider
- **Cost:** API calls to LLM service
- **Accuracy:** Very high for natural language
- **Scalability:** Limited by LLM service quotas

### Direct Routing Performance
- **Latency:** 1-10ms for pattern matching
- **Cost:** Minimal computational overhead
- **Accuracy:** Perfect for exact matches, limited for variations
- **Scalability:** Excellent, no external dependencies

### Optimization Tips

1. **Use direct routing for:**
   - High-frequency, simple commands
   - Exact pattern matches
   - Performance-critical operations

2. **Use AI routing for:**
   - Complex natural language queries
   - Parameter extraction from text
   - Context-dependent decisions

3. **Enable fallback:**
   - Set `fallback_enabled: true` to allow AI→Direct fallback
   - Improves reliability when LLM services are unavailable

## Migration Guide

### From Old Format

**Old Configuration:**
```yaml
routing:
  mode: direct
  default_skill: echo
  rules:
    - skill_id: echo
      keywords: [echo, repeat]
      patterns: ['echo.*']

skills:
  - skill_id: echo
    name: Echo Skill
    description: Echo messages
```

**New Configuration:**
```yaml
routing:
  default_mode: direct
  default_skill: echo

skills:
  - skill_id: echo
    name: Echo Skill
    description: Echo messages
    routing_mode: direct
    keywords: [echo, repeat]
    patterns: ['echo.*']
```

### Benefits of Migration

1. **Consolidated configuration:** All skill info in one place
2. **Per-skill routing:** Mix AI and direct routing as needed
3. **Better validation:** Clearer error messages and requirements
4. **Simplified templates:** Less duplication and confusion

## Troubleshooting

### Common Issues

**Issue:** AI routing not working
```yaml
# Problem: AI enabled but no LLM service configured
ai:
  enabled: true
  # Missing llm_service configuration

# Solution: Add LLM service
services:
  openai:
    type: llm
    provider: openai
    api_key: ${OPENAI_API_KEY}
```

**Issue:** Direct routing patterns not matching
```yaml
# Problem: Overly restrictive patterns
skills:
  - skill_id: calculator
    patterns: ['^calculate \d+ \+ \d+$']  # Too specific

# Solution: More flexible patterns
skills:
  - skill_id: calculator
    patterns: ['calcul.*', '\d+.*[\+\-\*\/].*\d+', 'math.*']
```

**Issue:** Skills not being found
```yaml
# Problem: Skill defined but no handler registered
skills:
  - skill_id: my_custom_skill
    name: My Skill

# Solution: Ensure handler is registered in handlers.py
@register_handler("my_custom_skill")
async def handle_my_custom_skill(task: Task) -> str:
    return "Handler response"
```
