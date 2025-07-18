"""
Core built-in plugins that ship with AgentUp.

Provides basic functionality for testing and examples.
"""

import structlog
from a2a.types import Task

from .builtin import BuiltinPlugin, register_builtin_plugin

logger = structlog.get_logger(__name__)


async def hello_capability(task: Task, context=None) -> str:
    """
    Simple hello world capability for testing and demonstration.

    Returns a friendly greeting with basic system information.
    Safe, simple, and always available.
    """
    user_message = "world"

    # Try to extract user input from task
    if hasattr(task, "history") and task.history:
        for message in task.history:
            if hasattr(message, "parts") and message.parts:
                for part in message.parts:
                    if hasattr(part, "text"):
                        # Extract name after "hello" if present
                        text = part.text.lower().strip()
                        if text.startswith("hello "):
                            user_message = text[6:].strip() or "world"
                        break

    return f"Hello, {user_message}! AgentUp is running successfully."


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
