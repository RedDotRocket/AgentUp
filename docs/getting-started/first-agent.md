# Create Your First AI Agent

In this tutorial, you'll create a simple as they come, out of the box, basic AgentUp agent. This will help you understand the core concepts and get hands-on experience with the framework.


!!! Prerequisites
    - AgentUp installed ([Installation Guide](installation.md))
    - Basic understanding of YAML configuration
    - Terminal/command prompt access
    - Familiarity with JSON-RPC (optional, but helpful)
## Create the Agent Project

```bash
# Create a new agent project
agentup agent create
```

Follow the prompts to set up your agent:

```bash hl_lines="6 9"
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

```bash hl_lines="2"
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

### agentup.yml

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

#### Plugins

Plugins are where the magic happens. They define the capabilities your agent can perform. In this case, we have a simple "Hello Plugin" that responds to greetings. Quite boring, but it serves as a good starting point.

```yaml
plugins:
  - plugin_id: hello (1)!
    name: Hello Plugin
    description: Simple greeting plugin for testing and examples
    tags: [hello, basic, example]
    input_mode: text
    output_mode: text
    keywords: [hi, greetings]
    patterns: ['^hello']
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
  | **priority** | Execution order (lower = higher) | `50` |
  | **capabilities** | Functions this plugin provides | hello |
  | **required_scopes** | Access permissions needed | `["api:read"]` |

??? question "AgentUp Routing Logic"
    AgentUp uses an **implicit routing system**, where routing is determined by the presence (or absence) of keywords and patterns in the user input. This allows
    deterministic routing, using keywords and patterns to decide which plugin to invoke.

    **Keywords:**

    Array of keywords that trigger direct routing to this plugin when found in user input.

    *Example:* `["file", "directory", "ls", "cat"]`

    **Patterns:**

    Array of regex patterns that trigger direct routing to this plugin when matched against user input.

    *Example:* `["^create file .*", "^delete .*"]`

    If keywords or patterns are matched, the plugin is invoked directly. If no keywords or patterns match, the request is pickedup by the LLM who will then decide which plugin to use based on the natural language used in the request.

#### capabilities

The `capabilities` section defines the specific functions this plugin provides. Each capability will inform on the scopes it requires, which is important for security and access control. More on that later.

### Middleware Configuration

```yaml
middleware:
  - name: timed
    params: {}
  - name: rate_limiting
    config:
      requests_per_minute: 60
```

Middleware allows you to add cross-cutting concerns like logging, timing, and rate limiting. In this example:

- **`timed`**: Measures the time taken to process requests.
- **`rate_limiting`**: Limits requests to 60 per minute to prevent abuse

??? tip "plugin middleware"
    Middleware can also be applied to specific plugins or globally. This allows you to control how middleware behaves for different capabilities of your agent. We will cover this in more detail in the advanced tutorials.


### Security Configuration

AgentUp provides a flexible security model to protect your agent's capabilities.

It supports multiple authentication methods:

- **API Key**: Simple, good for development
- **JWT Bearer**: Signed with scopes declared inside the token body
- **OAuth2**: Signed with scopes, but can also be integrated with external providers

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
    # Role-based scopes
    admin: ["*"]
    manager: ["files:admin", "system:read", "web:search", "image:read"]
    developer: ["files:write", "web:search", "api:write"]
    analyst: ["files:read", "web:search", "image:read"]
    readonly: ["files:read"]

    # Domain hierarchies
    files:admin: ["files:write", "files:read"]
    api:write: ["api:read"]
    files:write: ["files:read"]
    system:admin: ["system:write", "system:read"]
    system:write: ["system:read"]
```

#### Key Configuration Options

| Setting | Description | Example Value |
|---------|-------------|---------------|
| **`header_name`** | HTTP header containing the API key | `"X-API-Key"` |
| **`location`** | Where to set the API key | `header`, `query`, or `cookie` |
| **`keys`** | Valid API keys and their permissions | See scopes below |

??? tip "Mulitiple Keys"
    You can define multiple API keys with different scopes. This allows you to control access to specific capabilities based on the key used.

#### Understanding Scopes & Permissions

The `scope_hierarchy` defines a permission system for your agent:

```yaml
scope_hierarchy:
  admin: ["*"]                    # Full access to everything
  api:write: ["api:read"]         # Write access (includes read)
  api:read: []                    # Basic read-only access
  system:read: []                 # System information access
  files:read: []                  # File reading permissions
```

This allows you to control which API keys can access specific capabilities. For example, the `hello` capability requires the `api:read` scope, so only API keys with that scope can invoke it.

The `scope_hierarchy` system is more detailed then what we cover here. But to
put it succinctly a plugin says what it needs "api:read" and then you, the user,
state what is allowed to use within the `plugin` configuration.

For example:

```yaml hl_lines="5"
plugins:
  - plugin_id: hello
    capabilities:
      - capability_id: hello
        required_scopes: ["api:read"] # - I need this scope to be invoked
        enabled: true
```

This means the `hello` plugin requires the `api:read` scope to be invoked. If an API key does not have this scope, it will not be able to use the `hello` capability.

