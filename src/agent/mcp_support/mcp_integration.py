from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _extract_tool_scopes_from_servers(servers_config: list[Any]) -> dict[str, list[str]]:
    """Extract and merge tool_scopes from all server configurations.

    Handles both Pydantic models and dict-like objects.

    Args:
        servers_config: List of server configuration objects

    Returns:
        Dict mapping tool names to required scopes
    """
    tool_scopes = {}
    for server_config in servers_config:
        # Handle Pydantic model (use attribute access, not .get())
        if hasattr(server_config, "tool_scopes"):
            server_tool_scopes = server_config.tool_scopes or {}
        else:
            # Fallback for dict-like objects
            server_tool_scopes = server_config.get("tool_scopes", {}) if hasattr(server_config, "get") else {}
        tool_scopes.update(server_tool_scopes)
    return tool_scopes


async def initialize_mcp_integration(config: dict[str, Any]) -> None:
    mcp_config = config.get("mcp", {})

    if not mcp_config.get("enabled", False):
        logger.info("MCP integration disabled in configuration")
        return

    logger.debug("Initializing MCP service")

    # Get service registry
    from agent.services import get_services

    services = get_services()
    client_initialized = False
    server_initialized = False

    # Initialize MCP client if enabled (using flattened config structure)
    if mcp_config.get("client_enabled", False):
        logger.debug("Initializing MCP client")
        await _initialize_mcp_client(services, mcp_config)

        # Check if client initialization was successful
        mcp_client = services.get_mcp_client()
        if mcp_client and mcp_client.is_initialized and len(mcp_client.list_servers()) > 0:
            client_initialized = True

    # Initialize MCP server if enabled (using flattened config structure)
    if mcp_config.get("server_enabled", False):
        logger.debug("Initializing MCP server")
        await _initialize_mcp_server(services, mcp_config)

        # Check if server initialization was successful
        mcp_server = services.get_mcp_server()
        if mcp_server:
            server_initialized = True

    # Report overall integration status
    components_enabled = []
    if mcp_config.get("client_enabled", False):
        components_enabled.append(f"client ({'✓' if client_initialized else '✗'})")
    if mcp_config.get("server_enabled", False):
        components_enabled.append(f"server ({'✓' if server_initialized else '✗'})")

    if components_enabled:
        components_status = ", ".join(components_enabled)

        # Create structured logging context
        log_context = {
            "client_enabled": mcp_config.get("client_enabled", False),
            "client_initialized": client_initialized,
            "server_enabled": mcp_config.get("server_enabled", False),
            "server_initialized": server_initialized,
        }

        # Add client details if applicable
        if mcp_config.get("client_enabled", False):
            mcp_client = services.get_mcp_client()
            if mcp_client:
                log_context.update(
                    {
                        "connected_servers": len(mcp_client.list_servers()),
                        "available_tools": len(mcp_client.list_tools()),
                        "available_resources": len(mcp_client.list_resources()),
                    }
                )

        if (not mcp_config.get("client_enabled", False) or client_initialized) and (
            not mcp_config.get("server_enabled", False) or server_initialized
        ):
            logger.debug(f"MCP integration initialization complete: {components_status}", extra=log_context)
        else:
            logger.debug(f"MCP integration partially initialized: {components_status}", extra=log_context)
    else:
        logger.warning(
            "MCP integration enabled but no components configured",
            extra={"client_enabled": False, "server_enabled": False},
        )


async def _initialize_mcp_client(services, mcp_config: dict[str, Any]) -> None:
    """Initialize unified MCP client with support for all transport types."""
    servers = mcp_config.get("servers", [])

    if not servers:
        logger.info("No MCP servers configured")
        return

    from .mcp_client import MCPClientService

    try:
        # Create unified MCP client with all configured servers
        mcp_client = MCPClientService("mcp_client", mcp_config)
        await mcp_client.initialize()

        # Register with service registry
        services._services["mcp_client"] = mcp_client
        logger.debug("Registered unified MCP client with service registry")

        # Register MCP tools with AI orchestrator
        try:
            from agent.core.dispatcher import get_function_registry

            registry = get_function_registry()

            available_tools = await mcp_client.get_available_tools()
            if not len(available_tools):
                logger.warning("No MCP tools available across configured transports")
            else:
                # Log available tools for debugging
                tool_names = [tool.get("name", "unknown") for tool in available_tools]
                logger.debug(f"MCP tools available across all transports: {', '.join(tool_names)}")

            if available_tools:
                # Register MCP tools with scope enforcement
                await _register_mcp_tools_as_capabilities(mcp_client, available_tools, servers)
                # Also register with function registry for AI integration
                await _register_mcp_tools_with_scopes(registry, mcp_client, available_tools, servers)

                tool_names = [tool.get("name", "unknown") for tool in available_tools]
                logger.info(f"Registered MCP tools: {', '.join(tool_names)}")

        except Exception as e:
            logger.error(f"Failed to register MCP tools: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize unified MCP client: {e}")
        # Still register the failed client so we don't break the service registry
        if "mcp_client" in locals():
            services._services["mcp_client"] = mcp_client

    # The MCP client will now log its own detailed status during initialization
    # We don't need to duplicate that logging here


