import logging
from collections.abc import Callable

from a2a.types import Task

from ..config import load_config

# Import middleware decorators
from ..middleware import cached, logged, rate_limited, retryable, timed

# Load agent config to pull in project name
_config = load_config()
_project_name = _config.get("agent", {}).get("name", "Agent")

# Import shared utilities (with fallbacks for testing)
try:
    from ..utils.messages import ConversationContext, MessageProcessor
except ImportError:

    class ConversationContext:
        @classmethod
        def increment_message_count(cls, task_id):
            return 1

        @classmethod
        def get_message_count(cls, task_id):
            return 1

    class MessageProcessor:
        @staticmethod
        def extract_messages(task):
            return []

        @staticmethod
        def get_latest_user_message(messages):
            return None


# Separate import for extract_parameter with fallback
try:
    from ..utils.helpers import extract_parameter
except ImportError:

    def extract_parameter(text, param):
        return None


# Optional middleware decorators (no-ops if unavailable)
try:
    from ..middleware import cached, logged, rate_limited, retryable, timed, with_middleware
except ImportError:

    def cached(ttl=300):
        def decorator(f):
            return f

        return decorator

    def rate_limited(requests_per_minute=60):
        def decorator(f):
            return f

        return decorator

    def logged(level=None):
        def decorator(f):
            return f

        return decorator

    def retryable(max_attempts=3):
        def decorator(f):
            return f

        return decorator

    def timed():
        def decorator(f):
            return f

        return decorator

    def with_middleware(configs=None):
        def decorator(f):
            return f

        return decorator


# Optional AI decorator (no-op if unavailable)
try:
    from ..core.dispatcher import ai_function
except ImportError:

    def ai_function(description=None, parameters=None):
        def decorator(f):
            return f

        return decorator


logger = logging.getLogger(__name__)

# Handler registry - unified for all handlers (core, user, and individual)
_handlers: dict[str, Callable[[Task], str]] = {}


def register_handler(skill_id: str):
    """Decorator to register a skill handler by ID."""

    def decorator(func: Callable[[Task], str]):
        _handlers[skill_id] = func
        logger.debug(f"Registered handler: {skill_id}")
        return func

    return decorator


def get_handler(skill_id: str) -> Callable[[Task], str] | None:
    """Retrieve a registered handler by ID from unified registry, demo handlers, and registry skills."""
    # First check unified handlers registry (includes core and individual handlers)
    handler = _handlers.get(skill_id)
    if handler:
        return handler

    # No handler found
    return None


@register_handler("status")
async def handle_status(task: Task) -> str:
    """Get agent status and information."""
    return f"{_project_name} is operational and ready to process tasks. Task ID: {task.id}"


@register_handler("capabilities")
async def handle_capabilities(task: Task) -> str:
    """list agent capabilities and available skills."""
    skills = list(_handlers.keys())
    lines = "\n".join(f"- {skill}" for skill in skills)
    return f"{_project_name} capabilities:\n{lines}"


def get_all_handlers() -> dict[str, Callable[[Task], str]]:
    """Return a copy of the skill handler registry."""
    return _handlers.copy()


def list_skills() -> list[str]:
    """list all available skill IDs."""
    return list(_handlers.keys())


"""
The echo handler is an out of the box, simple handler that echoes back user messages.
It's used for testing and demonstration purposes.
"""


@register_handler("echo")
@ai_function(
    description="Echo back user messages with optional modifications",
    parameters={
        "message": {"type": "string", "description": "Message to echo back"},
        "format": {"type": "string", "description": "Format style (uppercase, lowercase, title)"},
    },
)
@rate_limited(requests_per_minute=120)
@timed()
async def handle_echo(task: Task) -> str:
    """Enhanced echo handler with formatting options."""
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

    ConversationContext.increment_message_count(task.id)
    return f"Echo: {echo_msg}"
