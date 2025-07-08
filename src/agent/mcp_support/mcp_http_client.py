from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class MCPHTTPClient:
    """MCP client for connecting to other agents via HTTP transport."""

    def __init__(self, agent_url: str, auth_config: dict[str, Any] | None = None):
        """
        Initialize MCP HTTP client.

        Args:
            agent_url: Base URL of the target agent (e.g., http://localhost:8002)
            auth_config: Optional OAuth2 configuration
        """
        self.agent_url = agent_url.rstrip("/")
        self.mcp_endpoint = f"{self.agent_url}/mcp"
        self.auth_config = auth_config or {}
        self._access_token = None
        self._tools: dict[str, dict[str, Any]] = {}
        self._agent_card = None

    async def connect(self) -> bool:
        """Connect to the agent and discover capabilities."""
        try:
            # First, discover the agent via AgentCard
            await self._discover_agent()

            # Authenticate if OAuth2 is configured
            if self.auth_config.get("enabled"):
                await self._authenticate()

            # Discover MCP tools
            await self._discover_tools()

            logger.info(f"Connected to agent at {self.agent_url} with {len(self._tools)} tools")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to agent at {self.agent_url}: {e}")
            return False

    async def _discover_agent(self) -> None:
        """Discover agent capabilities via AgentCard."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.agent_url}/.well-known/agent.json")
                response.raise_for_status()

                self._agent_card = response.json()
                logger.info(f"Discovered agent: {self._agent_card.get('name')}")

                # Check if agent supports MCP
                capabilities = self._agent_card.get("capabilities", {})
                if capabilities.get("mcp", {}).get("enabled"):
                    mcp_endpoint = capabilities["mcp"].get("endpoint", "/mcp")
                    self.mcp_endpoint = f"{self.agent_url}{mcp_endpoint}"
                    logger.info(f"Agent supports MCP at: {self.mcp_endpoint}")

        except Exception as e:
            logger.error(f"Failed to discover agent: {e}")
            raise

    async def _authenticate(self) -> None:
        """Authenticate with OAuth2 if configured."""
        try:
            token_url = self.auth_config.get("token_url")
            client_id = self.auth_config.get("client_id")
            client_secret = self.auth_config.get("client_secret")

            if not all([token_url, client_id, client_secret]):
                logger.warning("OAuth2 not properly configured, skipping authentication")
                return

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scope": "agent.read agent.tools.use",
                    },
                )
                response.raise_for_status()

                token_data = response.json()
                self._access_token = token_data.get("access_token")
                logger.info("Successfully authenticated with target agent")

        except Exception as e:
            logger.error(f"OAuth2 authentication failed: {e}")
            # Continue without auth - agent might not require it

    async def _discover_tools(self) -> None:
        """Discover available MCP tools from the agent."""
        try:
            headers = self._get_headers()

            # Call MCP list_tools method
            request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

            async with httpx.AsyncClient() as client:
                response = await client.post(self.mcp_endpoint, json=request_data, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "tools" in result["result"]:
                        for tool in result["result"]["tools"]:
                            tool_name = tool.get("name")
                            if tool_name:
                                self._tools[tool_name] = tool

                    logger.info(f"Discovered {len(self._tools)} MCP tools")
                else:
                    logger.warning(f"MCP tools discovery returned: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to discover MCP tools: {e}")
            # Continue - we might still be able to use the agent via A2A

    def _get_headers(self) -> dict[str, str]:
        """Get headers including auth token if available."""
        headers = {"Content-Type": "application/json"}

        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        return headers

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool on the remote agent."""
        try:
            headers = self._get_headers()

            # Prepare MCP tool call request
            request_data = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 2,
            }

            logger.info(f"Calling MCP tool '{tool_name}' on {self.agent_url}")

            async with httpx.AsyncClient() as client:
                response = await client.post(self.mcp_endpoint, json=request_data, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        # Extract text content from MCP response
                        content = result["result"]
                        if isinstance(content, list) and len(content) > 0:
                            # MCP returns content as array of content blocks
                            text_parts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text_parts.append(block.get("text", ""))
                            return "\n".join(text_parts)
                        return str(content)
                    elif "error" in result:
                        error = result["error"]
                        return f"MCP Error: {error.get('message', 'Unknown error')}"
                else:
                    return f"HTTP Error: {response.status_code}"

        except Exception as e:
            logger.error(f"Failed to call MCP tool {tool_name}: {e}")
            raise

    async def call_agent_skill(self, skill_id: str, message: str, metadata: dict | None = None) -> str:
        """
        Call an agent skill via A2A protocol (fallback when MCP is not available).
        """
        try:
            headers = self._get_headers()

            # Use A2A JSON-RPC format
            request_data = {
                "jsonrpc": "2.0",
                "method": "send_message",
                "params": {
                    "messages": [{"role": "user", "content": message}],
                    "metadata": {"skill_id": skill_id, **(metadata or {})},
                },
                "id": 3,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.agent_url,  # A2A endpoint is at root
                    json=request_data,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", "No response")
                else:
                    return f"Error: {response.status_code}"

        except Exception as e:
            logger.error(f"Failed to call agent skill {skill_id}: {e}")
            return f"Error: {str(e)}"

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available MCP tools."""
        return list(self._tools.values())

    def get_agent_info(self) -> dict[str, Any] | None:
        """Get discovered agent information."""
        return self._agent_card

    async def close(self) -> None:
        """Close the client connection."""
        self._tools.clear()
        self._access_token = None
        self._agent_card = None
        logger.info(f"Closed connection to {self.agent_url}")


class MCPHTTPClientService:
    """Service wrapper for managing multiple MCP HTTP clients."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self._clients: dict[str, MCPHTTPClient] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize MCP clients based on configuration."""
        servers_config = self.config.get("servers", [])

        for server_config in servers_config:
            if server_config.get("type") == "http":
                await self._connect_to_http_server(server_config)
            else:
                # Skip non-HTTP servers (like stdio-based ones)
                logger.info(f"Skipping non-HTTP server: {server_config.get('name')}")

        self._initialized = True
        logger.info(f"MCP HTTP client service initialized with {len(self._clients)} connections")

    async def _connect_to_http_server(self, server_config: dict[str, Any]) -> None:
        """Connect to an HTTP-based MCP server."""
        server_name = server_config.get("name", "unknown")
        server_url = server_config.get("url", "")

        if not server_url:
            logger.error(f"No URL provided for HTTP server: {server_name}")
            return

        try:
            # Extract auth config if present
            auth_config = server_config.get("auth", {})

            # Create and connect client
            client = MCPHTTPClient(server_url, auth_config)
            if await client.connect():
                self._clients[server_name] = client
                logger.info(f"Connected to HTTP MCP server: {server_name} at {server_url}")
            else:
                logger.error(f"Failed to connect to HTTP MCP server: {server_name}")

        except Exception as e:
            logger.error(f"Error connecting to HTTP MCP server {server_name}: {e}")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on any connected server."""
        # Parse server:tool format
        if ":" in tool_name:
            server_name, actual_tool_name = tool_name.split(":", 1)
            if server_name in self._clients:
                return await self._clients[server_name].call_tool(actual_tool_name, arguments)
            else:
                raise ValueError(f"No client connected to server: {server_name}")
        else:
            # Try to find the tool on any server
            for client in self._clients.values():
                tools = client.get_available_tools()
                if any(t.get("name") == tool_name for t in tools):
                    return await client.call_tool(tool_name, arguments)

            raise ValueError(f"Tool {tool_name} not found on any connected server")

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get all available tools from all connected servers."""
        all_tools = []

        for server_name, client in self._clients.items():
            tools = client.get_available_tools()
            # Prefix tool names with server name
            for tool in tools:
                prefixed_tool = tool.copy()
                prefixed_tool["name"] = f"{server_name}:{tool['name']}"
                prefixed_tool["server"] = server_name
                all_tools.append(prefixed_tool)

        return all_tools

    def list_servers(self) -> list[str]:
        """list connected server names."""
        return list(self._clients.keys())

    async def close(self) -> None:
        """Close all client connections."""
        for client in self._clients.values():
            await client.close()

        self._clients.clear()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
