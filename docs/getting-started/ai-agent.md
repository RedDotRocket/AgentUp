# Create Your First AI Agent

Now we should be able to make our agent AI capable by adding an AI provider (openAI) and a plugin that can provide more complex interactions. In this section, we will create a basic agent that can respond to simple greetings using a plugin.


### System Tools Plugin

The `sys_tools` plugin provides access to operating system tools to work with files, directories, and system information. It allows your agent to perform tasks like listing directories, getting system info, and calculating file hashes.

To enable this plugin, we will need to perform two steps:
1. Download the plugin from the AgentUp plugin repository.
2. Register the plugin with our agent's configuration file.

### Step 1: Download the Plugin

AgentUp provides a centralized plugin repository `registry.agentup.dev` where you can discover and use various plugins to extend your agent's capabilities. The **sys_tools** plugin, is one such plugin that is available through the AgentUp registry.

!!! info "Plugin Management"
    AgentUp leverages Python's native **entrypoint** system for plugin installation and management.

    **Benefits of the Entrypoint System**

    - **Easy Installation**: Plugins can be managed like any standard Python package
    - **Dependency Integration**: Include plugins in your `requirements.txt` or `pyproject.toml` files
    - **Automatic Setup**: Plugins install automatically when you set up your environment
    - **Lightweight Agents**: Agents remain portable and only require configuration files plus dependency specifications
    - **Easy Sharing**: Share agents with others using just the config file and dependency requirements


To install the `sys_tools` plugin, you can use pip, uv or poetry, whichever you prefer for managing Python packages.

The only difference is that we need to set a value for the tool to use our registry.

??? note "Offical PyPi registry"
    The existing PyPi registry can also be used for hosting plugins! The reason
    we elected to create our own registry was two fold:
    1. We prefer not to flood the PyPi registry with plugins and have maintainance
    fall on that awesome community.
    2. We wanted to build in some extra security features, such as secure coding checks,
    malware and vulnerability scanning + a quarantine mechanism for unverified plugins.

**Configure pip**

Add AgentUp Registry to your pip configuration:

```plaintext
[global]
extra-index-url = https://registry.agentup.dev/simple
```

**requirements.txt**

```plaintext
--extra-index-url https://registry.agentup.dev/simple
--trusted-host agentup.dev

agentup-plugin==1.0.0
```

**Pass in the argument**

```
pip install sys-tools --index-url https://registry.agentup.dev/simple
```

### Step 2: Agentup Plugin Command

Once installed, the plugin will be be shown as available for use:

```bash
agentup plugin list
```

```bash
    Loaded Plugins
╭──────────────┬──────────────────┬─────────┬────────╮
│ Plugin  │ Name   │ Version │ Status │
├──────────────┼──────────────────┼─────────┼────────┤
│ sys_tools    │ File Read   │  0.2.2  │ loaded │
╰──────────────┴──────────────────┴─────────┴────────╯
```

### Step 3: Register the Plugin

To register the `sys_tools` plugin, we will modify our agent's configuration file (`agent_config.yaml`) to include the plugin and its capabilities.


```yaml
plugins:
  - plugin_id: sys_tools
    name: System Tools
    description: Plugin to check scopes for API access
    input_mode: text
    output_mode: text
    capabilities:
 - capability_id: list_directory
   required_scopes: ["files:read"]
   enabled: true
 - capability_id: system_info
   enabled: true 
   required_scopes: ["system:read"]
 - capability_id: file_hash
   required_scopes: ["files:read"]
   enabled: true 
```

### Create an AI Provider

To create an AI provider, we will modify our agent's configuration file (`agent_config.yaml`) to include the AI provider and its capabilities.

```yaml
ai_provider:
    provider: openai
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}

ai:
  enabled: true
  system_prompt: |
    You are a helpful AI assistant

    Your role:
    - Understand user requests naturally
    - Provide helpful, accurate responses
    - Maintain a friendly and professional tone
    - Use available functions when appropriate
    - Keep responses concise and relevant

    Always be helpful, accurate, and maintain context in conversations.
```

A few things to note here:

- **provider**: This specifies the AI provider we want to use. In this case, we are using OpenAI.
- **model**: This specifies the AI model we want to use. In this case, we are using the `gpt-4o-mini` model.
- **api_key**: This specifies the API key for the AI provider. We are using an environment variable `${OPENAI_API_KEY}` to store the API key securely.
- **system_prompt**: This is the system prompt that will be used to guide the AI's behavior. It provides instructions on how the AI should respond to user requests.

