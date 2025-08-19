import importlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

from a2a.types import Task


def load_callable(path: str | None) -> Callable[..., Any] | None:
    """
    Given "some.module:func", import and return the func,
    or return None if path is falsy or import fails.
    """
    if not path:
        return None
    module_name, func_name = path.split(":")
    try:
        module = importlib.import_module(module_name)
        return getattr(module, func_name)
    except (ImportError, AttributeError):
        return None


class TaskValidator:
    @staticmethod
    def validate_task(task: Task) -> list[str]:
        errors = []

        # Check required fields
        if not task.id:
            errors.append("Task ID is required")

        # Check task metadata structure
        if task.metadata is not None and not isinstance(task.metadata, dict):
            errors.append("Task metadata must be a dictionary")

        # Validate history if present
        if hasattr(task, "history") and task.history:
            for i, entry in enumerate(task.history):
                if not hasattr(entry, "parts") or not entry.parts:
                    errors.append(f"History entry {i} missing parts")

        return errors

    @staticmethod
    def is_valid_task(task: Task) -> bool:
        return len(TaskValidator.validate_task(task)) == 0


def extract_parameter(text: str, param_name: str) -> str | None:
    import re

    # Pattern for "param_name: value" or "param_name = value"
    pattern = rf"{re.escape(param_name)}\s*[:=]\s*([^,\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip().strip("\"'")
    return None


def format_response(content: str, format_type: str = "plain") -> str:
    if format_type == "markdown":
        # Simple markdown formatting
        content = content.replace("\n\n", "\n\n---\n\n")
    elif format_type == "json":
        import json

        try:
            # Try to parse and pretty-format JSON
            data = json.loads(content)
            content = json.dumps(data, indent=2)
        except json.JSONDecodeError:
            # If not JSON, wrap in JSON structure
            content = json.dumps({"response": content}, indent=2)
    elif format_type == "html":
        # Basic HTML escaping
        content = content.replace("&", "&amp;")
        content = content.replace("<", "&lt;")
        content = content.replace(">", "&gt;")
        content = content.replace("\n", "<br>")

    return content


def sanitize_input(text: str) -> str:
    # Remove potentially dangerous characters
    text = text.replace("<script", "&lt;script")
    text = text.replace("</script>", "&lt;/script&gt;")
    text = text.replace("javascript:", "")
    text = text.replace("data:", "")

    # Limit length
    if len(text) > 10000:
        text = text[:10000] + "... [truncated]"

    return text


def generate_task_id() -> str:
    import uuid

    return str(uuid.uuid4())


def get_timestamp() -> str:
    return datetime.utcnow().isoformat()


# Export utility functions
__all__ = [
    "TaskValidator",
    "extract_parameter",
    "format_response",
    "sanitize_input",
    "generate_task_id",
    "get_timestamp",
]
