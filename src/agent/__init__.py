import warnings

# Suppress a2a-sdk deprecation warnings for camelCase field aliases
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r"Setting field .* via its camelCase alias is deprecated.*",
    module=r"a2a\..*",
)

__version__ = "0.4.0"

# Lazy imports to avoid loading config when using CLI
# Import these explicitly when needed:
# from agent.api.app import app, create_app, main
# from agent.config import Config
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
    "Config",
    # Services
    "get_services",
    "initialize_services",
    # State
    "ConversationManager",
    "get_context_manager",
]


def __getattr__(name):
    if name == "app":
        from .api.app import app

        return app
    elif name == "create_app":
        from .api.app import create_app

        return create_app
    elif name == "main":
        from .api.app import main

        return main
    elif name == "Config":
        from .config import Config

        return Config
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
