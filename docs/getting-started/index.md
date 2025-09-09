# Getting Started with AgentUp

Let's get you up and running with AgentUp! 

This section will guide you through your first steps with the framework.

!!! Prerequisites
    Before diving in, ensure you have the following:

    * Python 3.10 or higher installed
    * Familiarity with YAML configuration files
    * A text editor or IDE for coding
    * curl or an API client for testing endpoints

### What You'll Learn

By the end of this section, you'll:

- Have AgentUp installed and configured
- Understand the core concepts and architecture
- Have created and tested your first agent
- Know the difference between reactive and iterative agents
- Understand how to configure iterative agents for complex goals
- Know how to customize and extend your agents

## Getting Started Guide

Follow these steps to get up and running with AgentUp:

1. **[Installation](installation.md)** - Install AgentUp and its dependencies
2. **[Core Concepts](core-concepts.md)** - Learn the fundamental concepts
3. **[Create Your First Agent](first-agent.md)** - Build and test a basic agent
4. **[Iterative Agents](iterative-agent.md)** - Deep dive into self-directed, goal-based agents
5. **[AI Agent Integration](ai-agent.md)** - Connect with AI providers

## Quick Start

For the impatient, here's the fastest way to get started:

```bash
# Install AgentUp
pip install agentup

# Create a new agent project
agentup init my-agent

# Follow the prompts and choose "Iterative" for complex goal handling
# Start the agent
cd my-agent
uv sync
agentup run
```

Your agent will be running at `http://localhost:8000` and ready to handle complex, multi-step goals through its iterative execution engine.

