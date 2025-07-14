from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog
from mcp.server import Server
from mcp.types import TextContent, Tool

logger = structlog.get_logger(__name__)


class MCPHTTPServer:
    """
    MCP HTTP server that exposes AgentUp AI functions as MCP tools.
    This is an experimental implementation using the official MCP SDK.
    It provides a simple HTTP interface for listing and calling AI functions
    as MCP tools, along with resource management.
    It deliberately avoids expossing MCP servers as MCP servers (bare with me),
    as this would create a circular dependency.
    """

    def __init__(
        self,
        agent_name: str,
        agent_version: str = "1.0.0",  # Likely need to get this from the agent config
        expose_handlers: bool = True,
        expose_resources: list[str] | None = None,
    ):
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.expose_handlers = expose_handlers
        self.expose_resources = expose_resources or []
        self._server = None
        self._handlers: dict[str, Callable] = {}  # Kept for compatibility
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the MCP server."""

        # Create MCP server with agent info
        self._server = Server(self.agent_name, version=self.agent_version)

        # Setup tool listing handler
        @self._server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """list all available MCP tools."""
            tools = []

            # Get registered AI functions from the function registry
            try:
                from agent.core.dispatcher import get_function_registry

                registry = get_function_registry()

                # Only expose handlers/tools if configured to do so
                if self.expose_handlers:
                    for function_name in registry.list_functions():
                        if not registry.is_mcp_tool(function_name):  # Only expose local functions
                            schema = registry._functions.get(function_name, {})
                            if schema:
                                tool = Tool(
                                    name=function_name,
                                    description=schema.get("description", f"AI function: {function_name}"),
                                    inputSchema=schema.get("parameters", {}),
                                )
                                tools.append(tool)

                logger.info(f"MCP server exposing {len(tools)} AI functions as tools")

            except Exception as e:
                logger.error(f"Failed to list AI functions: {e}")

            return tools

        # Setup tool call handler
        @self._server.call_tool()
        async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle MCP tool calls by routing to AI functions."""
            try:
                from agent.core.dispatcher import get_function_registry

                registry = get_function_registry()

                if registry.is_mcp_tool(name):
                    return [
                        TextContent(
                            type="text", text=f"Error: {name} is an external MCP tool, not available on this server"
                        )
                    ]

                handler = registry.get_handler(name)
                if not handler:
                    return [TextContent(type="text", text=f"Error: No handler found for tool {name}")]

                # Create a task object for the handler
                import uuid

                from a2a.types import Message, Part, Role, Task, TaskState, TaskStatus, TextPart

                # Convert arguments to a message for the AI function
                message_content = arguments.get("message", str(arguments))

                # Create proper A2A message structure
                text_part = TextPart(text=message_content)
                part = Part(root=text_part)
                message = Message(messageId=f"mcp_{uuid.uuid4().hex[:8]}", role=Role.user, parts=[part])

                # Create task with metadata from arguments
                task = Task(
                    id=f"mcp_task_{uuid.uuid4().hex[:8]}",
                    contextId=f"mcp_context_{uuid.uuid4().hex[:8]}",
                    history=[message],
                    status=TaskStatus(state=TaskState.submitted, timestamp=datetime.now().isoformat()),
                    metadata=arguments,  # Pass all arguments as metadata
                )

                # Call the handler
                result = await handler(task)

                return [TextContent(type="text", text=str(result))]

            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                import traceback

                return [TextContent(type="text", text=f"Error calling tool {name}: {str(e)}\n{traceback.format_exc()}")]

        self._initialized = True
        logger.info(f"MCP HTTP server initialized for agent: {self.agent_name}")

    def register_handler(self, name: str, handler: Callable, schema: dict[str, Any]) -> None:
        """Register a handler (for compatibility with existing code)."""
        # With the official SDK, tools are dynamically listed from the function registry
        # This method is kept for backward compatibility but does nothing
        logger.debug(f"Handler registration ignored (using SDK): {name}")
        # Avoid unused parameter warnings
        _ = handler, schema

    async def get_server_instance(self):
        """Get the MCP server instance for integration with FastAPI."""
        if not self._initialized:
            await self.initialize()
        return self._server

    async def health_check(self) -> dict[str, Any]:
        """Check MCP server health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
        }


# FastAPI integration helper
def create_mcp_router(mcp_server: MCPHTTPServer):
    """Create a FastAPI router for MCP HTTP endpoint.

    Note: The route handlers defined below are automatically registered
    with FastAPI and are used when the router is included in the app.
    """
    import json
    import secrets

    from fastapi import APIRouter, HTTPException, Request, Response
    from fastapi.responses import StreamingResponse

    # Import security decorator
    from agent.security.decorators import protected

    router = APIRouter()

    # Session management
    _sessions: dict[str, dict] = {}

    def _validate_mcp_headers(request: Request) -> None:
        """Validate MCP protocol headers."""
        # Validate MCP protocol version
        protocol_version = request.headers.get("MCP-Protocol-Version")
        if protocol_version and protocol_version not in ["1.0", "2025-06-18"]:
            raise HTTPException(status_code=400, detail=f"Unsupported MCP protocol version: {protocol_version}")

        # Validate Origin header for security
        origin = request.headers.get("Origin")
        if origin:
            # In production, validate against allowed origins
            # For local development, be permissive
            if not (origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")):
                logger.warning(f"MCP request from non-local origin: {origin}")

    def _create_session() -> str:
        """Create a cryptographically secure session ID."""
        session_id = secrets.token_urlsafe(32)
        _sessions[session_id] = {
            "created_at": json.dumps({"timestamp": "now"}),  # Placeholder
            "active": True,
        }
        return session_id

    @router.post("/mcp")  # This handler is registered with FastAPI
    @protected(scopes={"mcp:access"})  # Require MCP access scope
    async def handle_mcp_request(request: Request) -> Response:
        """Handle MCP JSON-RPC requests via HTTP POST using the MCP SDK."""
        try:
            # Validate MCP protocol headers
            _validate_mcp_headers(request)
        except HTTPException as e:
            return Response(
                content=json.dumps({"error": e.detail}), status_code=e.status_code, media_type="application/json"
            )

        server = await mcp_server.get_server_instance()
        if not server:
            return Response(
                content=json.dumps({"error": "MCP server not initialized"}),
                status_code=503,
                media_type="application/json",
            )

        try:
            # Get request body
            body = await request.body()
            # Parse the JSON-RPC request
            request_data = json.loads(body)
            method = request_data.get("method")
            request_id = request_data.get("id")

            # Handle session initialization manually (not part of MCP SDK core)
            if method == "initialize":
                _create_session()  # Create session but don't store ID for now
                capabilities = {}

                if mcp_server.expose_handlers:
                    capabilities["tools"] = {"listChanged": True}

                if mcp_server.expose_resources:
                    capabilities["resources"] = {"subscribe": True, "listChanged": True}

                response_data = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": capabilities,
                        "serverInfo": {"name": mcp_server.agent_name, "version": mcp_server.agent_version},
                    },
                }
            else:
                # Delegate all other MCP methods to the SDK server
                # TODO: Implement proper MCP SDK HTTP transport integration
                # For now, return error for unknown methods
                response_data = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method {method} not implemented via HTTP transport yet"},
                }

            # For notifications (no id), return 202 Accepted
            if request_id is None:
                return Response(status_code=202)

            return Response(content=json.dumps(response_data), media_type="application/json")

        except Exception as e:
            logger.error(f"MCP request handling error: {e}")
            return Response(
                content=json.dumps(
                    {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Internal error: {str(e)}"}, "id": None}
                ),
                status_code=500,
                media_type="application/json",
            )

    @router.get("/mcp")  # This handler is registered with FastAPI
    @protected(scopes={"mcp:access"})  # Require MCP access scope for SSE streaming
    async def handle_mcp_sse(request: Request) -> StreamingResponse:
        """Handle MCP Server-Sent Events (SSE) for bidirectional streaming."""
        try:
            # Validate MCP protocol headers
            _validate_mcp_headers(request)
        except HTTPException as e:
            return Response(
                content=json.dumps({"error": e.detail}), status_code=e.status_code, media_type="application/json"
            )

        # Get or create session
        session_id = request.query_params.get("sessionId")
        if session_id and session_id not in _sessions:
            return Response(
                content=json.dumps({"error": "Session not found"}), status_code=404, media_type="application/json"
            )

        async def mcp_event_generator():
            """Generate MCP-compliant SSE events."""
            try:
                # Send initial connection event
                connection_event = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {
                        "agent": mcp_server.agent_name,
                        "version": mcp_server.agent_version,
                        "capabilities": {"tools": True, "resources": True},
                    },
                }
                yield f"data: {json.dumps(connection_event)}\n\n"

                # Keep connection alive and handle incoming messages
                # In a real implementation, this would handle bidirectional communication
                # For now, just keep the stream alive
                import asyncio

                while True:
                    await asyncio.sleep(30)  # Heartbeat every 30 seconds
                    heartbeat = {
                        "jsonrpc": "2.0",
                        "method": "notifications/heartbeat",
                        "params": {"timestamp": datetime.now().isoformat()},
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"

            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                error_event = {"jsonrpc": "2.0", "method": "notifications/error", "params": {"error": str(e)}}
                yield f"data: {json.dumps(error_event)}\n\n"

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",  # Configure appropriately for production
            "Access-Control-Allow-Headers": "MCP-Protocol-Version, Origin",
        }

        return StreamingResponse(mcp_event_generator(), media_type="text/event-stream", headers=headers)

    return router
