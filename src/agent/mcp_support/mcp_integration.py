from typing import Any

import structlog
from mcp import ClientSession, StdioServerParameters  # noqa: F401
from mcp.client.stdio import stdio_client  # noqa: F401

logger = structlog.get_logger(__name__)


async def initialize_mcp_integration(config: dict[str, Any]) -> None:
    mcp_config = config.get("mcp", {})

    if not mcp_config.get("enabled", False):
        logger.info("MCP integration disabled in configuration")
        return

    # Get service registry
    from agent.services import get_services

    services = get_services()

    # Initialize MCP client if enabled
    client_config = mcp_config.get("client", {})
    if client_config.get("enabled", False):
        logger.info("Initializing MCP client")
        await _initialize_mcp_client(services, client_config)

    # Initialize MCP server if enabled
    server_config = mcp_config.get("server", {})
    if server_config.get("enabled", False):
        logger.info("Initializing MCP server")
        await _initialize_mcp_server(services, server_config)


async def _initialize_mcp_client(services, client_config: dict[str, Any]) -> None:
    # Check if we have HTTP servers configured
    servers = client_config.get("servers", [])
    http_servers = [s for s in servers if s.get("type") == "http"]
    stdio_servers = [s for s in servers if s.get("type") != "http"]

    # Initialize HTTP client for agent-to-agent connections
    if http_servers:
        from .mcp_http_client import MCPHTTPClientService

        try:
            http_client = MCPHTTPClientService("mcp_http_client", client_config)
            await http_client.initialize()

            # Register with service registry
            services._services["mcp_http_client"] = http_client
            logger.info("Registered MCP HTTP client with service registry")

            # Register HTTP MCP tools with AI orchestrator
            try:
                from agent.core.dispatcher import get_function_registry

                registry = get_function_registry()

                available_tools = await http_client.get_available_tools()
                logger.info(f"HTTP MCP tools available: {len(available_tools)}")

                if available_tools:
                    # Register MCP tools with scope enforcement using new design pattern
                    await _register_mcp_tools_as_capabilities(http_client, available_tools, http_servers)
                    # Also register with function registry for AI integration
                    await _register_mcp_tools_with_scopes(registry, http_client, available_tools, http_servers)
                    tool_names = [tool.get("name", "unknown") for tool in available_tools]
                    logger.info(f"HTTP MCP tool names: {', '.join(tool_names)}")

            except Exception as e:
                logger.error(f"Failed to register HTTP MCP tools: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize HTTP MCP client: {e}")

    # Initialize stdio client for other servers (filesystem, etc.)
    if stdio_servers:
        from .mcp_client import MCPClientService

        try:
            # Create config with only stdio servers
            stdio_config = client_config.copy()
            stdio_config["servers"] = stdio_servers

            stdio_client = MCPClientService("mcp_stdio_client", stdio_config)
            await stdio_client.initialize()

            # Register with service registry
            services._services["mcp_stdio_client"] = stdio_client
            logger.info("Registered MCP stdio client with service registry")
            # Register stdio MCP tools with function dispatcher
            try:
                from agent.core.dispatcher import get_function_registry

                registry = get_function_registry()

                available_tools = await stdio_client.get_available_tools()
                logger.info(f"Stdio MCP tools available: {len(available_tools)}")

                if available_tools:
                    # Register MCP tools with scope enforcement using new design pattern
                    await _register_mcp_tools_as_capabilities(stdio_client, available_tools, stdio_servers)
                    # Also register with function registry for AI integration
                    await _register_mcp_tools_with_scopes(registry, stdio_client, available_tools, stdio_servers)
                    tool_names = [tool.get("name", "unknown") for tool in available_tools]
                    logger.info(f"Stdio MCP tool names: {', '.join(tool_names)}")

            except Exception as e:
                logger.error(f"Failed to register stdio MCP tools: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize stdio MCP client: {e}")

    total_clients = len([1 for k in services._services.keys() if "mcp" in k and "client" in k])
    logger.info(f"MCP clients initialized: {total_clients}")


async def _initialize_mcp_server(services, server_config: dict[str, Any]) -> None:
    try:
        from .mcp_server import MCPServerComponent
    except ImportError as e:
        logger.error(f"Failed to import MCPServerComponent: {e}")
        return

    try:
        # Create and register MCP server
        mcp_server = MCPServerComponent("mcp_server", server_config)
        await mcp_server.initialize()

        # Register with service registry
        services._services["mcp_server"] = mcp_server
        logger.info("Registered MCP server with service registry")
        # Expose AgentUp handlers as MCP tools if enabled
        if server_config.get("expose_handlers", False):
            await _expose_handlers_as_mcp_tools(mcp_server)

        logger.info("MCP server initialized and ready to expose agent tools")

        # Start MCP server in background if port is specified
        port = server_config.get("port")
        if port:
            logger.warning(
                f"Stdio MCP server on port {port} is not supported within FastAPI. Use HTTP MCP endpoint at /mcp instead."
            )
            # Disabled due to asyncio conflict with FastAPI
            # mcp_server._server_task = asyncio.create_task(_start_mcp_server_background(mcp_server, port))

    except Exception as e:
        logger.error(f"Failed to initialize MCP server: {e}")


