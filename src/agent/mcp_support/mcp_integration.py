import logging
from typing import Any, dict

logger = logging.getLogger(__name__)

try:
    import mcp  # noqa: F401
    from mcp import ClientSession, StdioServerParameters  # noqa: F401
    from mcp.client.stdio import stdio_client  # noqa: F401

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not available. Install with: pip install mcp")


async def initialize_mcp_integration(config: dict[str, Any]) -> None:
    """Initialize MCP client and server integration."""
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not available. MCP integration disabled.")
        return

    mcp_config = config.get("mcp", {})

    if not mcp_config.get("enabled", False):
        logger.info("MCP integration disabled in configuration")
        return

    # Get service registry
    from ..services import get_services

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
    """Initialize MCP client service."""
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not available. Cannot initialize MCP client.")
        return

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
                from ..function_dispatcher import get_function_registry

                registry = get_function_registry()

                available_tools = await http_client.get_available_tools()
                logger.info(f"HTTP MCP tools available: {len(available_tools)}")

                if available_tools:
                    await registry.register_mcp_client(http_client)
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
                from ..function_dispatcher import get_function_registry

                registry = get_function_registry()

                available_tools = await stdio_client.get_available_tools()
                logger.info(f"Stdio MCP tools available: {len(available_tools)}")

                if available_tools:
                    await registry.register_mcp_client(stdio_client)
                    tool_names = [tool.get("name", "unknown") for tool in available_tools]
                    logger.info(f"Stdio MCP tool names: {', '.join(tool_names)}")

            except Exception as e:
                logger.error(f"Failed to register stdio MCP tools: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize stdio MCP client: {e}")

    total_clients = len([1 for k in services._services.keys() if "mcp" in k and "client" in k])
    logger.info(f"MCP clients initialized: {total_clients}")


async def _initialize_mcp_server(services, server_config: dict[str, Any]) -> None:
    """Initialize MCP server component."""
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not available. Cannot initialize MCP server.")
        return

    from .mcp_server import MCPServerComponent

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

        logger.info("MCP server initialized and ready to expose {{ project_name }} tools")

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
    """Expose AgentUp handlers as MCP tools."""
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not available. Cannot expose handlers as MCP tools.")
        return

    try:
        # Get registered handlers from the function registry
        from ..function_dispatcher import get_function_registry

        registry = get_function_registry()

        # Register each handler as an MCP tool
        successful_registrations = 0
        for function_name in registry.list_functions():
            if not registry.is_mcp_tool(function_name):  # Only register local functions
                handler = registry.get_handler(function_name)
                schema = registry._functions.get(function_name, {})

                if handler and schema:
                    logger.info(f"Registering MCP tool: {function_name}")
                    try:
                        logger.info(f"Attempting to register MCP tool: {function_name}")
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


async def _start_mcp_server_background(mcp_server, port: int) -> None:
    """Start MCP server in background task."""
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not available. Cannot start MCP server.")
        return

    try:
        await mcp_server.start_server(port=port)
    except Exception as e:
        logger.error(f"MCP server failed to start on port {port}: {e}")


async def shutdown_mcp_integration() -> None:
    """Shutdown MCP client and server."""
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not available. Cannot shutdown MCP integration.")
        return

    from ..services import get_services

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
