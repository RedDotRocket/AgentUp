"""AgentUp - A2A-compliant AI agent framework."""

__version__ = "0.2.0"

# Lazy imports to avoid loading config when using CLI
# Import these explicitly when needed:
# from agent.api.app import app, create_app, main
# from agent.config import load_config
# from agent.core import AgentExecutor, FunctionDispatcher, FunctionExecutor
# from agent.services import get_services, initialize_services
# from agent.state import ConversationManager, get_context_manager

__all__ = [
    # Main app
    "app",
    "create_app",
    "main",
    # Core
    "AgentExecutor",
    "FunctionDispatcher",
    "FunctionExecutor",
    # Config
    "load_config",
    # Services
    "get_services",
    "initialize_services",
    # State
    "ConversationManager",
    "get_context_manager",
]


def __getattr__(name):
    """Lazy import attributes to avoid loading config when using CLI."""
    if name == "app":
        from .api.app import app

        return app
    elif name == "create_app":
        from .api.app import create_app

        return create_app
    elif name == "main":
        from .api.app import main

        return main
    elif name == "load_config":
        from .config import load_config

        return load_config
    elif name == "AgentExecutor":
        from .core import AgentExecutor

        return AgentExecutor
    elif name == "FunctionDispatcher":
        from .core import FunctionDispatcher

        return FunctionDispatcher
    elif name == "FunctionExecutor":
        from .core import FunctionExecutor

        return FunctionExecutor
    elif name == "get_services":
        from .services import get_services

        return get_services
    elif name == "initialize_services":
        from .services import initialize_services

        return initialize_services
    elif name == "ConversationManager":
        from .state import ConversationManager

        return ConversationManager
    elif name == "get_context_manager":
        from .state import get_context_manager

        return get_context_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
