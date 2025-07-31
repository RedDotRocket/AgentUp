from .base import Service
from .builtin_capabilities import BuiltinCapabilityRegistry
from .config import ConfigurationManager


class MCPService(Service):
    """Manages MCP integration for the agent.

    This service handles:
    - MCP client/server initialization
    - MCP tool registration as capabilities
    - MCP HTTP server setup
    """

    def __init__(self, config_manager: ConfigurationManager, capability_registry: BuiltinCapabilityRegistry):
        super().__init__(config_manager)
        self.capabilities = capability_registry
        self._mcp_client = None
        self._mcp_server = None

    async def initialize(self) -> None:
        self.logger.info("Initializing MCP service")

        mcp_config = self.config.get("mcp", {})
        if not mcp_config.get("enabled", False):
            self.logger.info("MCP integration disabled")
            self._initialized = True
            return

        try:
            # Initialize MCP integration using existing code
            from agent.mcp_support.mcp_integration import initialize_mcp_integration

            await initialize_mcp_integration(self.config.config)

            self._initialized = True
            self.logger.info("MCP integration initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize MCP integration: {e}")
            raise

    async def shutdown(self) -> None:
        self.logger.debug("Shutting down MCP service")

        try:
            from agent.mcp_support.mcp_integration import shutdown_mcp_integration

            await shutdown_mcp_integration()
            self.logger.info("MCP integration shut down successfully")

        except Exception as e:
            self.logger.error(f"Failed to shutdown MCP integration: {e}")

        self._mcp_client = None
        self._mcp_server = None
