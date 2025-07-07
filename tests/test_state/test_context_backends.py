import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.state.context import (
    ConversationContext,
    ConversationState,
    FileStorage,
    InMemoryStorage,
    ValkeyStorage,
    get_context_manager,
)


class TestMemoryStorageBackend:
    """Test memory-based storage backend."""

    def test_memory_storage_initialization(self):
        """Test memory storage initialization."""
        storage = InMemoryStorage()
        assert storage._states == {}

    @pytest.mark.asyncio
    async def test_memory_storage_set_and_get(self):
        """Test setting and getting state in memory storage."""
        storage = InMemoryStorage()

        # Create test state
        state = ConversationState(
            context_id="test-context",
            user_id="user-123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={"key": "value"},
            variables={"preference": "dark_mode"},
            history=[],
        )

        # Set state
        await storage.set(state)

        # Get state
        retrieved_state = await storage.get("test-context")
        assert retrieved_state is not None
        assert retrieved_state.context_id == "test-context"
        assert retrieved_state.user_id == "user-123"
        assert retrieved_state.variables["preference"] == "dark_mode"

    @pytest.mark.asyncio
    async def test_memory_storage_get_nonexistent(self):
        """Test getting non-existent state returns None."""
        storage = InMemoryStorage()

        result = await storage.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_storage_delete(self):
        """Test deleting state from memory storage."""
        storage = InMemoryStorage()

        # Create and set test state
        state = ConversationState(
            context_id="test-context",
            user_id="user-123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            variables={},
            history=[],
        )
        await storage.set(state)

        # Verify state exists
        assert await storage.get("test-context") is not None

        # Delete state
        await storage.delete("test-context")

        # Verify state is gone
        assert await storage.get("test-context") is None

    @pytest.mark.asyncio
    async def test_memory_storage_list_contexts(self):
        """Test listing contexts in memory storage."""
        storage = InMemoryStorage()

        # Create multiple states
        state1 = ConversationState(
            context_id="context1",
            user_id="user-123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            variables={},
            history=[],
        )
        state2 = ConversationState(
            context_id="context2",
            user_id="user-456",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            variables={},
            history=[],
        )

        await storage.set(state1)
        await storage.set(state2)

        # List all contexts
        all_contexts = await storage.list_contexts()
        assert len(all_contexts) == 2
        assert "context1" in all_contexts
        assert "context2" in all_contexts

        # List contexts for specific user
        user_contexts = await storage.list_contexts(user_id="user-123")
        assert len(user_contexts) == 1
        assert "context1" in user_contexts