### Export the API Key

Before we can use the AI provider, we need to export the OpenAI API key as an environment variable. You can do this by running the following command in your terminal:

```bash
export OPENAI_API_KEY="your_openai_api_key"
```

### Test the server and plugin loading

Let's now restart our agent to load the new configuration:

Perform `ctrl + c` to stop the agent, then run:

```bash
agentup agent serve
```

We should now seee the plugin being loaded:

```bash
[INFO] Discovered plugin 'sys_tools' with 11 capabilities
[INFO] Registered plugin capability with scope enforcement: list_directory (scopes: ['files:read'])
[INFO] Registered plugin capability with scope enforcement: system_info (scopes: ['system:read'])
[INFO] Registered plugin capability with scope enforcement: file_hash (scopes: ['files:read'])
[INFO] Configuration loaded 3 plugin capabilities (out of 11 discovered)
[INFO] Registered AI function 'list_directory' from capability 'list_directory'
[INFO] Registered AI function 'system_info' from capability 'system_info'
[INFO] Registered AI function 'file_hash' from capability 'file_hash'
[INFO] Plugin adapter integrated with function registry for AI function calling
```

All good! Now we have the `sys_tools` plugin loaded and ready to use. But first, we need to create an AI provider that can use this plugin.

### Test the AI Agent

```bash
curl -s -X POST http://localhost:8000/ \
 -H "Content-Type: application/json" \
 -H "X-API-Key: 24vgyiyNuzvPdtRG5R80YR4_eKXC9dk0" \
 -d '{
   "jsonrpc": "2.0",
   "method": "message/send",
   "params": {
"message": {
  "role": "user",
  "parts": [{"kind": "text", "text": "provide the system information"}],
  "messageId": "msg-001",,
  "kind": "message"
}
   },
   "id": "req-001"
 }' | jq -r '.result.artifacts[].parts[].text' | jq
```

??? success "Response"

    ```json
    {
      "success": true,
      "data": {
        "platform": "Darwin",
        "platform_release": "24.5.0",
        "platform_version": "Darwin Kernel Version 24.5.0: Tue Apr 22 19:54:25 PDT 2025; root:xnu-11417.121.6~2/RELEASE_ARM64_T6020",
        "architecture": "arm64",
        "processor": "arm",
        "hostname": "lhinds-mbp",
        "python_version": "3.11.11",
        "working_directory": "/Users/lhinds/basic_agent",
        "user": "lhinds"
      },
      "operation": "system_info"
    }
    ```

Let's also check the logs in the server console to see the scope enforcement and
the AI function call:

```bash hl_lines="2 4 9 11"
[INFO] SCOPE CHECK: Checking capability 'system_info' with required scopes: ['system:read']
[INFO] Checking if user has scope 'system:read'
[INFO] Expanding scopes: initial=['system:admin'], hierarchy_size=9, hierarchy={'admin': ['*'], 'manager': ['files:admin', 'system:read', 'web:search', 'image:read'], 'developer': ['files:write', 'system:read', 'web:search'], 'analyst': ['files:read', 'web:search', 'image:read'], 'readonly': ['files:read'], 'files:admin': ['files:write', 'files:read'], 'files:write': ['files:read'], 'system:admin': ['system:write', 'system:read'], 'system:write': ['system:read']}
[INFO] GRANTED built-in function 'system_info' (required: ['system:read'])
[INFO] AI tool filtering completed: 1 tools available for user with scopes ['system:admin']
[INFO] Tools granted to user: ['system_info']
[INFO] Using scope-filtered tools for user with scopes: ['system:admin']
[INFO] Available function schemas for AI: 1 functions
[INFO] Available functions for AI: ['system_info']
[INFO] HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK" 
[INFO] LLM selected function(s): system_info
```

It's a wrap! You just built your first AI agent that can respond to system information requests using
the `sys_tools` plugin. You can now extend this agent further by adding more plugins and
capabilities as needed.

From here you can explore the other capabilities of the `sys_tools` plugin, such as listing directories
or calculating file hashes, and integrate them into your AI agent.

The really ambitious could even look at building a coding agent! 