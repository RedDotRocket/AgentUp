"""
AgentUp MCP (Model Context Protocol) Support.

This module provides MCP protocol implementation for the AgentUp framework
including client/server communication, resource management, and tool integration.
"""

# Import key MCP models for easy access
from .model import (
    MCPCapability,
    MCPMessage,
    MCPMessageType,
    MCPResource,
    MCPResourceType,
    MCPSession,
    MCPSessionState,
    MCPTool,
    MCPToolType,
    create_mcp_validator,
)

__all__ = [
    "MCPCapability",
    "MCPMessage",
    "MCPMessageType",
    "MCPResource",
    "MCPResourceType",
    "MCPSession",
    "MCPSessionState",
    "MCPTool",
    "MCPToolType",
    "create_mcp_validator",
]
