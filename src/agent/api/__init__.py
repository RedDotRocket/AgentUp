"""API layer for AgentUp agents."""

# Import commonly used functions for backwards compatibility
from agent.config import load_config
from agent.security.decorators import protected

from .app import app, create_app, main
from .routes import (
    create_agent_card,
    get_request_handler,
    jsonrpc_error_handler,
    router,
    set_request_handler_instance,
    sse_generator,
)

__all__ = [
    "app",
    "create_app",
    "main",
    "create_agent_card",
    "get_request_handler",
    "jsonrpc_error_handler",
    "router",
    "set_request_handler_instance",
    "sse_generator",
    "load_config",
    "protected",
]
