"""
Core built-in plugins that ship with AgentUp.

Provides basic functionality for testing and examples.
"""

import structlog
from a2a.types import Task

from ..capabilities.executors import MessageProcessor
from .builtin import BuiltinPlugin, register_builtin_plugin

logger = structlog.get_logger(__name__)


async def hello_capability(task: Task, context=None) -> str:
    """
    Simple hello world capability for testing and demonstration.

    Returns a friendly greeting with basic system information.
    Safe, simple, and always available.
    """
    messages = MessageProcessor.extract_messages(task)
    latest = MessageProcessor.get_latest_user_message(messages)
    metadata = getattr(task, "metadata", {}) or {}

    echo_msg = metadata.get("message")
    style = metadata.get("format", "normal")

    if not echo_msg and latest:
        echo_msg = latest.get("content") if isinstance(latest, dict) else getattr(latest, "content", "")

    if not echo_msg:
        return "Echo: No message to echo back!"

    if style == "uppercase":
        echo_msg = echo_msg.upper()
    elif style == "lowercase":
        echo_msg = echo_msg.lower()
    elif style == "title":
        echo_msg = echo_msg.title()
    return f"Echo: {echo_msg}"


def register_core_plugins():
    """
    Built-in plugin used for testing and examples.
    """
    # Create simple hello plugin
    hello_plugin = BuiltinPlugin(
        plugin_id="hello",
        name="Hello Plugin",
        description="Simple greeting plugin for testing and examples",
    )

    # Register hello capability
    hello_plugin.register_capability("hello", hello_capability)

    # Register with global registry
    register_builtin_plugin(hello_plugin)

    logger.info("Registered hello plugin")
