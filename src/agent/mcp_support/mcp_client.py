from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MCPClientService:
    """MCP client service for connecting to external MCP servers."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self._servers: dict[str, Any] = {}
        self._available_tools: dict[str, dict[str, Any]] = {}
        self._available_resources: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize MCP client and connect to configured servers."""

        servers_config = self.config.get("servers", [])

        for server_config in servers_config:
            try:
                await self._connect_to_server(server_config)
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {server_config.get('name', 'unknown')}: {e}")

        self._initialized = True
        logger.info(f"MCP client initialized with {len(self._servers)} servers")

    async def _connect_to_server(self, server_config: dict[str, Any]) -> None:
        """Connect to a single MCP server."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_name = server_config["name"]
        command = server_config["command"]
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        logger.info(f"Connecting to MCP server: {server_name}")

        # Create server parameters
        server_params = StdioServerParameters(command=command, args=args, env=env)

        # Use context manager properly to discover capabilities
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()

                # Discover and cache tools and resources
                await self._discover_server_capabilities(server_name, session)

        # Store server info for future connections
        self._servers[server_name] = {"config": server_config, "params": server_params, "connected": True}

        logger.info(f"Successfully discovered capabilities from MCP server: {server_name}")

    async def _discover_server_capabilities(self, server_name: str, session) -> None:
        """Discover tools and resources from an MCP server."""
        tools_count = 0
        resources_count = 0

        # Try to discover tools
        try:
            logger.debug(f"Attempting to list tools from {server_name}")
            tools_result = await session.list_tools()
            logger.debug(f"Got tools result: {tools_result}")

            for tool in tools_result.tools:
                tool_key = f"{server_name}:{tool.name}"
                self._available_tools[tool_key] = {
                    "server": server_name,
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
                logger.debug(f"Registered tool: {tool_key}")

            tools_count = len(tools_result.tools)
            logger.info(f"Discovered {tools_count} tools from {server_name}")
        except Exception as e:
            logger.warning(f"Could not list tools from {server_name}: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")

        # Try to discover resources (optional, some servers may not support this)
        try:
            resources_result = await session.list_resources()
            for resource in resources_result.resources:
                resource_key = f"{server_name}:{resource.name}"
                self._available_resources[resource_key] = {
                    "server": server_name,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mimeType,
                }
            resources_count = len(resources_result.resources)
            logger.info(f"Discovered {resources_count} resources from {server_name}")
        except Exception as e:
            logger.debug(f"Could not list resources from {server_name} (this may be normal): {e}")

        if tools_count == 0 and resources_count == 0:
            logger.warning(f"No tools or resources discovered from {server_name}")

            # Fallback: If this is a filesystem server and discovery failed,
            # register common filesystem tools manually as a workaround
            if server_name == "filesystem":
                logger.info("Attempting fallback: manually registering common filesystem tools")
                self._register_fallback_filesystem_tools(server_name)
                logger.info("Registered fallback filesystem tools")
        else:
            logger.info(
                f"Successfully discovered capabilities from {server_name}: {tools_count} tools, {resources_count} resources"
            )

            # Debug: Log discovered tool names
            if tools_count > 0:
                tool_names = [tool["name"] for tool in self._available_tools.values() if tool["server"] == server_name]
                logger.info(f"Available tools from {server_name}: {', '.join(tool_names)}")

    def _register_fallback_filesystem_tools(self, server_name: str) -> None:
        """Register common filesystem tools as fallback when discovery fails."""
        fallback_tools = [
            {
                "name": "read_file",
                "description": "Read the complete contents of a file from the file system",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "The path of the file to read"}},
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Create a new file or completely overwrite an existing file with new content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path of the file to write"},
                        "content": {"type": "string", "description": "The content to write to the file"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": "Get a list of all files and directories in a specified path",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "The path of the directory to list"}},
                    "required": ["path"],
                },
            },
            {
                "name": "create_directory",
                "description": "Create a new directory at the specified path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path where the directory should be created"}
                    },
                    "required": ["path"],
                },
            },
        ]

        for tool in fallback_tools:
            tool_key = f"{server_name}:{tool['name']}"
            self._available_tools[tool_key] = {
                "server": server_name,
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get all available tools from connected MCP servers."""
        tools = []
        for tool_key, tool_info in self._available_tools.items():
            # Convert MCP tool schema to AgentUp function schema
            schema = {
                "name": tool_key,
                "description": tool_info["description"],
                "parameters": tool_info.get("inputSchema", {}),
            }
            tools.append(schema)
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool and return the result."""
        if tool_name not in self._available_tools:
            raise ValueError(f"Tool {tool_name} not found in available MCP tools")

        tool_info = self._available_tools[tool_name]
        server_name = tool_info["server"]
        actual_tool_name = tool_info["name"]

        # Get server configuration
        server_info = self._servers[server_name]
        server_params = server_info["params"]

        logger.info(
            f"Attempting to call MCP tool '{actual_tool_name}' on server '{server_name}' with args: {arguments}"
        )

        try:
            import traceback

            from mcp import ClientSession
            from mcp.client.stdio import stdio_client

            # Create fresh connection for tool call
            try:
                logger.debug(f"Creating stdio client connection to {server_name}")
                async with stdio_client(server_params) as (read, write):
                    logger.debug("Stdio client connected, creating session")
                    async with ClientSession(read, write) as session:
                        logger.debug("Session created, initializing")
                        await session.initialize()
                        logger.debug(f"Session initialized, calling tool {actual_tool_name}")

                        # Call the tool directly with name and arguments
                        logger.debug(f"Calling tool {actual_tool_name} with arguments: {arguments}")

                        result = await session.call_tool(name=actual_tool_name, arguments=arguments)
                        logger.debug(f"Tool call completed, result type: {type(result)}")

            except Exception as connection_error:
                logger.error(f"Connection error calling MCP tool {tool_name}")
                logger.error(f"Error details: {connection_error}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                raise

            # Process result
            logger.debug(f"Processing result, has content: {hasattr(result, 'content') and result.content is not None}")
            if hasattr(result, "content") and result.content:
                # Combine text content from the result
                content_parts = []
                for i, content in enumerate(result.content):
                    logger.debug(
                        f"Processing content part {i}: type={type(content)}, has_text={hasattr(content, 'text')}, has_data={hasattr(content, 'data')}"
                    )
                    if hasattr(content, "text"):
                        content_parts.append(content.text)
                    elif hasattr(content, "data"):
                        content_parts.append(str(content.data))
                    else:
                        logger.warning(f"Unknown content type in MCP result: {type(content)}")
                        content_parts.append(str(content))

                final_result = "\n".join(content_parts)
                logger.info(
                    f"MCP tool {tool_name} returned: {final_result[:200]}{'...' if len(final_result) > 200 else ''}"
                )
                return final_result
            else:
                logger.info(f"MCP tool {tool_name} completed with no content")
                return "Tool executed successfully (no content returned)"

        except Exception as e:
            logger.error(f"Failed to call MCP tool {tool_name}: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

    async def get_resource(self, resource_uri: str) -> str | None:
        """Get content from an MCP resource."""
        for resource_key, resource_info in self._available_resources.items():
            if resource_key == resource_uri or resource_info["name"] == resource_uri:
                server_name = resource_info["server"]
                server_info = self._servers[server_name]
                server_params = server_info["params"]

                try:
                    from mcp import ClientSession
                    from mcp.client.stdio import stdio_client

                    # Create fresh connection for resource access
                    async with stdio_client(server_params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()

                            result = await session.read_resource(uri=resource_info["name"])

                            # Process resource content
                            if result.contents:
                                content_parts = []
                                for content in result.contents:
                                    if hasattr(content, "text"):
                                        content_parts.append(content.text)
                                    elif hasattr(content, "data"):
                                        content_parts.append(str(content.data))
                                return "\n".join(content_parts)

                except Exception as e:
                    logger.error(f"Failed to read MCP resource {resource_uri}: {e}")
                break

        return None

    async def close(self) -> None:
        """Close MCP client and clear cached data."""
        logger.info("Closing MCP client")

        self._servers.clear()
        self._available_tools.clear()
        self._available_resources.clear()
        self._initialized = False

        logger.info("MCP client closed")

    async def health_check(self) -> dict[str, Any]:
        """Check health of MCP connections."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "servers_connected": len(self._servers),
            "tools_available": len(self._available_tools),
            "resources_available": len(self._available_resources),
        }

    @property
    def is_initialized(self) -> bool:
        """Check if MCP client is initialized."""
        return self._initialized

    def list_servers(self) -> list[str]:
        """list connected MCP server names."""
        return list(self._servers.keys())

    def list_tools(self) -> list[str]:
        """list available MCP tool names."""
        return list(self._available_tools.keys())

    def list_resources(self) -> list[str]:
        """list available MCP resource names."""
        return list(self._available_resources.keys())

    async def test_tool_connection(self, tool_name: str) -> dict[str, Any]:
        """Test MCP tool connection without arguments for debugging."""
        if tool_name not in self._available_tools:
            return {
                "success": False,
                "error": f"Tool {tool_name} not found in available MCP tools",
                "available_tools": list(self._available_tools.keys()),
            }

        tool_info = self._available_tools[tool_name]
        server_name = tool_info["server"]
        actual_tool_name = tool_info["name"]

        # Get server configuration
        server_info = self._servers[server_name]
        server_params = server_info["params"]

        try:
            import traceback

            from mcp import ClientSession
            from mcp.client.stdio import stdio_client

            logger.info(f"Testing connection to MCP tool '{actual_tool_name}' on server '{server_name}'")

            # Test basic connection without calling tool
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Just test that we can list tools again
                    tools_result = await session.list_tools()
                    found_tool = any(tool.name == actual_tool_name for tool in tools_result.tools)

                    return {
                        "success": True,
                        "server": server_name,
                        "tool_name": actual_tool_name,
                        "found_in_list": found_tool,
                        "total_tools": len(tools_result.tools),
                    }

        except Exception as e:
            logger.error(f"Failed to test MCP tool {tool_name}: {e}")
            import traceback

            return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
