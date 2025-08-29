import hashlib
import time
from typing import Any, Protocol

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
    TextResourceContents,
)

logger = structlog.get_logger(__name__)


class MCPTransportClient(Protocol):
    """Protocol for MCP transport clients."""

    async def __aenter__(self): ...

    async def __aexit__(self, exc_type, exc_val, exc_tb): ...


class MCPClientService:
    """MCP client service with support for all transport protocols."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self._servers: dict[str, dict[str, Any]] = {}
        self._available_tools: dict[str, dict[str, Any]] = {}
        self._available_resources: dict[str, dict[str, Any]] = {}
        self._initialized = False
        # Cache for function call results (tool_name + args hash -> (result, timestamp))
        self._function_call_cache: dict[str, tuple[str, float]] = {}
        # Cache TTL in seconds (short cache to avoid stale data)
        self._cache_ttl = 60
        # Persistent connections for MCP servers (server_name -> (session, read, write, transport_context))
        self._persistent_connections: dict[str, tuple[Any, Any, Any, Any]] = {}
        # Track which servers require persistent connections (OAuth-based servers)
        self._persistent_servers: set[str] = set()

    async def initialize(self) -> None:
        """Initialize MCP client and discover capabilities from all configured servers."""
        servers_config = self.config.get("servers", [])

        # Filter out disabled servers
        enabled_servers = [s for s in servers_config if s.get("enabled", True)]
        disabled_count = len(servers_config) - len(enabled_servers)

        if disabled_count > 0:
            logger.info(f"Skipping {disabled_count} disabled MCP servers")

        for server_config in enabled_servers:
            await self._connect_to_server(server_config)

        # Count successful connections and gather detailed status
        connected_servers = []
        failed_servers = []

        for server_name, server_info in self._servers.items():
            if server_info.get("connected", False):
                connected_servers.append(server_name)
            else:
                failed_servers.append(
                    {
                        "name": server_name,
                        "transport": server_info.get("transport", "unknown"),
                        "error": server_info.get("error", "Unknown error"),
                    }
                )

        self._initialized = True

        # Count available tools (removed as they're not used in the new logging format)

        # Log detailed connection results
        if connected_servers:
            # Create a summary of tools with scopes for each server
            server_summaries = []
            for server in connected_servers:
                server_tools = [
                    (tool_name, tool_info)
                    for tool_name, tool_info in self._available_tools.items()
                    if tool_info["server"] == server
                ]
                if server_tools:
                    tool_summary = f"{server}: "
                    tool_details = []
                    for _, tool_info in server_tools:
                        scopes = tool_info.get("scopes", [])
                        scope_str = f"[{', '.join(scopes)}]" if scopes else "[no scopes]"
                        tool_details.append(f"{tool_info['name']} {scope_str}")
                    tool_summary += ", ".join(tool_details)
                    server_summaries.append(tool_summary)

            if server_summaries:
                logger.debug(
                    f"MCP initialized: {len(connected_servers)} server(s) connected with tools: "
                    + "; ".join(server_summaries)
                )

            # Log connection failures with specific details
            if failed_servers:
                for failed in failed_servers:
                    logger.error(
                        f"MCP server '{failed['name']}' ({failed['transport']}) failed to connect: {failed['error']}",
                        extra={
                            "server_name": failed["name"],
                            "transport": failed["transport"],
                            "error": failed["error"],
                        },
                    )
                logger.warning(
                    f"MCP client partially functional: {len(failed_servers)} of {len(self._servers)} servers failed to connect"
                )
        else:
            # No servers connected - this is a critical issue
            logger.error(
                "MCP client initialization failed: No servers connected successfully. "
                "MCP functionality will be unavailable.",
                extra={"configured_servers": len(enabled_servers), "failed_servers": len(failed_servers)},
            )

            # Log specific failure details
            for failed in failed_servers:
                logger.error(f"Server '{failed['name']}' ({failed['transport']}): {failed['error']}")

    async def _connect_to_server(self, server_config: dict[str, Any]) -> None:
        """Connect to a server using the appropriate transport protocol."""
        server_name = server_config["name"]
        transport = server_config["transport"]

        logger.debug(f"Connecting to MCP server '{server_name}' using {transport} transport")

        # Check if this server needs persistent connection (OAuth-based servers)
        needs_persistent = self._requires_persistent_connection(server_config)

        if needs_persistent:
            logger.debug(f"Server '{server_name}' identified as requiring persistent connection")
            self._persistent_servers.add(server_name)
            await self._establish_persistent_connection(server_name, server_config)
        else:
            # Use temporary connection for discovery only
            await self._discover_server_with_temp_connection(server_name, server_config)

    def _requires_persistent_connection(self, server_config: dict[str, Any]) -> bool:
        """Determine if a server requires persistent connection (OAuth-based servers)."""
        # Check for OAuth credentials in environment variables
        env = server_config.get("env", {})
        for key in env.keys():
            if any(oauth_key in key.upper() for oauth_key in ["OAUTH", "CREDENTIAL", "AUTH"]):
                return True
        return False

    async def _establish_persistent_connection(self, server_name: str, server_config: dict[str, Any]) -> None:
        """Establish and maintain persistent connection for OAuth servers."""
        transport = server_config["transport"]

        try:
            # Create transport client
            transport_context = self._create_transport_client(server_config)

            # Establish connection
            read, write, *_ = await transport_context.__aenter__()

            # Create and initialize session
            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()

            # Store persistent connection
            self._persistent_connections[server_name] = (session, read, write, transport_context)

            # Discover capabilities through persistent connection
            await self._discover_server_capabilities(server_name, session)

            # Store server info
            self._servers[server_name] = {
                "config": server_config,
                "transport": transport,
                "connected": True,
                "persistent": True,
            }

            logger.debug(f"Successfully established persistent connection to MCP server: {server_name}")

        except Exception as e:
            await self._handle_connection_error(server_name, server_config, e)

    async def _discover_server_with_temp_connection(self, server_name: str, server_config: dict[str, Any]) -> None:
        """Discover server capabilities using temporary connection."""
        transport = server_config["transport"]
        transport_context = self._create_transport_client(server_config)

        try:
            async with transport_context as (read, write, *_):
                async with ClientSession(read, write) as session:
                    # Initialize session
                    await session.initialize()

                    # Discover and cache tools and resources
                    await self._discover_server_capabilities(server_name, session)

            # Store server info for future connections
            self._servers[server_name] = {
                "config": server_config,
                "transport": transport,
                "connected": True,
                "persistent": False,
            }

            logger.debug(f"Successfully connected to MCP server: {server_name}")

        except Exception as e:
            await self._handle_connection_error(server_name, server_config, e)

    async def _handle_connection_error(self, server_name: str, server_config: dict[str, Any], e: Exception) -> None:
        """Handle connection errors with enhanced error messages."""
        error_msg = str(e)
        transport = server_config["transport"]

        # Provide specific, actionable error messages based on common failure patterns
        if "403" in error_msg or "Forbidden" in error_msg:
            enhanced_error = (
                f"Authentication failed for MCP server '{server_name}': Invalid or missing authentication token. "
                f"Check your API key or authentication token in the server configuration."
            )
            logger.error(enhanced_error)
        elif "401" in error_msg or "Unauthorized" in error_msg:
            enhanced_error = (
                f"Authentication required for MCP server '{server_name}': Missing authorization header. "
                f"Ensure the server configuration includes valid authentication credentials."
            )
            logger.error(enhanced_error)
        elif "Connection refused" in error_msg or "refused" in error_msg.lower():
            enhanced_error = (
                f"Connection refused to MCP server '{server_name}': Server may not be running or URL may be incorrect. "
                f"Verify the server is running and the URL/port in your configuration is correct."
            )
            logger.error(enhanced_error)
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            enhanced_error = (
                f"Connection timeout to MCP server '{server_name}': Server is not responding. "
                f"Check if the server is running and network connectivity is available."
            )
            logger.error(enhanced_error)
        elif "Name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
            enhanced_error = (
                f"DNS resolution failed for MCP server '{server_name}': Cannot resolve hostname. "
                f"Check the server URL/hostname in your configuration."
            )
            logger.error(enhanced_error)
        elif "unhandled errors in a TaskGroup" in error_msg:
            # TaskGroup exceptions often wrap the real error
            enhanced_error = (
                f"Connection error to MCP server '{server_name}': {error_msg}. "
                f"This may be due to authentication, network, or server configuration issues."
            )
            logger.error(enhanced_error)
        else:
            enhanced_error = (
                f"Failed to establish session with MCP server '{server_name}': {error_msg}. "
                f"Check server configuration and ensure the server is running and accessible."
            )
            logger.error(enhanced_error)

        # Include impact information
        logger.debug(
            f"MCP server '{server_name}' failure will result in unavailable tools/resources from this server. "
            f"Other configured servers may still function normally."
        )

        # Store server as failed with enhanced error information
        self._servers[server_name] = {
            "config": server_config,
            "transport": transport,
            "connected": False,
            "error": enhanced_error,
            "original_error": str(e),
            "persistent": False,
        }

        # Don't raise - allow other servers to connect

    def _create_transport_client(self, server_config: dict[str, Any]):
        """Create appropriate transport client based on configuration."""
        transport = server_config["transport"]

        if transport == "stdio":
            return self._create_stdio_client(server_config)
        elif transport == "sse":
            return self._create_sse_client(server_config)
        elif transport == "streamable_http":
            return self._create_streamable_http_client(server_config)
        else:
            raise ValueError(f"Unsupported transport type: {transport}")

    def _create_stdio_client(self, server_config: dict[str, Any]):
        """Create stdio transport client."""
        command = server_config["command"]
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        server_params = StdioServerParameters(command=command, args=args, env=env)

        return stdio_client(server_params)

    def _create_sse_client(self, server_config: dict[str, Any]):
        """Create SSE transport client."""
        url = server_config["url"]
        headers = server_config.get("headers", {})

        # Add headers if provided
        if headers:
            # Mask sensitive headers for logging
            safe_headers = {k: "***" if k.lower() == "authorization" else v for k, v in headers.items()}
            logger.debug(f"Using SSE client with headers: {safe_headers}")
            # Pass headers to SSE client
            return sse_client(url, headers=headers)

        return sse_client(url)

    def _create_streamable_http_client(self, server_config: dict[str, Any]):
        """Create streamable HTTP transport client."""
        url = server_config["url"]
        headers = server_config.get("headers", {})

        # Add headers if provided
        if headers:
            # Mask sensitive headers for logging
            safe_headers = {k: "***" if k.lower() == "authorization" else v for k, v in headers.items()}
            logger.debug(f"Using streamable HTTP client with headers: {safe_headers}")
            # Pass headers to streamable HTTP client
            return streamablehttp_client(url, headers=headers)

        return streamablehttp_client(url)

    async def _discover_server_capabilities(self, server_name: str, session: ClientSession) -> None:
        """Discover and cache tools and resources from a server."""
        tools_count = 0
        resources_count = 0

        # Discover tools
        try:
            logger.debug(f"Discovering tools from {server_name}")
            tools_result = await session.list_tools()

            for tool in tools_result.tools:
                # Use clean tool name, store server info separately
                tool_key = tool.name
                self._available_tools[tool_key] = {
                    "server": server_name,
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
                logger.debug(f"Registered tool: {tool_key} from server {server_name}")

            tools_count = len(tools_result.tools)
            logger.debug(f"Discovered {tools_count} tools from {server_name}")

        except Exception as e:
            logger.warning(f"Could not list tools from {server_name}: {e}")

        # Discover resources (optional)
        try:
            resources_result = await session.list_resources()

            for resource in resources_result.resources:
                # Use clean resource name, store server info separately
                resource_key = resource.name
                self._available_resources[resource_key] = {
                    "server": server_name,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": getattr(resource, "mimeType", None),
                }

            resources_count = len(resources_result.resources)
            logger.debug(f"Discovered {resources_count} resources from {server_name}")

        except Exception as e:
            logger.debug(f"Could not list resources from {server_name} (this may be normal): {e}")

        if tools_count == 0 and resources_count == 0:
            logger.warning(f"No tools or resources discovered from {server_name}")
        else:
            logger.debug(
                f"Successfully discovered capabilities from {server_name}: "
                f"{tools_count} tools, {resources_count} resources"
            )

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools in AgentUp function schema format."""
        tools = []
        for tool_key, tool_info in self._available_tools.items():
            schema = {
                "name": tool_key,
                "description": tool_info["description"],
                "parameters": tool_info.get("inputSchema", {}),
                "server": tool_info["server"],  # Include server information for capability registration
                "inputSchema": tool_info.get("inputSchema", {}),  # Include original inputSchema
            }
            tools.append(schema)
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool using persistent connection when available, with caching to prevent repeated calls."""
        # Handle prefixed tool names (e.g., "stdio:get_forecast" -> "get_forecast")
        clean_tool_name = tool_name
        if ":" in tool_name:
            # Extract clean tool name from prefixed name
            clean_tool_name = tool_name.split(":", 1)[1]

        if clean_tool_name not in self._available_tools:
            raise ValueError(f"Tool {tool_name} not found in available MCP tools")

        tool_info = self._available_tools[clean_tool_name]
        server_name = tool_info["server"]
        actual_tool_name = tool_info["name"]

        # Check if server is connected
        server_info = self._servers.get(server_name)
        if not server_info or not server_info.get("connected", False):
            error = server_info.get("error", "Unknown error") if server_info else "Server not found"
            raise ValueError(f"Cannot call tool '{tool_name}': Server '{server_name}' is not connected. {error}")

        # Generate cache key from tool name and arguments
        cache_key = self._generate_cache_key(actual_tool_name, arguments)
        current_time = time.time()

        # Check cache first
        if cache_key in self._function_call_cache:
            cached_result, cached_time = self._function_call_cache[cache_key]
            if current_time - cached_time < self._cache_ttl:
                logger.info(f"Using cached result for MCP tool '{actual_tool_name}' on server '{server_name}'")
                return cached_result
            else:
                # Remove expired cache entry
                del self._function_call_cache[cache_key]

        logger.info(f"Calling MCP tool '{actual_tool_name}' on server '{server_name}' with arguments: {arguments}")

        try:
            # Use persistent connection if available, otherwise create fresh connection
            if server_name in self._persistent_connections:
                result = await self._call_tool_persistent(server_name, actual_tool_name, arguments)
            else:
                result = await self._call_tool_temporary(server_name, actual_tool_name, arguments)

            # Process and return result
            processed_result = self._process_tool_result(result, tool_name)

            # Cache the result
            self._function_call_cache[cache_key] = (processed_result, current_time)

            # Clean up expired cache entries periodically (every 10 calls)
            if len(self._function_call_cache) % 10 == 0:
                self._cleanup_expired_cache()

            return processed_result

        except Exception as e:
            logger.error(f"Failed to call MCP tool {tool_name}: {e}")
            raise

    async def _call_tool_persistent(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call tool using persistent connection."""
        session, read, write, transport_context = self._persistent_connections[server_name]

        try:
            # Call the tool using the existing session
            result = await session.call_tool(name=tool_name, arguments=arguments)
            return result
        except Exception as e:
            # If persistent connection fails, try to re-establish it
            logger.warning(f"Persistent connection to '{server_name}' failed, attempting to re-establish: {e}")
            await self._reconnect_persistent_server(server_name)

            # Retry the call with new connection
            session, read, write, transport_context = self._persistent_connections[server_name]
            result = await session.call_tool(name=tool_name, arguments=arguments)
            return result

    async def _call_tool_temporary(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call tool using temporary connection (original behavior)."""
        server_info = self._servers[server_name]
        server_config = server_info["config"]

        # Create fresh transport connection for tool call
        transport_context = self._create_transport_client(server_config)

        async with transport_context as (read, write, *_):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Call the tool
                result = await session.call_tool(name=tool_name, arguments=arguments)
                return result

    async def _reconnect_persistent_server(self, server_name: str) -> None:
        """Re-establish persistent connection for a server."""
        # Clean up existing connection
        if server_name in self._persistent_connections:
            session, read, write, transport_context = self._persistent_connections[server_name]
            try:
                await session.__aexit__(None, None, None)
                await transport_context.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error cleaning up old connection for '{server_name}': {e}")
            del self._persistent_connections[server_name]

        # Re-establish connection
        server_config = self._servers[server_name]["config"]
        await self._establish_persistent_connection(server_name, server_config)

    def _process_tool_result(self, result: Any, tool_name: str) -> str:
        """Process MCP tool result into string format."""
        if hasattr(result, "content") and result.content:
            content_parts = []
            for content in result.content:
                # Handle different content types from MCP
                if isinstance(content, TextContent):
                    content_parts.append(content.text)
                elif isinstance(content, ImageContent | AudioContent):
                    # For binary content types, include metadata
                    content_parts.append(f"[{content.type}: {content.mimeType}]")
                elif isinstance(content, ResourceLink):
                    # For resource links, include the URI
                    content_parts.append(f"[Resource: {content.uri}]")
                elif isinstance(content, EmbeddedResource):
                    # Handle embedded resources
                    if isinstance(content.resource, TextResourceContents):
                        content_parts.append(content.resource.text)
                    elif isinstance(content.resource, BlobResourceContents):
                        content_parts.append(f"[Embedded blob: {content.resource.mimeType}]")
                else:
                    # Fallback for unknown content types
                    content_parts.append(str(content))

            final_result = "\n".join(content_parts)
            logger.debug(
                f"MCP tool {tool_name} returned: {final_result[:200]}{'...' if len(final_result) > 200 else ''}"
            )
            return final_result
        else:
            logger.info(f"MCP tool {tool_name} completed with no content")
            return "Tool executed successfully (no content returned)"

    async def get_resource(self, resource_uri: str) -> str | None:
        """Get an MCP resource by creating a fresh session."""
        for resource_key, resource_info in self._available_resources.items():
            if resource_key == resource_uri or resource_info["name"] == resource_uri:
                server_name = resource_info["server"]
                server_info = self._servers[server_name]
                server_config = server_info["config"]

                try:
                    transport_context = self._create_transport_client(server_config)

                    async with transport_context as (read, write, *_):
                        async with ClientSession(read, write) as session:
                            await session.initialize()

                            result = await session.read_resource(uri=resource_info["name"])

                            # Process resource content
                            if result.contents:
                                content_parts = []
                                for content in result.contents:
                                    # Check if it's TextResourceContents (has 'text' field)
                                    if isinstance(content, TextResourceContents):
                                        content_parts.append(content.text)
                                    # Check if it's BlobResourceContents (has 'blob' field)
                                    elif isinstance(content, BlobResourceContents):
                                        content_parts.append(content.blob)
                                    else:
                                        content_parts.append(str(content))  # type: ignore[unreachable]
                                return "\n".join(content_parts)

                except Exception as e:
                    logger.error(f"Failed to read MCP resource {resource_uri}: {e}")
                break

        return None

    def _generate_cache_key(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Generate a cache key from tool name and arguments."""
        # Create a deterministic string from arguments by sorting keys
        args_str = str(sorted(arguments.items()))
        cache_input = f"{tool_name}:{args_str}"
        # Use hash to create a shorter key
        # Bandit nosec, as not used for security, just for caching
        return hashlib.md5(cache_input.encode()).hexdigest()  # nosec

    def _cleanup_expired_cache(self) -> None:
        """Remove expired entries from the function call cache."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, cached_time) in self._function_call_cache.items()
            if current_time - cached_time >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._function_call_cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def close(self) -> None:
        """Close MCP client and clean up resources."""
        logger.info("Closing MCP client")

        # Close all persistent connections
        for server_name, (session, _, _, transport_context) in self._persistent_connections.items():
            try:
                logger.debug(f"Closing persistent connection for server '{server_name}'")
                await session.__aexit__(None, None, None)
                await transport_context.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error closing persistent connection for '{server_name}': {e}")

        self._persistent_connections.clear()
        self._persistent_servers.clear()
        self._servers.clear()
        self._available_tools.clear()
        self._available_resources.clear()
        self._function_call_cache.clear()
        self._initialized = False

        logger.info("MCP client closed")

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on MCP client."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "servers_connected": len(self._servers),
            "tools_available": len(self._available_tools),
            "resources_available": len(self._available_resources),
        }

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized

    def list_servers(self) -> list[str]:
        """List connected server names."""
        return list(self._servers.keys())

    def list_tools(self) -> list[str]:
        """List available tool names."""
        return list(self._available_tools.keys())

    def list_resources(self) -> list[str]:
        """List available resource names."""
        return list(self._available_resources.keys())

    async def test_tool_connection(self, tool_name: str) -> dict[str, Any]:
        """Test connection to a specific tool."""
        if tool_name not in self._available_tools:
            return {
                "success": False,
                "error": f"Tool {tool_name} not found in available MCP tools",
                "available_tools": list(self._available_tools.keys()),
            }

        tool_info = self._available_tools[tool_name]
        server_name = tool_info["server"]
        server_config = self._servers[server_name]["config"]

        try:
            logger.info(f"Testing connection to MCP tool '{tool_name}' on server '{server_name}'")

            # Test basic connection without calling tool
            transport_context = self._create_transport_client(server_config)

            async with transport_context as (read, write, *_):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Test that we can list tools again
                    tools_result = await session.list_tools()
                    found_tool = any(tool.name == tool_info["name"] for tool in tools_result.tools)

                    return {
                        "success": True,
                        "server": server_name,
                        "tool_name": tool_info["name"],
                        "found_in_list": found_tool,
                        "total_tools": len(tools_result.tools),
                        "transport": server_config["transport"],
                    }

        except Exception as e:
            logger.error(f"Failed to test MCP tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "server": server_name,
                "transport": server_config["transport"],
            }
