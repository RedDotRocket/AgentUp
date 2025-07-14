import importlib
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

from .executors import (  # noqa: E402
    execute_capabilities,
    execute_status,
    get_all_capabilities,
    get_capability_executor,
    list_capabilities,
    register_capability,
)


# Dynamic capability discovery and import
def discover_and_import_capabilities():
    """Dynamically discover and import all capability modules."""
    capabilities_dir = Path(__file__).parent
    discovered_modules = []
    failed_imports = []

    logger.debug(f"Starting dynamic capability discovery in {capabilities_dir}")

    # TODO: I expect there is a better way to do this,
    # this will dynamically import all Python files in the capabilities directory
    # except __init__.py and executors.py (core files)
    for py_file in capabilities_dir.glob("*.py"):
        # Skip __init__.py and executors.py (core files)
        if py_file.name in ["__init__.py", "executors.py"]:
            continue

        module_name = py_file.stem

        try:
            # Try to import the module
            importlib.import_module(f".{module_name}", package=__name__)
            discovered_modules.append(module_name)
            logger.debug(f"Successfully imported capability module: {module_name}")

        except ImportError as e:
            failed_imports.append((module_name, f"ImportError: {e}"))
            logger.warning(f"Failed to import capability module {module_name}: {e}")
        except SyntaxError as e:
            failed_imports.append((module_name, f"SyntaxError: {e}"))
            logger.error(f"Syntax error in capability module {module_name}: {e}")
        except Exception as e:
            failed_imports.append((module_name, f"Exception: {e}"))
            logger.error(f"Unexpected error importing capability module {module_name}: {e}", exc_info=True)

    if discovered_modules:
        logger.info(
            f"Successfully imported {len(discovered_modules)} capability modules: {', '.join(discovered_modules)}"
        )

    if failed_imports:
        logger.warning(f"Failed to import {len(failed_imports)} capability modules:")
        for module_name, error in failed_imports:
            logger.warning(f"  - {module_name}: {error}")

    return discovered_modules, failed_imports


# Run dynamic discovery
discovered_modules, failed_imports = discover_and_import_capabilities()

# Export all public functions and capabilities (core only)
__all__ = [
    # Core capability functions
    "get_capability_executor",
    "register_capability",
    "get_all_capabilities",
    "list_capabilities",
    # Core capabilities
    "execute_status",
    "execute_capabilities",
]
