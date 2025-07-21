# Create Your First AI Agent


In this tutorial, you'll create a simple as they come, out of the box basic AgentUp agent. This will help you understand the core concepts and get hands-on experience with the framework.


!!! Prerequisites
    - AgentUp installed ([Installation Guide](installation.md))
    - Basic understanding of YAML configuration
    - Terminal/command prompt access

## Create the Agent Project

```bash
# Create a new agent project
agentup agent create
```

Follow the prompts to set up your agent:

```bash
----------------------------------------
Create your AI agent:
----------------------------------------
? Agent name: Basic Agent
? Description: AI Agent Basic Agent Project.
? Would you like to customize the features? Yes
? Select features to include: (Use arrow keys to move, <space> to select, <a> t
o toggle, <i> to invert)
 » ● Authentication Method (API Key, Bearer(JWT), OAuth2)
   ○ Context-Aware Middleware (caching, retry, rate limiting)
   ○ State Management (conversation persistence)
   ○ AI Provider (ollama, openai, anthropic)
   ○ MCP Integration (Model Context Protocol)
   ○ Push Notifications (webhooks)
   ○ Development Features (filesystem plugins, debug mode)
```

After selecting only "Authentication Method", you select "API Key":

```bash
? Select authentication method: (Use arrow keys)
 » API Key (simple, good for development)
   JWT Bearer (production-ready with scopes)
   OAuth2 (enterprise-grade with provider integration)
```

Hit Enter to create the agent project. This will generate a directory structure like this:

```bash
Creating project...
Initializing git repository...
Git repository initialized

✓ Project created successfully!

Location: /Users/lhinds/basic_agent

Next steps:
  1. cd basic_agent
  2. uv sync                    # Install dependencies
  3. agentup agent serve        # Start development server
```


You should see:
```
basic_agent
├── agentup.yml
├── pyproject.toml
└── README.md
```

Let's walk through the key files:

- **`agentup.yml`**: Main configuration file for your agent.
- **`pyproject.toml`**: Agent metadata and Plugin dependencies (more on this later).
- **`README.md`**: Basic documentation for your agent.



## Understand the Basic Configuration

The `agentup.yml` file is where you define your agent's behavior and capabilities.

Let's examine the generated configuration:

```bash
cat agentup.yml
```

First we have our basic agent configuration:

```yaml
name: "basic-agent"
description: "AI Agent Basic Agent Project"
version: "0.1.0"
```

Next our where plugins are defined

!!! plugins
    Plugins are where the magic happens. They define the capabilities your agent can perform. In this case, we have a simple "Hello Plugin" that responds to greetings. Quite boring, but it serves as a good starting point.

```yaml
plugins:
  - plugin_id: hello
    name: Hello Plugin
    description: Simple greeting plugin for testing and examples
    tags: [hello, basic, example]
    input_mode: text
    output_mode: text
    keywords: [hi, greetings]
    patterns: ['^hello']
    routing_mode: direct
    priority: 50
    capabilities:
      - capability_id: hello
        required_scopes: ["api:read"]
        enabled: true
```

Some key points about this plugin configuration:

  Let's explain the plugin configuration in a more visually pleasing way:

  | Property | Description | Example |
  |----------|-------------|---------|
  | **input_mode** | Format the plugin accepts | `text` |
  | **output_mode** | Format the plugin returns | `text` |
  | **keywords** | Trigger words for this plugin | `[hi, greetings]` |
  | **patterns** | Regex patterns to match | `['^hello']` |
  | **routing_mode** | Request routing method | `direct` |
  | **priority** | Execution order (lower = higher) | `50` |
  | **capabilities** | Functions this plugin provides | hello |
  | **required_scopes** | Access permissions needed | `["api:read"]` |

!!! routing

    The `routing_mode` defines how requests are handled. In this case, `direct` means the plugin will handle requests directly without the direction of the Large Language Model (LLM). This is useful for simple plugins that you want to be 'deterministic'. When routing is set to `llm`, the LLM will decide which plugin to use based on the request context.

!!! capabilities

    The `capabilities` section defines the specific functions this plugin provides. Each capability will
    inform on the scopes it requires, which is important for security and access control. More on that later.

### Middleware Configuration

```yaml
middleware:
  - name: logged
    params:
      log_level: 20
  - name: timed
    params: {}
  - name: rate_limiting
    config:
      requests_per_minute: 60
```

Middleware allows you to add cross-cutting concerns like logging, timing, and rate limiting. In this example:

- **`logged`**: Logs requests and responses at the specified log level (20 = INFO).
- **`timed`**: Measures the time taken to process requests.
- **`rate_limiting`**: Limits requests to 60 per minute to prevent abuse