class TestFileStorageBackend:
    """Test file-based storage backend."""

    def test_file_storage_initialization(self):
        """Test file storage initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = FileStorage(storage_dir=tmp_dir)
            assert storage.storage_dir == tmp_dir
            assert Path(tmp_dir).exists()

    @pytest.mark.asyncio
    async def test_file_storage_set_and_get(self):
        """Test setting and getting state in file storage."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = FileStorage(storage_dir=tmp_dir)

            # Create test state
            state = ConversationState(
                context_id="test-context",
                user_id="user-123",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={"key": "value"},
                variables={"preference": "dark_mode"},
                history=[],
            )

            # Set state
            await storage.set(state)

            # Verify file was created
            file_path = Path(tmp_dir) / "test-context.json"
            assert file_path.exists()

            # Get state
            retrieved_state = await storage.get("test-context")
            assert retrieved_state is not None
            assert retrieved_state.context_id == "test-context"
            assert retrieved_state.user_id == "user-123"
            assert retrieved_state.variables["preference"] == "dark_mode"

    @pytest.mark.asyncio
    async def test_file_storage_persistence(self):
        """Test that file storage persists across instances."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create first storage instance
            storage1 = FileStorage(storage_dir=tmp_dir)

            state = ConversationState(
                context_id="persistent-context",
                user_id="user-123",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={},
                variables={"persisted": True},
                history=[],
            )
            await storage1.set(state)

            # Create second storage instance
            storage2 = FileStorage(storage_dir=tmp_dir)
            retrieved_state = await storage2.get("persistent-context")

            # Verify data persisted
            assert retrieved_state is not None
            assert retrieved_state.variables["persisted"] is True

    @pytest.mark.asyncio
    async def test_file_storage_delete(self):
        """Test deleting state from file storage."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = FileStorage(storage_dir=tmp_dir)

            # Create and set test state
            state = ConversationState(
                context_id="test-context",
                user_id="user-123",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={},
                variables={},
                history=[],
            )
            await storage.set(state)

            # Verify file exists
            file_path = Path(tmp_dir) / "test-context.json"
            assert file_path.exists()

            # Delete state
            await storage.delete("test-context")

            # Verify file is gone
            assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_file_storage_corrupted_file(self):
        """Test handling corrupted state file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = FileStorage(storage_dir=tmp_dir)

            # Create a corrupted file
            file_path = Path(tmp_dir) / "corrupted-context.json"
            file_path.write_text("invalid json content")

            # Try to get state (should handle corruption gracefully)
            result = await storage.get("corrupted-context")
            assert result is None


class TestValkeyStorageBackend:
    """Test Valkey/Redis-based storage backend."""

    def test_valkey_storage_initialization(self):
        """Test Valkey storage initialization."""
        storage = ValkeyStorage(url="valkey://localhost:6379", key_prefix="test:")
        assert storage.url == "valkey://localhost:6379"
        assert storage.key_prefix == "test:"

    @pytest.mark.asyncio
    async def test_valkey_storage_set_and_get(self):
        """Test setting and getting state in Valkey storage."""
        with patch("valkey.asyncio.from_url") as mock_valkey:
            mock_client = AsyncMock()
            mock_valkey.return_value = mock_client

            # Mock successful ping
            mock_client.ping.return_value = True

            # Mock get to return serialized state
            state_data = {
                "context_id": "test-context",
                "user_id": "user-123",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {"key": "value"},
                "variables": {"preference": "dark_mode"},
                "history": [],
            }
            mock_client.get.return_value = json.dumps(state_data)
            mock_client.setex.return_value = True

            storage = ValkeyStorage(url="valkey://localhost:6379", key_prefix="test:", ttl=3600)

            # Create test state
            state = ConversationState(
                context_id="test-context",
                user_id="user-123",
                created_at=datetime.fromisoformat("2023-01-01T00:00:00"),
                updated_at=datetime.fromisoformat("2023-01-01T00:00:00"),
                metadata={"key": "value"},
                variables={"preference": "dark_mode"},
                history=[],
            )

            # Set state
            await storage.set(state)

            # Verify setex was called correctly
            mock_client.setex.assert_called_once()
            args = mock_client.setex.call_args[0]
            assert args[0] == "test:test-context"  # key
            assert args[1] == 3600  # ttl

            # Get state
            retrieved_state = await storage.get("test-context")
            assert retrieved_state is not None
            assert retrieved_state.context_id == "test-context"
            assert retrieved_state.user_id == "user-123"

    @pytest.mark.asyncio
    async def test_valkey_storage_connection_failure(self):
        """Test Valkey storage fallback when connection fails."""
        with patch("valkey.asyncio.from_url") as mock_valkey:
            # Mock connection failure
            mock_valkey.side_effect = Exception("Connection failed")

            storage = ValkeyStorage(url="valkey://localhost:6379")

            # Create test state
            state = ConversationState(
                context_id="test-context",
                user_id="user-123",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={},
                variables={},
                history=[],
            )

            # Mock FileStorage fallback
            with patch("src.agent.state.context.FileStorage") as mock_file_storage:
                mock_file_instance = AsyncMock()
                mock_file_storage.return_value = mock_file_instance

                # Set state (should fallback to file storage)
                await storage.set(state)

                # Verify fallback was used
                mock_file_instance.set.assert_called_once_with(state)

    @pytest.mark.asyncio
    async def test_valkey_storage_delete(self):
        """Test deleting state from Valkey storage."""
        with patch("valkey.asyncio.from_url") as mock_valkey:
            mock_client = AsyncMock()
            mock_valkey.return_value = mock_client
            mock_client.ping.return_value = True
            mock_client.delete.return_value = 1

            storage = ValkeyStorage(url="valkey://localhost:6379", key_prefix="test:")

            # Delete state
            await storage.delete("test-context")

            # Verify delete was called
            mock_client.delete.assert_called_once_with("test:test-context")


class TestConversationContext:
    """Test conversation context management."""

    @pytest.mark.asyncio
    async def test_conversation_context_get_or_create_new(self):
        """Test creating new conversation context."""
        storage = InMemoryStorage()
        context = ConversationContext(storage)

        # Get or create new context
        state = await context.get_or_create("new-context", user_id="user-123")

        assert state.context_id == "new-context"
        assert state.user_id == "user-123"
        assert state.variables == {}
        assert state.history == []

    @pytest.mark.asyncio
    async def test_conversation_context_get_existing(self):
        """Test getting existing conversation context."""
        storage = InMemoryStorage()
        context = ConversationContext(storage)

        # Create initial state
        initial_state = await context.get_or_create("existing-context", user_id="user-123")
        initial_state.variables["test"] = "value"
        await storage.set(initial_state)

        # Get existing context
        retrieved_state = await context.get_or_create("existing-context")

        assert retrieved_state.context_id == "existing-context"
        assert retrieved_state.variables["test"] == "value"

    @pytest.mark.asyncio
    async def test_conversation_context_set_and_get_variable(self):
        """Test setting and getting variables through context."""
        storage = InMemoryStorage()
        context = ConversationContext(storage)

        # Set variable
        await context.set_variable("test-context", "preference", "dark_mode")

        # Get variable
        result = await context.get_variable("test-context", "preference")
        assert result == "dark_mode"

        # Get non-existent variable with default
        result = await context.get_variable("test-context", "nonexistent", "default")
        assert result == "default"

    @pytest.mark.asyncio
    async def test_conversation_context_add_and_get_history(self):
        """Test adding and getting history through context."""
        storage = InMemoryStorage()
        context = ConversationContext(storage)

        # Add history entries
        await context.add_to_history("test-context", "user", "Hello", {"timestamp": "2023-01-01"})
        await context.add_to_history("test-context", "agent", "Hi there", {"timestamp": "2023-01-02"})

        # Get history
        history = await context.get_history("test-context")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "agent"
        assert history[1]["content"] == "Hi there"

        # Get limited history
        limited_history = await context.get_history("test-context", limit=1)
        assert len(limited_history) == 1
        assert limited_history[0]["role"] == "agent"  # Most recent

    @pytest.mark.asyncio
    async def test_conversation_context_clear(self):
        """Test clearing conversation context."""
        storage = InMemoryStorage()
        context = ConversationContext(storage)

        # Add some data
        await context.set_variable("test-context", "key", "value")
        await context.add_to_history("test-context", "user", "Hello", {})

        # Verify data exists
        variable = await context.get_variable("test-context", "key")
        history = await context.get_history("test-context")
        assert variable == "value"
        assert len(history) == 1

        # Clear context
        await context.clear_context("test-context")

        # Verify data is cleared
        variable = await context.get_variable("test-context", "key", "default")
        history = await context.get_history("test-context")
        assert variable == "default"
        assert len(history) == 0


class TestContextManagerFactory:
    """Test context manager factory function."""

    def test_get_context_manager_memory(self):
        """Test getting memory context manager."""
        context = get_context_manager("memory", force_new=True)
        assert isinstance(context, ConversationContext)
        assert isinstance(context.storage, InMemoryStorage)

    def test_get_context_manager_file(self):
        """Test getting file context manager."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            context = get_context_manager("file", storage_dir=tmp_dir, force_new=True)
            assert isinstance(context, ConversationContext)
            assert isinstance(context.storage, FileStorage)
            assert context.storage.storage_dir == tmp_dir

    def test_get_context_manager_valkey(self):
        """Test getting Valkey context manager."""
        context = get_context_manager("valkey", url="valkey://localhost:6379", key_prefix="test:", force_new=True)
        assert isinstance(context, ConversationContext)
        assert isinstance(context.storage, ValkeyStorage)
        assert context.storage.url == "valkey://localhost:6379"
        assert context.storage.key_prefix == "test:"

    def test_get_context_manager_invalid_backend(self):
        """Test getting context manager with invalid backend."""
        with pytest.raises(ValueError, match="Unknown storage type"):
            get_context_manager("invalid_backend", force_new=True)

    def test_get_context_manager_file_default_storage_dir(self):
        """Test getting file context manager with default storage directory."""
        context = get_context_manager("file", force_new=True)
        assert isinstance(context, ConversationContext)
        assert isinstance(context.storage, FileStorage)
        assert context.storage.storage_dir == "./conversation_states"


