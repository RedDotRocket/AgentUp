# Create Your First AI Agent

In this tutorial, you'll create a simple as they come, out of the box, basic AgentUp agent. This will help you understand the core concepts and get hands-on experience with the framework.


!!! Prerequisites
    - AgentUp installed ([Installation Guide](installation.md))
    - Basic understanding of YAML configuration
    - Terminal/command prompt access
    - Familiarity with JSON-RPC (optional, but helpful)

## Create the Agent Project

Creating an agent project is straightforward. Use the `agentup init` command to scaffold a new agent project.

Open your terminal and run:

``` { .bash .copy }
agentup init
```

Follow the prompts to set up your agent:

```{.text}
----------------------------------------
Create your AI agent:
----------------------------------------
? Agent name: Basic Agent
? Description: AI Agent Basic Agent Project.
? Version: 0.0.1
? Would you like to customize the features? No
```

Hit **Enter** to create the agent project.

```{.text}
Creating project...
Initializing git repository...
Git repository initialized

──────────────────────────────────────────────────
✓ Project created successfully!
──────────────────────────────────────────────────

Location: /Users/lhinds/basic_agent

Read the documentation to get started:
https://docs.agentup.dev/getting-started/first-agent/

Next steps:
  1. cd basic_agent
  2. uv sync                # Install dependencies
  3. uv add <plugin_name>   # Add AgentUp plugins
  4. agentup plugin sync    # Sync plugins with config
  5. agentup run            # Start development server
```


 This will generate a directory structure like this:

``` { .bash }
basic_agent
├── agentup.yml
└── README.md
└── pyproject.toml
```

Let's walk through the key files:

| File | Description |
|------|-------------|
| **`agentup.yml`** | Main configuration file for your agent. |
| **`README.md`** | Basic documentation for your agent. |
| **`pyproject.toml`** | Python project configuration file (used for plugin management). |

## Understanding `agentup.yml`

The `agentup.yml` file is where you define your agent's behavior, capabilities
and how it integrates with other services.

### AgentUp Basic Configuration

First we have our basic agent configuration:

```yaml
name: "basic-agent"
description: AI Agent Project.
version: 0.5.7
url: http://localhost:8000
provider_organization: AgentUp
provider_url: https://agentup.dev
icon_url: https://raw.githubusercontent.com/RedDotRocket/AgentUp/refs/heads/main/assets/icon.png
documentation_url: https://docs.agentup.dev
```

You're free to change any of these!

That's it for the basic configuration, there is a lot more, but these will be covered in the later
sections of this guide.

### Verify Agent Functionality (starting the agent)

Let's start the agent and see if everything is working as expected!

```{.bash .copy}
# Start the agent
agentup run
```

??? success "Expected Output"
    ```
    INFO:     Will watch for changes in these directories: ['/Users/lhinds/basic_agent']
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
    INFO:     Started reloader process [61915] using StatReload
    2025-08-21 08:38:59 [debug    ] Loading configuration for the first time
    2025-08-21T07:38:59.399917Z [INFO     ] Configuration loaded successfully [agent.services.config]
    2025-08-21T07:38:59.431421Z [INFO     ] Security mode: configured with 0 allowed plugins [agent.plugins.manager]
    2025-08-21T07:38:59.434045Z [INFO     ] No plugins discovered at entry points. [agent.plugins.manager]
    2025-08-21T07:38:59.436873Z [INFO     ] Started server process [61917] [uvicorn.error]
    2025-08-21T07:38:59.436917Z [INFO     ] Waiting for application startup. [uvicorn.error]
    2025-08-21T07:38:59.437052Z [INFO     ] Starting service initialization [agent.services.bootstrap]
    2025-08-21T07:38:59.437103Z [INFO     ] No plugins configured, skipping plugin integration [agent.services.bootstrap]
    2025-08-21T07:38:59.437146Z [INFO     ] Initializing middleware manager [MiddlewareManager]
    2025-08-21T07:38:59.437179Z [INFO     ] Middleware manager initialized with 4 global middleware [MiddlewareManager]
    2025-08-21T07:38:59.437203Z [INFO     ] ✓ Initialized MiddlewareManager [agent.services.bootstrap]
    2025-08-21T07:38:59.438243Z [INFO     ] Capability registry initialized with 3 capabilities [BuiltinCapabilityRegistry]
    2025-08-21T07:38:59.438274Z [INFO     ] ✓ Initialized BuiltinCapabilityRegistry [agent.services.bootstrap]
    2025-08-21T07:38:59.438308Z [INFO     ] Initializing push notification service [PushNotificationService]
    2025-08-21T07:38:59.492793Z [INFO     ] Push notification service initialized with memory backend [PushNotificationService]
    2025-08-21T07:38:59.492862Z [INFO     ] ✓ Initialized PushNotificationService [agent.services.bootstrap]
    2025-08-21T07:38:59.492910Z [INFO     ] ================================================== [agent.services.bootstrap]
    2025-08-21T07:38:59.492933Z [INFO     ] Agent v0.5.1 initialized  [agent.services.bootstrap]
    2025-08-21T07:38:59.492954Z [INFO     ] AgentUp Agent             [agent.services.bootstrap]
    2025-08-21T07:38:59.492971Z [INFO     ] ================================================== [agent.services.bootstrap]
    2025-08-21T07:38:59.492989Z [INFO     ] Active Services (3):      [agent.services.bootstrap]
    2025-08-21T07:38:59.493010Z [INFO     ]   ✓ MiddlewareManager     [agent.services.bootstrap]
    2025-08-21T07:38:59.493030Z [INFO     ]   ✓ BuiltinCapabilityRegistry [agent.services.bootstrap]
    2025-08-21T07:38:59.493048Z [INFO     ]   ✓ PushNotificationService [agent.services.bootstrap]
    2025-08-21T07:38:59.493071Z [INFO     ] ====================      [agent.services.bootstrap]
    2025-08-21T07:38:59.507262Z [INFO     ] Application startup complete. [uvicorn]
    ```

