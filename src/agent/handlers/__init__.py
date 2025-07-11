import importlib
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

from .handlers import (  # noqa: E402
    get_all_handlers,
    get_handler,
    handle_capabilities,
    handle_echo,
    handle_status,
    list_plugins,
    register_handler,
)


# Dynamic handler discovery and import
def discover_and_import_handlers():
    """Dynamically discover and import all handler modules."""
    handlers_dir = Path(__file__).parent
    discovered_modules = []
    failed_imports = []

    logger.debug(f"Starting dynamic handler discovery in {handlers_dir}")

    # TODO: I expect there is a better way to do this,
    # this will dynamically import all Python files in the handlers directory
    # except __init__.py and handlers.py (core files)
    for py_file in handlers_dir.glob("*.py"):
        # Skip __init__.py and handlers.py (core files)
        if py_file.name in ["__init__.py", "handlers.py"]:
            continue

        module_name = py_file.stem

        try:
            # Try to import the module
            importlib.import_module(f".{module_name}", package=__name__)
            discovered_modules.append(module_name)
            logger.debug(f"Successfully imported handler module: {module_name}")

        except ImportError as e:
            failed_imports.append((module_name, f"ImportError: {e}"))
            logger.warning(f"Failed to import handler module {module_name}: {e}")
        except SyntaxError as e:
            failed_imports.append((module_name, f"SyntaxError: {e}"))
            logger.error(f"Syntax error in handler module {module_name}: {e}")
        except Exception as e:
            failed_imports.append((module_name, f"Exception: {e}"))
            logger.error(f"Unexpected error importing handler module {module_name}: {e}", exc_info=True)

    if discovered_modules:
        logger.info(f"Successfully imported {len(discovered_modules)} handler modules: {', '.join(discovered_modules)}")

    if failed_imports:
        logger.warning(f"Failed to import {len(failed_imports)} handler modules:")
        for module_name, error in failed_imports:
            logger.warning(f"  - {module_name}: {error}")

    return discovered_modules, failed_imports


# Run dynamic discovery
discovered_modules, failed_imports = discover_and_import_handlers()

# Export all public functions and handlers (core only)
__all__ = [
    # Core handler functions
    "get_handler",
    "register_handler",
    "get_all_handlers",
    "list_plugins",
    # Core handlers
    "handle_status",
    "handle_capabilities",
    "handle_echo",
]
