from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


@dataclass
class ConversationState:
    context_id: str
    user_id: str | None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    variables: dict[str, Any]
    history: list[dict[str, Any]]

    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize datetime objects to ISO format strings."""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        else:
            return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self._serialize_value(self.metadata),
            "variables": self._serialize_value(self.variables),
            "history": self._serialize_value(self.history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationState:
        return cls(
            context_id=data["context_id"],
            user_id=data.get("user_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
            variables=data.get("variables", {}),
            history=data.get("history", []),
        )


class StateStorage:
    async def get(self, context_id: str) -> ConversationState | None:
        raise NotImplementedError

    async def set(self, state: ConversationState) -> None:
        raise NotImplementedError

    async def delete(self, context_id: str) -> None:
        raise NotImplementedError

    async def list_contexts(self, user_id: str | None = None) -> list[str]:
        raise NotImplementedError


class InMemoryStorage(StateStorage):
    def __init__(self):
        self._states: dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()

    async def get(self, context_id: str) -> ConversationState | None:
        async with self._lock:
            return self._states.get(context_id)

    async def set(self, state: ConversationState) -> None:
        async with self._lock:
            self._states[state.context_id] = state

    async def delete(self, context_id: str) -> None:
        async with self._lock:
            self._states.pop(context_id, None)

    async def list_contexts(self, user_id: str | None = None) -> list[str]:
        async with self._lock:
            if user_id:
                return [ctx_id for ctx_id, state in self._states.items() if state.user_id == user_id]
            return list(self._states.keys())


class FileStorage(StateStorage):
    def __init__(self, storage_dir: str = "./conversation_states"):
        self.storage_dir = storage_dir
        import os

        os.makedirs(storage_dir, exist_ok=True)
        self._lock = asyncio.Lock()

    def _get_file_path(self, context_id: str) -> str:
        return f"{self.storage_dir}/{context_id}.json"

    async def get(self, context_id: str) -> ConversationState | None:
        async with self._lock:
            file_path = self._get_file_path(context_id)
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                return ConversationState.from_dict(data)
            except FileNotFoundError:
                return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error loading state {context_id}: {e} at line {e.lineno}, column {e.colno}")
                # Try to backup the corrupted file for debugging
                try:
                    import shutil

                    backup_path = f"{file_path}.corrupted.{int(time.time())}"
                    shutil.copy2(file_path, backup_path)
                    logger.warning(f"Backed up corrupted state file to {backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to backup corrupted state file: {e}")
                return None
            except Exception as e:
                logger.error(f"Error loading state {context_id}: {e}")
                return None

    async def set(self, state: ConversationState) -> None:
        async with self._lock:
            file_path = self._get_file_path(state.context_id)
            temp_path = f"{file_path}.tmp"

            try:
                # Write to temporary file first for atomic operation
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(state.to_dict(), f, cls=DateTimeEncoder, indent=2)
                    f.flush()  # Ensure data is written to disk
                    import os

                    os.fsync(f.fileno())  # Force write to disk

                # Atomic rename
                import os

                os.rename(temp_path, file_path)

            except Exception as e:
                logger.error(f"Error saving state {state.context_id}: {e}")
                # Clean up temp file if it exists
                try:
                    import os

                    os.remove(temp_path)
                except FileNotFoundError:
                    pass

    async def delete(self, context_id: str) -> None:
        async with self._lock:
            file_path = self._get_file_path(context_id)
            try:
                import os

                os.remove(file_path)
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.error(f"Error deleting state {context_id}: {e}")

    async def list_contexts(self, user_id: str | None = None) -> list[str]:
        async with self._lock:
            import os

            contexts = []
            try:
                for filename in os.listdir(self.storage_dir):
                    if filename.endswith(".json"):
                        context_id = filename[:-5]  # Remove .json
                        if user_id:
                            # Load state to check user_id
                            state = await self.get(context_id)
                            if state and state.user_id == user_id:
                                contexts.append(context_id)
                        else:
                            contexts.append(context_id)
            except Exception as e:
                logger.error(f"Error listing contexts: {e}")
            return contexts


class ValkeyStorage(StateStorage):
    def __init__(
        self,
        url: str = "valkey://localhost:6379",
        key_prefix: str = "agentup:state:",
        ttl: int = 3600,
    ):
        self.url = url
        self.key_prefix = key_prefix
        self.ttl = ttl
        self.client = None
        self._lock = asyncio.Lock()

    async def _get_client(self):
        if self.client is None:
            try:
                # Try to import valkey
                import valkey.asyncio as valkey

                self.client = valkey.from_url(self.url)
                # Test connection
                await self.client.ping()
                logger.info(f"Valkey storage connected to {self.url}")
            except ImportError:
                logger.warning("valkey package not available, falling back to file storage")
                # Fallback to file storage
                return None
            except Exception as e:
                logger.error(f"Failed to connect to Valkey at {self.url}: {e}")
                # Fallback to file storage
                return None
        return self.client

    def _get_key(self, context_id: str) -> str:
        return f"{self.key_prefix}{context_id}"

    async def get(self, context_id: str) -> ConversationState | None:
        async with self._lock:
            client = await self._get_client()
            if client is None:
                # Fallback to file storage
                fallback = FileStorage()
                return await fallback.get(context_id)

            try:
                key = self._get_key(context_id)
                data = await client.get(key)
                if data:
                    import json

                    data_dict = json.loads(data)
                    return ConversationState.from_dict(data_dict)
                return None
            except Exception as e:
                logger.error(f"Error getting state {context_id} from Valkey: {e}")
                return None

    async def set(self, state: ConversationState) -> None:
        async with self._lock:
            client = await self._get_client()
            if client is None:
                # Fallback to file storage
                fallback = FileStorage()
                return await fallback.set(state)

            try:
                key = self._get_key(state.context_id)
                import json

                data = json.dumps(state.to_dict())
                await client.setex(key, self.ttl, data)
            except Exception as e:
                logger.error(f"Error saving state {state.context_id} to Valkey: {e}")

    async def delete(self, context_id: str) -> None:
        async with self._lock:
            client = await self._get_client()
            if client is None:
                # Fallback to file storage
                fallback = FileStorage()
                return await fallback.delete(context_id)

            try:
                key = self._get_key(context_id)
                await client.delete(key)
            except Exception as e:
                logger.error(f"Error deleting state {context_id} from Valkey: {e}")

    async def list_contexts(self, user_id: str | None = None) -> list[str]:
        async with self._lock:
            client = await self._get_client()
            if client is None:
                # Fallback to file storage
                fallback = FileStorage()
                return await fallback.list_contexts(user_id)

            try:
                pattern = f"{self.key_prefix}*"
                keys = await client.keys(pattern)
                contexts = []

                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode("utf-8")
                    context_id = key.replace(self.key_prefix, "")

                    if user_id:
                        # Load state to check user_id
                        state = await self.get(context_id)
                        if state and state.user_id == user_id:
                            contexts.append(context_id)
                    else:
                        contexts.append(context_id)

                return contexts
            except Exception as e:
                logger.error(f"Error listing contexts from Valkey: {e}")
                return []


class ConversationContext:
    def __init__(self, storage: StateStorage | None = None):
        self.storage = storage or InMemoryStorage()

    async def get_or_create(self, context_id: str, user_id: str | None = None) -> ConversationState:
        state = await self.storage.get(context_id)

        if not state:
            state = ConversationState(
                context_id=context_id,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                metadata={},
                variables={},
                history=[],
            )
            await self.storage.set(state)

        return state

    async def update_state(self, context_id: str, **kwargs) -> None:
        state = await self.get_or_create(context_id)

        # Update fields
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)

        state.updated_at = datetime.now(timezone.utc)
        await self.storage.set(state)

    async def add_to_history(
        self, context_id: str, role: str, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        state = await self.get_or_create(context_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        state.history.append(message)

        # Limit history size to prevent unbounded growth
        if len(state.history) > 100:
            state.history = state.history[-100:]

        state.updated_at = datetime.now(timezone.utc)
        await self.storage.set(state)

    async def get_history(self, context_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        state = await self.storage.get(context_id)
        if not state:
            return []

        history = state.history
        if limit:
            history = history[-limit:]

        return history

    async def set_variable(self, context_id: str, key: str, value: Any) -> None:
        state = await self.get_or_create(context_id)
        state.variables[key] = value
        state.updated_at = datetime.now(timezone.utc)
        await self.storage.set(state)

    async def get_variable(self, context_id: str, key: str, default: Any = None) -> Any:
        state = await self.storage.get(context_id)
        if not state:
            return default
        return state.variables.get(key, default)

    async def set_metadata(self, context_id: str, key: str, value: Any) -> None:
        state = await self.get_or_create(context_id)
        state.metadata[key] = value
        state.updated_at = datetime.now(timezone.utc)
        await self.storage.set(state)

    async def get_metadata(self, context_id: str, key: str, default: Any = None) -> Any:
        state = await self.storage.get(context_id)
        if not state:
            return default
        return state.metadata.get(key, default)

    async def clear_context(self, context_id: str) -> None:
        await self.storage.delete(context_id)

    async def cleanup_old_contexts(self, max_age_hours: int = 24) -> int:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cleaned = 0

        for context_id in await self.storage.list_contexts():
            state = await self.storage.get(context_id)
            if state and state.updated_at < cutoff_time:
                await self.storage.delete(context_id)
                cleaned += 1

        return cleaned


# Global context manager
_context_manager: ConversationContext | None = None


def get_context_manager(storage_type: str = "memory", **kwargs) -> ConversationContext:
    global _context_manager

    # For testing or when force_new is True, create a new instance
    force_new = kwargs.pop("force_new", False)

    if _context_manager is None or force_new:
        if storage_type == "memory":
            storage = InMemoryStorage()
        elif storage_type == "file":
            storage = FileStorage(**kwargs)
        elif storage_type == "valkey":
            storage = ValkeyStorage(**kwargs)
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")

        if force_new:
            return ConversationContext(storage)
        else:
            _context_manager = ConversationContext(storage)

    return _context_manager


# Decorator for handlers that need state management
def stateful(storage: str = "memory", **storage_kwargs):
    def decorator(func):
        async def wrapper(task, *args, **kwargs):
            # Get context manager
            context = get_context_manager(storage, **storage_kwargs)

            # Extract context ID from task
            context_id = getattr(task, "context_id", None) or task.id

            # Add context to kwargs
            kwargs["context"] = context
            kwargs["context_id"] = context_id

            # Call original function
            return await func(task, *args, **kwargs)

        return wrapper

    return decorator


# Export classes and functions
__all__ = [
    "ConversationState",
    "StateStorage",
    "InMemoryStorage",
    "FileStorage",
    "ValkeyStorage",
    "ConversationContext",
    "get_context_manager",
    "stateful",
]