async def _initialize_mcp_server(services, mcp_config: dict[str, Any]) -> None:
    try:
        from .mcp_server import MCPServerComponent
    except ImportError as e:
        logger.error(f"Failed to import MCPServerComponent: {e}")
        return

    try:
        # Create and register MCP server
        mcp_server = MCPServerComponent("mcp_server", mcp_config)
        await mcp_server.initialize()

        # Register with service registry
        services._services["mcp_server"] = mcp_server
        logger.info("Registered MCP server with service registry")
        # Expose AgentUp handlers as MCP tools if enabled
        if mcp_config.get("expose_handlers", False):
            await _expose_handlers_as_mcp_tools(mcp_server)

        logger.info("MCP server initialized and ready to expose agent tools")

        # Start MCP server in background if port is specified
        port = mcp_config.get("server_port")
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
        from agent.capabilities.manager import register_mcp_tool_as_capability

        # Extract tool scopes from server configuration
        tool_scopes = _extract_tool_scopes_from_servers(servers_config)

        # Register each tool as a capability with scope enforcement
        for tool in available_tools:
            # tool is a dict from MCP client, not a Pydantic model
            tool_name = tool["name"]  # Clean tool name (no colon prefix)
            server_name = tool["server"]  # Server name stored directly in tool data
            # Use prefixed tool name for scope lookup (server_name:tool_name)
            prefixed_tool_name = f"{server_name}:{tool_name}"
            required_scopes = tool_scopes.get(prefixed_tool_name)  # tool_scopes is a dict, .get() is correct

            # SECURITY: Require explicit scope configuration
            if required_scopes is None:
                logger.error(f"MCP tool '{prefixed_tool_name}' requires explicit scope configuration in agentup.yml")
                raise ValueError(
                    f"MCP tool '{prefixed_tool_name}' requires explicit scope configuration. "
                    f"Add 'tool_scopes' configuration with required scopes for this tool using the format '{server_name}:{tool_name}'."
                )

            # Clean tool names no longer need colon sanitization, just ensure valid identifier
            capability_name = tool_name.replace("-", "_")  # Only replace hyphens for valid Python identifiers

            # Register with clean name, server name, and pass the tool data for rich information
            await register_mcp_tool_as_capability(capability_name, mcp_client, required_scopes, server_name, tool)
            logger.debug(
                f"Registered MCP tool as capability: '{tool_name}' -> '{capability_name}' from server '{server_name}' with scopes: {required_scopes}"
            )

    except Exception as e:
        logger.error(f"Failed to register MCP tools as capabilities: {e}")


async def _register_mcp_tools_with_scopes(registry, mcp_client, available_tools, servers_config):
    try:
        # Extract tool scopes from server configuration
        tool_scopes = _extract_tool_scopes_from_servers(servers_config)

        # Register each tool with scope enforcement
        for tool in available_tools:
            original_tool_name = tool.get("name", "unknown")
            server_name = tool.get("server", "unknown")
            # Use prefixed tool name for scope lookup (server_name:tool_name)
            prefixed_tool_name = f"{server_name}:{original_tool_name}"
            required_scopes = tool_scopes.get(prefixed_tool_name)

            # SECURITY: Require explicit scope configuration - no automatic assignment
            if required_scopes is None:
                logger.error(f"MCP tool '{prefixed_tool_name}' requires explicit scope configuration in agentup.yml")
                raise ValueError(
                    f"MCP tool '{prefixed_tool_name}' requires explicit scope configuration. "
                    f"Add 'tool_scopes' configuration with required scopes for this tool using the format '{server_name}:{original_tool_name}'."
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

        # Register the MCP client after registering all tools
        await registry.register_mcp_client(mcp_client)
        logger.debug("Registered MCP client with function registry")

    except Exception as e:
        logger.error(f"Failed to register MCP tools with scope enforcement: {e}")
        # DO NOT fallback to registration without scope enforcement for security

        # Always register the MCP client regardless of tool registration success/failure
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