??? tip "Under the hood. FastAPI"
    AgentUp uses FastAPI under the hood, so you don't have to use `agentup run` to start your agent, you can also use `uvicorn` directly
    if you prefer, for example you may want to use the `--reload` option or `--workers` option to run multiple instances of your agent for load balancing.


### Check Agent Status

Open a new terminal and test the agent:

```{.bash .copy}
curl http://localhost:8000/health | jq
```

??? success "Expected Output"
    ```json
    {
      "status": "healthy",
      "agent": "Agent",
      "timestamp": "2025-07-21T23:25:18.630604"
    }
    ```

### Call the Agent's Main Interface

Ok, well done so far, now let's test the main endpoint used by the Agent.

The following curl statement is using JSON RPC, which is the standard
Agent communication protocol for AgentUp. It's not going to do much yet, as we
have not wired up a AI Model or plugin.

```{.bash .copy}
curl -s -X POST http://localhost:8000/ \
    -H "Content-Type: application/json" \
    -H "X-API-Key: admin-key-123" \
    -d '{
      "jsonrpc": "2.0",
      "method": "message/send",
      "params": {
        "message": {
          "role": "user",
          "parts": [{"kind": "text", "text": "hello"}],
          "message_id": "msg-001",
          "kind": "message"
        }
      },
      "id": "req-001"
    }' |  jq -r '.result.artifacts[].parts[] | select(.kind=="text")'
```

??? success "Expected Output"
    ```{.json }
    {
      "kind": "text",
      "metadata": null,
      "text": "I received your message: 'hello'. However, my AI capabilities are currently unavailable. Please try again later."
    }
    ```

| Value | Description |
|------|-------------|
| **`method`** | The JSON-RPC method to call (e.g., `message/send`). |
| **`params`** | The parameters to pass to the method. |
| **`id`** | A unique identifier for the request. |

We will look into the params later, but the main aspect to note is the structure of the message being sent to the agent.

The `message` object contains the `role`, `parts`, `message_id`, and `kind` fields, which are all important for the agent to
understand and process the request. In this case we are sending text content of `hello` which triggers a status check in the agent

!!! tip "A2A Spec and JSON-RPC"
    AgentUp uses the [A2A Specification](../middleware/a2a-protocol.md) for its API design, which is based on JSON-RPC 2.0. This means there is a single endpoint (`/`) for all requests, and you can use JSON-RPC methods to interact with the agent. The `message/send` method is used to send messages to the agent.

### Agent Card

Last of all, as AgentUp follows the [A2A Specification](https://a2a.spec), the Agent Card allows our Agent to communicate its capabilities and how to interact with it.

Ours is not going to be much fun for other Agents and users yet, but that will change in the next chapter.

```bash
curl -s http://localhost:8000/.well-known/agent-card.json |jq
```

??? success "Response"

    ```{.json }
    {
      "additionalInterfaces": null,
      "capabilities": {
        "extensions": null,
        "pushNotifications": true,
        "stateTransitionHistory": false,
        "streaming": true
      },
      "defaultInputModes": [
        "text"
      ],
      "defaultOutputModes": [
        "text"
      ],
      "description": "AI Agent Basic Agent Project.",
      "documentationUrl": "https://docs.agentup.dev",
      "iconUrl": "https://raw.githubusercontent.com/RedDotRocket/AgentUp/refs/heads/main/assets/icon.png",
      "name": "basic-agent",
      "preferredTransport": "JSONRPC",
      "protocolVersion": "0.3.2",
      "provider": {
        "organization": "AgentUp",
        "url": "http://localhost:8000"
      },
      "security": null,
      "securitySchemes": null,
      "signatures": null,
      "skills": [],
      "supportsAuthenticatedExtendedCard": false,
      "url": "http://localhost:8000",
      "version": "0.6.3"
    }
    ```