```yaml hl_lines="4"
 api_key:
      keys:
        - key: "24vgyiyNuzvPdtRG5R80YR4_eKXC9dk0"
          scopes: ["api:read"] # - I allow this scope to invoked
```



!!! warning "Scope Security"
    In the above example, we are using scopes with **basic API keys**. More secure options are **OAuth2** and **JWT** tokens where scopes are cryptographically secured and cannot be tampered with. The expectation is that an external policy and authorization server will mint the tokens and manage the scopes. AgentUp will
    ensure they are enforced at runtime.

## Next Steps

This covers the basic security setup. Ready to see your agent in action? Let's start it up and test it out!

### Verify Agent Functionality (starting the agent)

Right, let's start the agent and see if everything is working as expected!

```bash
# Start the agent
agentup agent serve
```

!!! tip "Under the hood"
    AgentUp uses FastAPI under the hood, so you don't have to use `agentup agent serve` to start your agent, you can also use `uvicorn` directly if you prefer, for example you may want to use the `--reload` option or `--workers` option to run multiple instances of your agent for load balancing.

We  Agent start up , load the configuration, and register the plugins and activities various services. You should see output similar to this:


??? success "Expected Output"
    ```
    [INFO] Registered built-in plugin: hello (Hello Plugin) [agent.plugins.builtin]
    [INFO] Registered hello plugin   [agent.plugins.core_plugins]
    [INFO] Registered built-in capability 'hello' from plugin 'hello' with scopes: ['api:read'] [agent.plugins.builtin]
    [INFO] Built-in plugins registered and integrated [agent.plugins.integration]
    [INFO] Configuration loaded 0 plugin capabilities (out of 0 discovered) [agent.plugins.integration]
    [INFO] Plugin adapter integrated with function registry for AI function calling [agent.plugins.integration]
    [INFO] Registered plugin capability with scope enforcement: hello (scopes: ['api:read']) [agent.capabilities.executors]
    [INFO] Loaded plugin: hello with 1 capabilities [PluginService]
    [INFO] Plugin service initialized with 1 plugins [PluginService]
    [INFO] ✓ Initialized PluginService [agent.services.bootstrap]
    [INFO] ================================================== [agent.services.bootstrap]
    [INFO] Basic Agent v0.3.0 initialized [agent.services.bootstrap]
    [INFO] AI Agent Basic Agent Project. [agent.services.bootstrap]
    [INFO] ================================================== [agent.services.bootstrap]
    [INFO] Active Services (4):      [agent.services.bootstrap]
    [INFO]   ✓ SecurityService       [agent.services.bootstrap]
    [INFO]   ✓ MiddlewareManager     [agent.services.bootstrap]
    [INFO]   ✓ CapabilityRegistry    [agent.services.bootstrap]
    [INFO]   ✓ PluginService         [agent.services.bootstrap]
    [INFO] Enabled Features:         [agent.services.bootstrap]
    [INFO]   ✓ Security (api_key)    [agent.services.bootstrap]
    [INFO]   ✓ Capabilities (4)      [agent.services.bootstrap]
    [INFO] ================================================== [agent.services.bootstrap]
    [INFO] Loaded 1 plugins from config [agent.api.routes]
    [INFO] Plugin 0: id=hello, desc=Simple greeting plugin for testing and examples [agent.api.routes]
    [INFO] Application startup complete. [uvicorn.error]
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

??? success "Response"

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

### Agent Card

Last of all, as AgentUp follows the [A2A Specification](https://a2a.spec), you can also view your agent's card by visiting the `/agent` endpoint:

```bash
curl -s http://localhost:8000/.well-known/agent.json |jq
```

??? success "Response"

    ```json
    {
      "additionalInterfaces": null,
      "capabilities": {
        "extensions": null,
        "pushNotifications": false,
        "stateTransitionHistory": true,
        "streaming": true
      },
      "defaultInputModes": [
        "text"
      ],
      "defaultOutputModes": [
        "text"
      ],
      "description": "AI Agent Basic Agent Project.",
      "documentationUrl": null,
      "iconUrl": null,
      "name": "Basic Agent",
      "preferredTransport": null,
      "protocolVersion": "0.2.5",
      "provider": null,
      "security": [
        {
          "X-API-Key": []
        }
      ],
      "securitySchemes": {
        "X-API-Key": {
          "description": "API key for authentication",
          "in": "header",
          "name": "X-API-Key",
          "type": "apiKey"
        }
      },
      "skills": [
        {
          "description": "Simple greeting plugin for testing and examples",
          "examples": null,
          "id": "hello",
          "inputModes": [
            "text"
          ],
          "name": "Hello Plugin",
          "outputModes": [
            "text"
          ],
          "tags": [
            "hello",
            "basic",
            "example"
          ]
        }
      ],
      "supportsAuthenticatedExtendedCard": false,
      "url": "http://localhost:8000",
      "version": "0.3.0"
    }
    ```

The key points to note in the agent card, are how are plugin 'hello' is listed under `skills`, and the security scheme is defined under `securitySchemes`. This card provides a machine-readable description of your agent's capabilities and how to interact with it.
```bash