class TestConversationStateModel:
    """Test ConversationState data model."""

    def test_conversation_state_to_dict(self):
        """Test converting conversation state to dictionary."""
        created_at = datetime.utcnow()
        updated_at = datetime.utcnow()

        state = ConversationState(
            context_id="test-context",
            user_id="user-123",
            created_at=created_at,
            updated_at=updated_at,
            metadata={"key": "value"},
            variables={"preference": "dark_mode"},
            history=[{"role": "user", "content": "Hello"}],
        )

        data = state.to_dict()

        assert data["context_id"] == "test-context"
        assert data["user_id"] == "user-123"
        assert data["created_at"] == created_at.isoformat()
        assert data["updated_at"] == updated_at.isoformat()
        assert data["metadata"] == {"key": "value"}
        assert data["variables"] == {"preference": "dark_mode"}
        assert data["history"] == [{"role": "user", "content": "Hello"}]

    def test_conversation_state_from_dict(self):
        """Test creating conversation state from dictionary."""
        data = {
            "context_id": "test-context",
            "user_id": "user-123",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T01:00:00",
            "metadata": {"key": "value"},
            "variables": {"preference": "dark_mode"},
            "history": [{"role": "user", "content": "Hello"}],
        }

        state = ConversationState.from_dict(data)

        assert state.context_id == "test-context"
        assert state.user_id == "user-123"
        assert state.created_at == datetime.fromisoformat("2023-01-01T00:00:00")
        assert state.updated_at == datetime.fromisoformat("2023-01-01T01:00:00")
        assert state.metadata == {"key": "value"}
        assert state.variables == {"preference": "dark_mode"}
        assert state.history == [{"role": "user", "content": "Hello"}]


