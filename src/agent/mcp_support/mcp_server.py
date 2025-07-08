import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# CONDITIONAL_MCP_IMPORTS
def _check_fastmcp_availability():
    """Check if FastMCP is available."""
    try:
        import fastmcp
        from fastmcp import FastMCP

        return True, fastmcp, FastMCP
    except ImportError:
        return False, None, None


MCP_AVAILABLE, _fastmcp_module, _FastMCP = _check_fastmcp_availability()

if not MCP_AVAILABLE:
    logger.warning("FastMCP not available. Install with: pip install fastmcp")


class MCPServerComponent:
    """MCP server that exposes AgentUp handlers as MCP tools."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self._handlers: dict[str, Callable] = {}
        self._resources: dict[str, Any] = {}
        self._server = None
        self._initialized = False
        self._server_task = None  # Track background server task

    async def initialize(self) -> None:
        """Initialize the MCP server."""
        logger.info("Initializing MCP server")
        if not MCP_AVAILABLE:
            logger.warning("FastMCP not available. Install with: pip install fastmcp")
            return

        # Create FastMCP server
        logger.info("Creating FastMCP server")
        self._server = _FastMCP(self.config.get("name", "{{ project_name_snake }}-server"))

        # Register default resources
        logger.info("Registering default MCP resources")
        await self._register_default_resources()

        self._initialized = True
        logger.info(f"MCP server '{self.name}' initialized")

    async def _register_default_resources(self) -> None:
        """Register default MCP resources."""
        # CONDITIONAL_MCP_IMPLEMENTATION
        if not self._server:
            return

        # Example: Agent info resource
        @self._server.resource("agent://info")
        async def get_agent_info() -> str:
            """Get information about this {{ project_name }} agent."""
            return "AgentUp - A2A-compliant AI agent with MCP support"

        # Example: Health status resource
        @self._server.resource("agent://health")
        async def get_health_status() -> str:
            """Get agent health status."""
            return f"Status: healthy, Handlers: {len(self._handlers)}, Time: {datetime.now()}"

        logger.info("Registered default MCP resources")

    def register_handler_as_tool(self, name: str, handler: Callable, schema: dict[str, Any]) -> None:
        """Register an AgentUp handler as an MCP tool."""
        # CONDITIONAL_MCP_IMPLEMENTATION
        if not MCP_AVAILABLE or not self._server:
            logger.warning(f"Cannot register handler {name} - MCP server not available")
            return

        self._handlers[name] = handler

        # Extract parameters from schema
        parameters = schema.get("parameters", {})
        if not parameters:
            # If no parameters defined, create a simple wrapper with no parameters
            @self._server.tool(name)
            async def mcp_tool_wrapper() -> str:
                """MCP wrapper for AgentUp handler."""
                try:
                    # Create a minimal A2A task object for the handler
                    from types import SimpleNamespace

                    mock_task = SimpleNamespace()
                    mock_task.id = f"mcp-{name}-{datetime.now().isoformat()}"
                    mock_task.metadata = {}
                    mock_task.history = []

                    # Call the handler
                    result = await handler(mock_task)
                    return str(result)
                except Exception as e:
                    logger.error(f"MCP tool {name} failed: {e}")
                    return f"Error: {str(e)}"
        else:
            # Create wrapper with specific parameters based on schema
            param_names = list(parameters.get("properties", {}).keys())

            if not param_names:
                # No parameters, create simple wrapper
                @self._server.tool(name)
                async def mcp_tool_wrapper() -> str:
                    """MCP wrapper for AgentUp handler."""
                    try:
                        from types import SimpleNamespace

                        mock_task = SimpleNamespace()
                        mock_task.id = f"mcp-{name}-{datetime.now().isoformat()}"
                        mock_task.metadata = {}
                        mock_task.history = []
                        result = await handler(mock_task)
                        return str(result)
                    except Exception as e:
                        logger.error(f"MCP tool {name} failed: {e}")
                        return f"Error: {str(e)}"
            else:
                # Create function with explicit parameters
                # Build parameter string for function signature
                param_str = ", ".join(param_names)

                # Create function source code
                func_source = f"""
async def mcp_tool_wrapper({param_str}) -> str:
    \"\"\"MCP wrapper for AgentUp handler.\"\"\"
    try:
        from types import SimpleNamespace
        mock_task = SimpleNamespace()
        mock_task.id = f"mcp-{name}-{{datetime.now().isoformat()}}"
        mock_task.metadata = {{{", ".join([f"'{p}': {p}" for p in param_names])}}}
        mock_task.history = []
        result = await handler(mock_task)
        return str(result)
    except Exception as e:
        logger.error(f"MCP tool {name} failed: {{e}}")
        return f"Error: {{str(e)}}"
"""

                # Execute the function definition with restricted globals for security
                # Validate parameter names to prevent code injection
                for param in param_names:
                    if not param.isidentifier() or param.startswith("_"):
                        raise ValueError(f"Invalid parameter name: {param}")

                # Restricted globals to minimize attack surface
                restricted_globals = {
                    "__builtins__": {
                        "str": str,
                        "len": len,
                        "range": range,
                        "Exception": Exception,
                    },
                    "datetime": datetime,
                }
                local_vars = {"handler": handler, "logger": logger, "datetime": datetime}

                # Bandit: This is a controlled execution of a function definition
                # in a restricted environment with no external input
                exec(func_source, restricted_globals, local_vars)  # nosec
                mcp_tool_wrapper = local_vars["mcp_tool_wrapper"]

                # Register with FastMCP
                self._server.tool(name)(mcp_tool_wrapper)

        logger.info(f"Registered handler '{name}' as MCP tool")

    async def start_server(self, host: str = "localhost", port: int = 8001) -> None:
        """Start the MCP server."""
        if not self._server:
            logger.error("MCP server not initialized")
            return

        try:
            logger.info(f"Starting MCP server on {host}:{port}")
            await self._server.run(host=host, port=port)
        except asyncio.CancelledError:
            logger.info("MCP server task cancelled")
            raise
        except Exception as e:
            logger.error(f"MCP server failed: {e}")

    async def close(self) -> None:
        """Close the MCP server."""
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        self._server = None
        self._handlers.clear()
        self._resources.clear()
        self._initialized = False

        logger.info("MCP server closed")

    async def health_check(self) -> dict[str, Any]:
        """Check MCP server health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "handlers_registered": len(self._handlers),
            "resources_available": len(self._resources),
        }

    @property
    def is_initialized(self) -> bool:
        """Check if MCP server is initialized."""
        return self._initialized

    def list_handlers(self) -> list[str]:
        """list registered handler names."""
        return list(self._handlers.keys())

    def list_resources(self) -> list[str]:
        """list available resource names."""
        return list(self._resources.keys())
