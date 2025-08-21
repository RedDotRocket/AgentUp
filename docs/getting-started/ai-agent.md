# Create Your First AI Agent

In this section, we will create an agent that can tell us information about a system using an AI model.

Let's create a new agent project.

```{.bash }
agentup init
```

We want to grab some extra options this time.

```{.text hl_lines="10 12 13 14"}
> agentup init
──────────────────────────────────────────────────
AgentUp Agent Creator
──────────────────────────────────────────────────
Create your AI agent

? Agent name: Tools
? Description: AI Agent Tools Project.
? Version: 0.0.1
? Would you like to customize the features? Yes
? Select features to include: done (2 selections)
? Select authentication method: API Key (simple, but less secure)
? Please select an AI Provider: OpenAI
? Enable streaming responses? Yes
```

**Note:** In the above example, we use `OpenAI` as the AI provider, but you can choose any other supported provider that fits your needs.
  For example, you could use `Anthropic` or `Ollama` for local models (*shout out to the **[/r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/)** community*).

Change into our agent directory:

```{.bash }
cd tools && uv sync
```

??? "Package Managers"
    We reference **uv** a lot in AgentUp, as its what the developers of the project use, but you can use any package manager you prefer, such as pip or poetry.


### System Tools Plugin

The [agentup-systools](https://agentup.dev/packages/agentup-systools) plugin provides access to operating system tools to work with files, directories, and system information. 

It allows your agent to perform tasks such as listing directories, getting system info, and working with files.

To enable this plugin, we will need to perform two steps:

1. Download the plugin from the AgentUp plugin repository.
2. Register the plugin with our agent's configuration file.

### Step 1: Download the Plugin

AgentUp provides a plugin [repository](https://agentup.dev) where you can discover and use various plugins to extend your
agent's capabilities or contribute your own plugins. You are also welcome to use any PyPi compliant registry. The advantages
to using the AgentUp registry include:

- **Curated Plugins**: Access to a curated list of plugins specifically designed for AgentUp.
- **Security**: Enhanced security, including malware scanning and secure coding checks of plugins
- **Quarantine Mechanism**: Unverified plugins are quarantined for safety.

??? info "Plugin Management"
    AgentUp leverages Python's native **entrypoint** system for plugin installation and management.

    **Benefits of the Entrypoint System**

    - **Easy Installation**: Plugins can be managed like any standard Python package
    - **Dependency Integration**: Include plugins in your `requirements.txt` or `pyproject.toml` files
    - **Automatic Setup**: Plugins install automatically when you set up your environment
    - **Lightweight Agents**: Agents remain portable and only require configuration files plus dependency specifications
    - **Easy Sharing**: Share agents with others using just the config file and dependency requirements


To install the `sys_tools` plugin, you can use pip, uv or poetry, whichever you prefer for managing Python packages.

```{.bash .copy}
uv add agentup-systools
```

### Step 2: Agentup Plugin Command

Once installed, the plugin will be be shown as available for use:

```{.bash .copy}
agentup plugin list
```

??? success "Expected Output"
    ```{.text .no-copy}
                          Available Plugins                      
    ╭──────────────────┬──────────────────┬─────────┬───────────╮
    │ Plugin           │ Package          │ Version │  Status   │
    ├──────────────────┼──────────────────┼─────────┼───────────┤
    │ agentup_systools │ agentup-systools │  0.5.0  │ available │
    ╰──────────────────┴──────────────────┴─────────┴───────────╯
    ```

You will note `available` as a status, this means the plugin is there to be used,
but not yet activated in our agent. To activate the plugin, we need to register it in our agent's configuration file.

AgentUp makes plugin management easy and intuitive, with the `plugin` command.

Let's add our `agentup_systools` plugin.

```{.bash .copy}
agentup plugin sync
```

??? success "Expected output"
    ```{.bash .no.copy}
    > agentup plugin sync
      Synchronizing agentup.yml with installed plugins...
      Current agentup.yml has 0 configured plugins
      Found 1 installed AgentUp plugins

      Plugins to add (1):
        + agentup-systools (plugin: agentup_systools, v0.5.0)
        ✓ Added agentup-systools with 11 capabilities

      ✓ Updated agentup.yml with 1 additions and 0 removals
    ```

That's all, the `sync` command will always syncronise your agent's configuration with the installed plugins.

If however you prefer more granular control, there is also the `agentup plugin add` command, which allows you to add plugins individually.

Likewise, the `agentup plugin remove` command allows you to remove plugins from your agent's configuration.

### Step 3: Plugin configuration

Let's now look at our `agentup.yml` and how the `sys_tools` plugin is configured.

```{.yaml}
plugins:
  agentup-systools:
    capabilities:
      create_directory:
        required_scopes:
          - files:write
      delete_file:
        required_scopes:
          - files:admin
      execute_command:
        required_scopes:
          - system:admin
      file_exists:
        required_scopes:
          - files:read
      file_hash:
        required_scopes:
          - files:read
      file_info:
        required_scopes:
          - files:read
      file_read:
        required_scopes:
          - files:read
      file_write:
        required_scopes:
          - files:write
      list_directory:
        required_scopes:
          - files:read
      system_info:
        required_scopes:
          - system:read
      working_directory:
        required_scopes:
          - system:read
```

OK , a log going on, but it's pretty simple. 

| Component | Description |
|-----------|-------------|
| **plugins** | This section lists all the plugins used by the agent. |
| **capabilities** | This section lists all the capabilities provided by the plugin, along with their required scopes. |
| **required_scopes** | This section lists all the scopes required to use the capabilities. |

So in our instance we have the `agentup-systools` plugin, which provides capabilities for file and system operations.

??? tip "Discover capabilities"
    You can explore the capabilities of a plugin by using the `--capabilities` or `-c` flag with `agentup plugin list`.
    ```{.text .no-copy}
    agentup plugin list --capabilities
                              Available Plugins                      
    ╭──────────────────┬──────────────────┬─────────┬───────────╮
    │ Plugin           │ Package          │ Version │  Status   │
    ├──────────────────┼──────────────────┼─────────┼───────────┤
    │ agentup_systools │ agentup-systools │  0.5.0  │ available │
    ╰──────────────────┴──────────────────┴─────────┴───────────╯

                            Available Capabilities                         
    ╭───────────────────┬──────────────────┬─────────────┬─────────────────╮
    │ Capability        │ Plugin           │ AI Function │ Required Scopes │
    ├───────────────────┼──────────────────┼─────────────┼─────────────────┤
    │ create_directory  │ agentup_systools │      ✓      │ files:write     │
    │ delete_file       │ agentup_systools │      ✓      │ files:admin     │
    │ execute_command   │ agentup_systools │      ✓      │ system:admin    │
    │ file_exists       │ agentup_systools │      ✓      │ files:read      │
    │ file_hash         │ agentup_systools │      ✓      │ files:read      │
    │ file_info         │ agentup_systools │      ✓      │ files:read      │
    │ file_read         │ agentup_systools │      ✓      │ files:read      │
    │ file_write        │ agentup_systools │      ✓      │ files:write     │
    │ list_directory    │ agentup_systools │      ✓      │ files:read      │
    │ system_info       │ agentup_systools │      ✓      │ system:read     │
    │ working_directory │ agentup_systools │      ✓      │ system:read     │
    ╰───────────────────┴──────────────────┴─────────────┴─────────────────╯
    ```

### What are scopes?

Scopes are a way to define the permissions required to use certain capabilities within a plugin. They help ensure that only
authorized users or processes can access specific functionalities. This is what makes AgentUp unique,
other frameworks often lack this level of granularity in permission management and control, which exposes
the agent to many nasty security vulnerabilities. 

We cover scopes in more detail in the [Security](../security/scope-based-authorization.md) section.


A few things to note here:

- **provider**: This specifies the AI provider we want to use. In this case, we are using OpenAI.
- **model**: This specifies the AI model we want to use. In this case, we are using the `gpt-4o-mini` model.
- **api_key**: This specifies the API key for the AI provider. We are using an environment variable `${OPENAI_API_KEY}` to store the API key securely.
- **system_prompt**: This is the system prompt that will be used to guide the AI's behavior. It provides instructions on how the AI should respond to user requests.

### Export the API Key

If you set 'OpenAI' or 'Anthropic' as your AI provider, you'll need to export the corresponding API key as an environment variable. 

You can do this by running the following command in your terminal:

```{.bash}
export OPENAI_API_KEY="your_openai_api_key"
```

```{.bash}
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

### Test the server and plugin loading

Let's now start our agent:

```bash
agentup run
```

??? success "Expected Output"

    ```{.bash}
    2025-08-21T10:36:39 [INFO] Configuration loaded successfully [agent.services.config]
    2025-08-21T10:36:39 [INFO] Security mode: configured with 3 allowed plugins [agent.plugins.manager]
    2025-08-21T10:36:39 [INFO] Registered plugin 'agentup_systools' with 11 capabilities [agent.plugins.manager]
    2025-08-21T10:36:39 [INFO] Registered plugin 'agentup_systools' with 11 capabilities [agent.plugins.manager]
    2025-08-21T10:36:39 [INFO] Started server process [25455] [uvicorn.error]
    2025-08-21T10:36:39 [INFO] Waiting for application startup. [uvicorn.error]
    2025-08-21T10:36:39 [INFO] Starting service initialization [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Integrating plugins with capabilities system [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Starting plugin integration with capabilities system [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Registered plugin 'agentup_systools' with 11 capabilities [agent.plugins.manager]
    2025-08-21T10:36:39 [INFO] Registered plugin 'agentup_systools' with 11 capabilities [agent.plugins.manager]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'create_directory' with scopes: ['files:write'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'delete_file' with scopes: ['files:admin'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'execute_command' with scopes: ['system:admin'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'file_exists' with scopes: ['files:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'file_hash' with scopes: ['files:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'file_info' with scopes: ['files:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'file_read' with scopes: ['files:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'file_write' with scopes: ['files:write'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'list_directory' with scopes: ['files:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'system_info' with scopes: ['system:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Capability Registered: 'working_directory' with scopes: ['system:read'] [agent.plugins.integration]
    2025-08-21T10:36:39 [INFO] Registered 11 capabilities from plugins [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Initializing security service [SecurityService]
    2025-08-21T10:36:39 [INFO] Security authentication manager initialized [agent.security.unified_auth] enabled=True providers=['api_key']
    2025-08-21T10:36:39 [INFO] Security manager initialized - enabled: True, primary auth: api_key [agent.security.manager]
    2025-08-21T10:36:39 [INFO] Security enabled with api_key authentication [SecurityService]
    2025-08-21T10:36:39 [INFO] ✓ Initialized SecurityService [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Initializing middleware manager [MiddlewareManager]
    2025-08-21T10:36:39 [INFO] Middleware manager initialized with 4 global middleware [MiddlewareManager]
    2025-08-21T10:36:39 [INFO] ✓ Initialized MiddlewareManager [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Capability registry initialized with 3 capabilities [BuiltinCapabilityRegistry]
    2025-08-21T10:36:39 [INFO] ✓ Initialized BuiltinCapabilityRegistry [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Initializing push notification service [PushNotificationService]
    2025-08-21T10:36:39 [INFO] Push notification service initialized with memory backend [PushNotificationService]
    2025-08-21T10:36:39 [INFO] ✓ Initialized PushNotificationService [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] ================================================== [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Agent v0.5.1 initialized  [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] AgentUp Agent   [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] ================================================== [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Active Services (4): [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO]   ✓ SecurityService  [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO]   ✓ MiddlewareManager[agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO]   ✓ BuiltinCapabilityRegistry [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO]   ✓ PushNotificationService [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Enabled Features:    [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO]   ✓ Security (api_key)    [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] ==================== [agent.services.bootstrap]
    2025-08-21T10:36:39 [INFO] Registered 11 AI functions from plugins [agent.core.dispatcher]
    2025-08-21T10:36:39 [INFO] Application startup complete. [uvicorn.error]
    ```

### Test the AI Agent

We now can engage with LLM enabled agent and ask for some information about the agents system,
but before we do, we need to get the API key

From within your `agentup.yml`, retrieve the API key:

```yaml
security:
  enabled: true
  auth:
    api_key:
      header_name: X-API-Key
      location: header
      keys:
        - key: your_key
```

And lets send a message to the Agent:

```bash
curl -s -X POST http://localhost:8000/ \
 -H "Content-Type: application/json" \
 -H "X-API-Key: your_key" \
 -d '{
   "jsonrpc": "2.0",
   "method": "message/send",
   "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "provide the system information"}],
        "messageId": "msg-001",
        "kind": "message"
      }
        },
        "id": "req-001"
  }' | jq '.result.artifacts[].parts[]'
```

!!! failure "Woops!"
    ```json
    {
      "kind": "text",
      "metadata": null,
      "text": "I'm unable to access system information directly. However, if you let me know what specific information you're looking for, I can guide you on how to find it or help you with related questions!"
    }
    ```

Something went wrong, let's check the server logs. We were hoping that the Agent would use the `system_info` capability, but it seems that the request was not properly authorized.

```{.bash .wrap}
2025-08-21T10:47:18 [WARNING] Security event [security.audit] action=execute details={'required_scopes_count': 1} event_type=function_access_denied resource=system_info risk_level=low success=False user_id=user_1318
```

So here we have the `system_info` capability was denied!

Let's check what we need:

```{.bash .no-copy hl_lines="2"}
uv run agentup plugin list -c | grep system_info
│ system_info       │ agentup_systools │      ✓      │ system:read     │
```

We need to assign that scope to our key! Let's head back over to `agentup.yml` and make the change by adding a scope entry grant `system:read` to our API key.

```{.yaml .no-copy hl_lines="11"}
security:
  enabled: true
  auth:
    api_key:
      header_name: X-API-Key
      location: header
      keys:
        - key: your-key
          scopes:
            - files:read
            - system:read
```

Restart your server, and try again. You should now see your system information instead:

??? sucesss "Expected Output"

    ```{.json}
     "parts": [
    {
      "kind": "text",
      "metadata": null,
      "text": "Here's the system information:\n\n- **Platform:** Darwin\n- **Platform Release:** 24.5.0\n- **Platform Version:** Darwin Kernel Version 24.5.0 (Tue Apr 22 19:54:25 PDT 2025; root:xnu-11417.121.6~2/RELEASE_ARM64_T6020)\n- **Architecture:** arm64\n- **Processor:** arm\n- **Hostname:** lhinds-mbp\n- **Python Version:** 3.13.2\n- **Working Directory:** /Users/lhinds/dev/agentup-ws/rubbish/tools\n- **User:** lhinds\n\nIf you need any more details or have further questions, feel free to ask!"
    }
    ```

It's a wrap! You just built your first AI agent that can respond to system information requests using
the `sys_tools` plugin. You can now extend this agent further by adding more plugins and
capabilities as needed.

From here you can explore the other capabilities of the `sys_tools` plugin, such as listing directories
or calculating file hashes, and integrate them into your AI agent.

The really ambitious could even look at building a coding agent! 
