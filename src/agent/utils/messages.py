from datetime import datetime
from typing import Any

from a2a.types import Message, Role, Task


class MessageProcessor:
    """Advanced message processing for A2A compliance."""

    @staticmethod
    def extract_messages(task: Task) -> list[Message]:
        """Extract A2A Message objects from task."""
        # Get messages from task.history (A2A standard) or metadata (fallback)
        if hasattr(task, "history") and task.history:
            return task.history

        # Fallback to metadata for backwards compatibility
        messages_data = task.metadata.get("messages", []) if task.metadata else []
        if not messages_data:
            return []

        messages = []
        for msg in messages_data:
            if isinstance(msg, dict):
                # Convert dict to Message object
                try:
                    message = Message(
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                        timestamp=msg.get("timestamp", datetime.utcnow().isoformat()),
                    )
                    messages.append(message)
                except Exception:
                    # Fallback to dict if Message creation fails
                    messages.append(msg)
            else:
                messages.append(msg)

        return messages

    @staticmethod
    def get_latest_user_message(messages: list[Message | dict]) -> dict[str, Any] | None:
        """Get the most recent user message converted to dict format."""
        for message in reversed(messages):
            if isinstance(message, dict):
                role = message.get("role")
                if role == "user" or role == Role.user:
                    return message
            else:
                # Handle A2A Message object
                role = getattr(message, "role", None)
                if role == Role.user:
                    # Extract text content from A2A SDK parts
                    content = ""
                    if hasattr(message, "parts") and message.parts:
                        for part in message.parts:
                            if hasattr(part, "root") and hasattr(part.root, "kind"):
                                if part.root.kind == "text" and hasattr(part.root, "text"):
                                    content = part.root.text
                                    break

                    # Return dict format for backwards compatibility
                    return {"role": "user", "content": content, "message_id": getattr(message, "message_id", "unknown")}
        return None

    @staticmethod
    def get_conversation_history(messages: list[Message | dict], limit: int = 10) -> list[dict[str, Any]]:
        """Get conversation history as serializable format."""
        history = []
        for message in messages[-limit:]:
            if isinstance(message, dict):
                history.append(message)
            else:
                # Convert Message object to dict
                history.append(
                    {
                        "role": getattr(message, "role", "unknown"),
                        "content": getattr(message, "content", ""),
                        "timestamp": getattr(message, "timestamp", datetime.utcnow().isoformat()),
                    }
                )
        return history

    @staticmethod
    def create_system_message(content: str) -> dict[str, Any]:
        """Create a system message for conversation context."""
        return {"role": "system", "content": content, "timestamp": datetime.utcnow().isoformat()}

    @staticmethod
    def create_assistant_message(content: str) -> dict[str, Any]:
        """Create an assistant message for conversation context."""
        return {"role": "assistant", "content": content, "timestamp": datetime.utcnow().isoformat()}


class ConversationContext:
    """Manage conversation context and state across requests."""

    _contexts: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_context(cls, task_id: str) -> dict[str, Any]:
        """Get conversation context for a task."""
        if task_id not in cls._contexts:
            cls._contexts[task_id] = {
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "message_count": 0,
                "conversation_history": [],
                "user_preferences": {},
                "session_data": {},
            }
        return cls._contexts[task_id]

    @classmethod
    def update_context(cls, task_id: str, **kwargs) -> None:
        """Update conversation context."""
        context = cls.get_context(task_id)
        context.update(kwargs)
        context["last_activity"] = datetime.utcnow()

    @classmethod
    def increment_message_count(cls, task_id: str) -> int:
        """Increment and return message count for a conversation."""
        context = cls.get_context(task_id)
        context["message_count"] += 1
        context["last_activity"] = datetime.utcnow()
        return context["message_count"]

    @classmethod
    def get_message_count(cls, task_id: str) -> int:
        """Get current message count for a conversation."""
        context = cls.get_context(task_id)
        return context.get("message_count", 0)

    @classmethod
    def add_to_history(cls, task_id: str, role: str, content: str) -> None:
        """Add a message to conversation history."""
        context = cls.get_context(task_id)
        history = context.get("conversation_history", [])

        history.append({"role": role, "content": content, "timestamp": datetime.utcnow().isoformat()})

        # Keep only last 20 messages to prevent memory issues
        if len(history) > 20:
            history = history[-20:]

        context["conversation_history"] = history
        context["last_activity"] = datetime.utcnow()

    @classmethod
    def get_history(cls, task_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get conversation history for a task."""
        context = cls.get_context(task_id)
        history = context.get("conversation_history", [])
        return history[-limit:] if limit else history

    @classmethod
    def set_user_preference(cls, task_id: str, key: str, value: Any) -> None:
        """Set user preference for a conversation."""
        context = cls.get_context(task_id)
        preferences = context.get("user_preferences", {})
        preferences[key] = value
        context["user_preferences"] = preferences

    @classmethod
    def get_user_preference(cls, task_id: str, key: str, default: Any = None) -> Any:
        """Get user preference for a conversation."""
        context = cls.get_context(task_id)
        preferences = context.get("user_preferences", {})
        return preferences.get(key, default)

    @classmethod
    def clear_context(cls, task_id: str) -> None:
        """Clear conversation context for a task."""
        if task_id in cls._contexts:
            del cls._contexts[task_id]

    @classmethod
    def get_active_contexts(cls) -> list[str]:
        """Get list of active conversation contexts."""
        return list(cls._contexts.keys())

    @classmethod
    def cleanup_old_contexts(cls, max_age_hours: int = 24) -> int:
        """Clean up old conversation contexts."""
        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        contexts_to_remove = []

        for task_id, context in cls._contexts.items():
            last_activity = context.get("last_activity", datetime.utcnow())
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)

            if last_activity.timestamp() < cutoff_time:
                contexts_to_remove.append(task_id)

        for task_id in contexts_to_remove:
            del cls._contexts[task_id]

        return len(contexts_to_remove)


# Export utility functions
__all__ = ["MessageProcessor", "ConversationContext"]