!!! tip "plugin middleware"
    Middleware can be applied to specific plugins or globally. This allows you to control how middleware behaves for different capabilities of your agent.


### Security Configuration

```yaml
security:
  enabled: true
  type: api_key
  auth:
    # Default to API key authentication
    api_key:
      header_name: "X-API-Key"
      location: "header"  # Options: header, query, cookie
      keys:
        - key: "24vgyiyNuzvPdtRG5R80YR4_eKXC9dk0"
          scopes: ["api:read", "api:write", "system:read"]  # Permissions for demo plugin
  # Basic scope hierarchy for minimal template
  scope_hierarchy:
    admin: ["*"]        # Admin has all permissions
    api:write: ["api:read"]   # Write access includes read
    api:read: []        # Basic read access
    system:read: []     # System information access
    files:read: []      # File read access
```

This section configures security for your agents and can get quite complex, for now, our basic agent
uses `api_key` authentication, later tutorials will cover more advanced topics like OAuth and JWT.

The `location` specifies where the API key should be sent in requests. In this case, it's in the header,
those developing web applications may prefer to use query parameters or cookies.

`scope_hierarchy` is something we will cover in more detail later, but it allows you to define a hierarchy of permissions for your agent. This is useful for controlling access to different capabilities based on the user's role. We are using scopes here, but its really designed to work with protocols like OAuth2 and JWT, where
scopes are backed by cryptographic tokens. For an API Key, those scopes would need to be mapped to another
system that can cross check the permissions of the API key being used.

Right that will do for the basic configuration, let's move on to starting the agent and testing it out!

## Verify Agent Functionality (starting the agent)

Right, let's start the agent and see if everything is working as expected!

```bash
# Start the agent
agentup agent serve
```

!!! tip "Under the hood"
    AgentUp uses FastAPI under the hood, so you don't have to use `agentup agent serve` to start your agent, you can also use `uvicorn` directly if you prefer, for example you may want to use the `--reload` option or `--workers` option to run multiple instances of your agent for load balancing.

We  Agent start up , load the configuration, and register the plugins and activities various services. You should see output similar to this:

```
2025-07-21T22:08:27.898312Z [INFO     ] Registered built-in plugin: hello (Hello Plugin) [agent.plugins.builtin]
2025-07-21T22:08:27.898388Z [INFO     ] Registered hello plugin   [agent.plugins.core_plugins]
2025-07-21T22:08:27.958877Z [INFO     ] Registered built-in capability 'hello' from plugin 'hello' with scopes: ['api:read'] [agent.plugins.builtin]
2025-07-21T22:08:27.958968Z [INFO     ] Built-in plugins registered and integrated [agent.plugins.integration]
2025-07-21T22:08:27.992681Z [INFO     ] Configuration loaded 0 plugin capabilities (out of 0 discovered) [agent.plugins.integration]
2025-07-21T22:08:27.992760Z [INFO     ] Plugin adapter integrated with function registry for AI function calling [agent.plugins.integration]
2025-07-21T22:08:28.024429Z [INFO     ] Registered plugin capability with scope enforcement: hello (scopes: ['api:read']) [agent.capabilities.executors]
2025-07-21T22:08:28.024517Z [INFO     ] Loaded plugin: hello with 1 capabilities [PluginService]
2025-07-21T22:08:28.024564Z [INFO     ] Plugin service initialized with 1 plugins [PluginService]
2025-07-21T22:08:28.024612Z [INFO     ] ✓ Initialized PluginService [agent.services.bootstrap]
2025-07-21T22:08:28.024663Z [INFO     ] ================================================== [agent.services.bootstrap]
2025-07-21T22:08:28.024692Z [INFO     ] Basic Agent v0.2.0 initialized [agent.services.bootstrap]
2025-07-21T22:08:28.024716Z [INFO     ] AI Agent Basic Agent Project. [agent.services.bootstrap]
2025-07-21T22:08:28.024736Z [INFO     ] ================================================== [agent.services.bootstrap]
2025-07-21T22:08:28.024758Z [INFO     ] Active Services (4):      [agent.services.bootstrap]
2025-07-21T22:08:28.024779Z [INFO     ]   ✓ SecurityService       [agent.services.bootstrap]
2025-07-21T22:08:28.024810Z [INFO     ]   ✓ MiddlewareManager     [agent.services.bootstrap]
2025-07-21T22:08:28.024846Z [INFO     ]   ✓ CapabilityRegistry    [agent.services.bootstrap]
2025-07-21T22:08:28.024866Z [INFO     ]   ✓ PluginService         [agent.services.bootstrap]
2025-07-21T22:08:28.024900Z [INFO     ] Enabled Features:         [agent.services.bootstrap]
2025-07-21T22:08:28.024934Z [INFO     ]   ✓ Security (api_key)    [agent.services.bootstrap]
2025-07-21T22:08:28.024956Z [INFO     ]   ✓ Capabilities (4)      [agent.services.bootstrap]
2025-07-21T22:08:28.024977Z [INFO     ] ================================================== [agent.services.bootstrap]
2025-07-21T22:08:28.061587Z [INFO     ] Loaded 1 plugins from config [agent.api.routes]
2025-07-21T22:08:28.061639Z [INFO     ] Plugin 0: id=hello, desc=Simple greeting plugin for testing and examples [agent.api.routes]
2025-07-21T22:08:28.077410Z [INFO     ] Application startup complete. [uvicorn.error]
```