async def _expose_handlers_as_mcp_tools(mcp_server) -> None:
    try:
        # Get registered handlers from the function registry
        from agent.core.dispatcher import get_function_registry

        registry = get_function_registry()

        # Register each handler as an MCP tool
        successful_registrations = 0
        for function_name in registry.list_functions():
            if not registry.is_mcp_tool(function_name):  # Only register local functions
                handler = registry.get_handler(function_name)
                schema = registry._functions.get(function_name, {})

                if handler and schema:
                    try:
                        logger.debug(f"Attempting to register MCP tool: {function_name}")
                        mcp_server.register_handler_as_tool(function_name, handler, schema)
                        successful_registrations += 1
                        logger.debug(f"Successfully registered MCP tool: {function_name}")
                    except Exception as e:
                        if "kwargs" in str(e):
                            logger.warning(
                                f"Skipping function '{function_name}' - functions with **kwargs are not supported as MCP tools"
                            )
                        else:
                            logger.warning(f"Failed to register MCP tool '{function_name}': {e}")

        logger.info(
            f"Exposed {successful_registrations} handlers as MCP tools (out of {len(registry.list_functions())} total)"
        )

    except Exception as e:
        logger.error(f"Failed to expose handlers as MCP tools: {e}")


async def _register_mcp_tools_as_capabilities(mcp_client, available_tools, servers_config):
    try:
        from agent.capabilities.executors import register_mcp_tool_as_capability

        # Extract tool scopes from server configuration
        tool_scopes = {}
        for server_config in servers_config:
            server_tool_scopes = server_config.get("tool_scopes", {})
            tool_scopes.update(server_tool_scopes)

        # Register each tool as a capability with scope enforcement
        for tool in available_tools:
            original_tool_name = tool.get("name", "unknown")
            required_scopes = tool_scopes.get(original_tool_name)

            # SECURITY: Require explicit scope configuration
            if required_scopes is None:
                logger.error(f"MCP tool '{original_tool_name}' requires explicit scope configuration in agentup.yml")
                raise ValueError(
                    f"MCP tool '{original_tool_name}' requires explicit scope configuration. "
                    f"Add 'tool_scopes' configuration with required scopes for this tool."
                )

            # Convert MCP tool names to valid capability names (replace colons with underscores)
            sanitized_tool_name = original_tool_name.replace(":", "_")

            # Register using the design pattern with sanitized name
            register_mcp_tool_as_capability(sanitized_tool_name, mcp_client, required_scopes)
            logger.debug(
                f"Registered MCP tool as capability: '{original_tool_name}' -> '{sanitized_tool_name}' with scopes: {required_scopes}"
            )

    except Exception as e:
        logger.error(f"Failed to register MCP tools as capabilities: {e}")


async def _register_mcp_tools_with_scopes(registry, mcp_client, available_tools, servers_config):
    try:
        # Extract tool scopes from server configuration
        tool_scopes = {}
        for server_config in servers_config:
            server_tool_scopes = server_config.get("tool_scopes", {})
            tool_scopes.update(server_tool_scopes)

        # Register each tool with scope enforcement
        for tool in available_tools:
            original_tool_name = tool.get("name", "unknown")
            required_scopes = tool_scopes.get(original_tool_name)

            # SECURITY: Require explicit scope configuration - no automatic assignment
            if required_scopes is None:
                logger.error(f"MCP tool '{original_tool_name}' requires explicit scope configuration in agentup.yml")
                raise ValueError(
                    f"MCP tool '{original_tool_name}' requires explicit scope configuration. "
                    f"Add 'tool_scopes' configuration with required scopes for this tool."
                )

            # Convert MCP tool names to valid function names (replace colons with underscores)
            sanitized_tool_name = original_tool_name.replace(":", "_")

            # Create scope-enforced wrapper for the MCP tool
            def create_mcp_tool_wrapper(client, original_name, sanitized_name, scopes):
                async def scope_enforced_mcp_tool(*args, **kwargs):
                    # Get current authentication context
                    from agent.security.context import create_capability_context, get_current_auth

                    auth_result = get_current_auth()
                    if auth_result:
                        # Create a mock task for context creation
                        from types import SimpleNamespace

                        mock_task = SimpleNamespace()
                        mock_task.id = f"mcp-{sanitized_name}"

                        context = create_capability_context(mock_task, auth_result)

                        # Check required scopes
                        for scope in scopes:
                            if not context.has_scope(scope):
                                raise PermissionError(f"MCP tool {sanitized_name} requires scope: {scope}")

                    # All scopes passed, call the MCP tool with original name
                    return await client.call_tool(original_name, *args, **kwargs)

                return scope_enforced_mcp_tool

            # Wrap the tool with scope enforcement
            wrapped_tool = create_mcp_tool_wrapper(mcp_client, original_tool_name, sanitized_tool_name, required_scopes)

            # Update tool schema to use sanitized name
            sanitized_tool = tool.copy()
            sanitized_tool["name"] = sanitized_tool_name
            sanitized_tool["original_name"] = original_tool_name

            # Register the wrapped tool with the registry using sanitized name
            await registry.register_mcp_tool(sanitized_tool_name, wrapped_tool, sanitized_tool)
            logger.debug(
                f"Registered MCP tool '{original_tool_name}' -> '{sanitized_tool_name}' with scope enforcement: {required_scopes}"
            )

    except Exception as e:
        logger.error(f"Failed to register MCP tools with scope enforcement: {e}")
        # DO NOT fallback to registration without scope enforcement for security
        # Instead, register with dispatcher only (which uses sanitized names)
        await registry.register_mcp_client(mcp_client)


async def _start_mcp_server_background(mcp_server, port: int) -> None:
    try:
        await mcp_server.start_server(port=port)
    except Exception as e:
        logger.error(f"MCP server failed to start on port {port}: {e}")


async def shutdown_mcp_integration() -> None:
    from agent.services import get_services

    services = get_services()

    # Close MCP client
    mcp_client = services.get_mcp_client()
    if mcp_client:
        await mcp_client.close()
        logger.info("MCP client shut down")

    # Close MCP server
    mcp_server = services.get_mcp_server()
    if mcp_server:
        await mcp_server.close()
        logger.info("MCP server shut down")