class TestIntegrationScenarios:
    """Test integration scenarios across different backends."""

    @pytest.mark.asyncio
    async def test_full_conversation_workflow(self):
        """Test complete conversation workflow with state management."""
        storage = InMemoryStorage()
        context = ConversationContext(storage)

        # Simulate a conversation
        context_id = "conversation-123"
        _user_id = "user-456"

        # User starts conversation
        await context.add_to_history(
            context_id, "user", "Hello, my name is Alice", {"timestamp": "2023-01-01T10:00:00"}
        )
        await context.set_variable(context_id, "user_name", "Alice")

        # Agent responds
        await context.add_to_history(
            context_id, "agent", "Hello Alice! Nice to meet you.", {"timestamp": "2023-01-01T10:00:05"}
        )

        # User asks about preferences
        await context.add_to_history(context_id, "user", "I prefer dark mode", {"timestamp": "2023-01-01T10:01:00"})
        await context.set_variable(context_id, "theme_preference", "dark")

        # Agent acknowledges
        await context.add_to_history(
            context_id, "agent", "I'll remember you prefer dark mode", {"timestamp": "2023-01-01T10:01:05"}
        )

        # Verify conversation state
        user_name = await context.get_variable(context_id, "user_name")
        theme_pref = await context.get_variable(context_id, "theme_preference")
        history = await context.get_history(context_id)

        assert user_name == "Alice"
        assert theme_pref == "dark"
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello, my name is Alice"
        assert history[-1]["role"] == "agent"
        assert history[-1]["content"] == "I'll remember you prefer dark mode"

    @pytest.mark.asyncio
    async def test_cross_backend_consistency(self):
        """Test data consistency across different storage backends."""
        # Test data
        context_id = "consistency-test"
        test_variables = {"user_name": "Bob", "preference": "light_mode"}
        test_history = [
            {"role": "user", "content": "Hello", "metadata": {"timestamp": "2023-01-01"}},
            {"role": "agent", "content": "Hi there", "metadata": {"timestamp": "2023-01-02"}},
        ]

        # Test memory backend
        memory_storage = InMemoryStorage()
        memory_context = ConversationContext(memory_storage)

        for key, value in test_variables.items():
            await memory_context.set_variable(context_id, key, value)

        for entry in test_history:
            await memory_context.add_to_history(context_id, entry["role"], entry["content"], entry["metadata"])

        # Verify memory backend
        memory_vars = {}
        for key in test_variables:
            memory_vars[key] = await memory_context.get_variable(context_id, key)
        memory_history = await memory_context.get_history(context_id)

        assert memory_vars == test_variables
        assert len(memory_history) == len(test_history)

        # Test file backend
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_storage = FileStorage(storage_dir=tmp_dir)
            file_context = ConversationContext(file_storage)

            for key, value in test_variables.items():
                await file_context.set_variable(context_id, key, value)

            for entry in test_history:
                await file_context.add_to_history(context_id, entry["role"], entry["content"], entry["metadata"])

            # Verify file backend
            file_vars = {}
            for key in test_variables:
                file_vars[key] = await file_context.get_variable(context_id, key)
            file_history = await file_context.get_history(context_id)

            assert file_vars == test_variables
            assert len(file_history) == len(test_history)

            # Verify consistency between backends
            assert memory_vars == file_vars
            assert len(memory_history) == len(file_history)