Open a new terminal and test the agent:

### Check Agent Status
```bash
curl http://localhost:8000/health | jq 
```

Expected response:
```json
{
  "status": "healthy",
  "agent": "Agent",
  "timestamp": "2025-07-21T23:25:18.630604"
}
```

### Call the Hello Plugin

Ok, well done so far, now let's test the plugin we created. This is a simple plugin
that echos back the message you send it, so let's try it out:

```bash
curl -X POST http://localhost:8000/ \
  -H "X-API-Key: 24vgyiyNuzvPdtRG5R80YR4_eKXC9dk0" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{
          "kind": "text",
          "text": "Hello Agent"
        }],
        "messageId": "msg-001",
        "kind": "message"
      }
    },
    "id": "req-001"
  }' | jq
```

!!! tip "A2A Spec and JSON-RPC"
    AgentUp uses the [A2A Specification](https://a2a.spec) for its API design, which is based on JSON-RPC 2.0. This means there is a single endpoint (`/`) for all requests, and you can use JSON-RPC methods to interact with the agent. The `message/send` method is used to send messages to the agent.

We should see an A2A response like this:

```json
{
  "id": "req-001",
  "jsonrpc": "2.0",
  "result": {
    "artifacts": [
      {
        "artifactId": "5e13b182-fdf7-487f-8f76-0a807f0b680b",
        "description": null,
        "extensions": null,
        "metadata": null,
        "name": "Basic Agent-result",
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Echo: Hello Agent"
          }
        ]
      }
    ],
    "contextId": "962aed21-4519-4ef5-a877-b9b25ba0d56d",
    "history": [
      {
        "contextId": "962aed21-4519-4ef5-a877-b9b25ba0d56d",
        "extensions": null,
        "kind": "message",
        "messageId": "msg-001",
        "metadata": null,
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Hello Agent"
          }
        ],
        "referenceTaskIds": null,
        "role": "user",
        "taskId": "5869775c-1a55-4e56-8361-dba1492d454f"
      },
      {
        "contextId": "962aed21-4519-4ef5-a877-b9b25ba0d56d",
        "extensions": null,
        "kind": "message",
        "messageId": "93047743-f065-4dec-a4b6-60ea98244084",
        "metadata": null,
        "parts": [
          {
            "kind": "text",
            "metadata": null,
            "text": "Processing request with for task 5869775c-1a55-4e56-8361-dba1492d454f using Basic Agent."
          }
        ],
        "referenceTaskIds": null,
        "role": "agent",
        "taskId": "5869775c-1a55-4e56-8361-dba1492d454f"
      }
    ],
    "id": "5869775c-1a55-4e56-8361-dba1492d454f",
    "kind": "task",
    "metadata": null,
    "status": {
      "message": null,
      "state": "completed",
      "timestamp": "2025-07-21T22:38:56.583225+00:00"
    }
  }
}
```

Ok, that was a lot of information, but the key part is the `result` field, which contains the `artifacts` and `history` of the interaction. The `parts` of the first artifact show the response from the Hello Plugin:

```json
{
  "kind": "text",
  "metadata": null,
  "text": "Echo: Hello Agent"
}
```

This confirms that the plugin is working correctly and echoing back the message you sent!

But as said, this is quite a boring Agent, so let's spice it up a bit in the next section by making our Agent AI capable and adding a plugin that can handle more complex interactions!


<div class="next-page-cta">
    <div class="next-page-content">
        <span class="next-page-label">Next Step</span>
        <a href="installation" class="next-page-link">
            <span class="next-page-title">Create an AI Agent</span>
            <span class="next-page-arrow">→</span>
        </a>
    </div>
</div>