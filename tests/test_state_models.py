"""
Tests for AgentUp state management models.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from agent.state.model import (
    ConversationMessage,
    ConversationRole,
    ConversationState,
    StateBackendConfig,
    StateBackendType,
    StateConfig,
    StateMetrics,
    StateOperation,
    StateOperationType,
    StateVariable,
    StateVariableType,
)


class TestStateVariable:
    """Test StateVariable model."""

    def test_string_state_variable(self):
        """Test string state variable."""
        var = StateVariable[str](
            key="user_name", value="John Doe", type_name=StateVariableType.STRING, description="User's full name"
        )

        assert var.key == "user_name"
        assert var.value == "John Doe"
        assert var.type_name == StateVariableType.STRING
        assert var.version == 1
        assert not var.is_expired

    def test_integer_state_variable(self):
        """Test integer state variable."""
        var = StateVariable[int](
            key="user_age",
            value=25,
            type_name=StateVariableType.INTEGER,
            ttl=3600,  # 1 hour
        )

        assert var.key == "user_age"
        assert var.value == 25
        assert var.type_name == StateVariableType.INTEGER
        assert var.ttl == 3600

    def test_dict_state_variable(self):
        """Test dictionary state variable."""
        config_data = {"theme": "dark", "notifications": True}
        var = StateVariable[dict](
            key="user_config", value=config_data, type_name=StateVariableType.DICT, tags=["config", "user"]
        )

        assert var.key == "user_config"
        assert var.value["theme"] == "dark"
        assert var.value["notifications"] is True
        assert "config" in var.tags

    def test_key_validation(self):
        """Test state variable key validation."""
        # Valid keys
        StateVariable(key="valid_key", value="test", type_name=StateVariableType.STRING)
        StateVariable(key="valid.key", value="test", type_name=StateVariableType.STRING)
        StateVariable(key="valid-key", value="test", type_name=StateVariableType.STRING)
        StateVariable(key="valid123", value="test", type_name=StateVariableType.STRING)

        # Invalid keys
        with pytest.raises(ValidationError):
            StateVariable(key="", value="test", type_name=StateVariableType.STRING)

        with pytest.raises(ValidationError):
            StateVariable(key="invalid key!", value="test", type_name=StateVariableType.STRING)

        with pytest.raises(ValidationError):
            StateVariable(key="a" * 257, value="test", type_name=StateVariableType.STRING)  # Too long

    def test_ttl_validation(self):
        """Test TTL validation."""
        # Valid TTL
        StateVariable(key="test", value="test", type_name=StateVariableType.STRING, ttl=3600)
        StateVariable(key="test", value="test", type_name=StateVariableType.STRING, ttl=None)

        # Invalid TTL
        with pytest.raises(ValidationError):
            StateVariable(key="test", value="test", type_name=StateVariableType.STRING, ttl=0)

        with pytest.raises(ValidationError):
            StateVariable(key="test", value="test", type_name=StateVariableType.STRING, ttl=-1)

    def test_expiration_checking(self):
        """Test variable expiration."""
        # Non-expiring variable
        var = StateVariable(key="test", value="test", type_name=StateVariableType.STRING)
        assert not var.is_expired

        # Expired variable
        past_time = datetime.utcnow() - timedelta(seconds=10)
        expired_var = StateVariable(
            key="test",
            value="test",
            type_name=StateVariableType.STRING,
            ttl=5,  # 5 seconds
            updated_at=past_time,
        )
        assert expired_var.is_expired

        # Not yet expired
        recent_time = datetime.utcnow() - timedelta(seconds=1)
        fresh_var = StateVariable(
            key="test", value="test", type_name=StateVariableType.STRING, ttl=10, updated_at=recent_time
        )
        assert not fresh_var.is_expired

    def test_touch_method(self):
        """Test the touch method for updating timestamps."""
        var = StateVariable(key="test", value="test", type_name=StateVariableType.STRING)
        original_version = var.version
        original_time = var.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        var.touch()

        assert var.version == original_version + 1
        assert var.updated_at > original_time


class TestConversationMessage:
    """Test ConversationMessage model."""

    def test_basic_message_creation(self):
        """Test creating basic messages."""
        message = ConversationMessage(id="msg_123", role=ConversationRole.USER, content="Hello, how are you?", tokens=5)

        assert message.id == "msg_123"
        assert message.role == ConversationRole.USER
        assert message.content == "Hello, how are you?"
        assert message.tokens == 5
        assert isinstance(message.timestamp, datetime)

    def test_function_message(self):
        """Test function call message."""
        message = ConversationMessage(
            id="msg_func",
            role=ConversationRole.FUNCTION,
            content="Function result",
            function_name="get_weather",
            function_call={"location": "New York", "units": "celsius"},
        )

        assert message.role == ConversationRole.FUNCTION
        assert message.function_name == "get_weather"
        assert message.function_call["location"] == "New York"

    def test_tool_calls_message(self):
        """Test message with tool calls."""
        message = ConversationMessage(
            id="msg_tool",
            role=ConversationRole.ASSISTANT,
            content="I'll help you with that.",
            tool_calls=[
                {"tool": "calculator", "operation": "add", "args": [2, 3]},
                {"tool": "search", "query": "weather today"},
            ],
        )

        assert len(message.tool_calls) == 2
        assert message.tool_calls[0]["tool"] == "calculator"
        assert message.tool_calls[1]["tool"] == "search"

    def test_threaded_message(self):
        """Test message with threading."""
        message = ConversationMessage(
            id="msg_reply",
            role=ConversationRole.USER,
            content="Thanks for the help!",
            reply_to="msg_assistant",
            thread_id="thread_123",
        )

        assert message.reply_to == "msg_assistant"
        assert message.thread_id == "thread_123"

    def test_content_validation(self):
        """Test message content validation."""
        # Valid content
        ConversationMessage(id="test", role=ConversationRole.USER, content="Normal message")

        # Too large content
        large_content = "x" * (1_000_001)  # Over 1MB
        with pytest.raises(ValidationError) as exc_info:
            ConversationMessage(id="test", role=ConversationRole.USER, content=large_content)
        assert "too large" in str(exc_info.value)

    def test_message_id_validation(self):
        """Test message ID validation."""
        # Valid IDs
        ConversationMessage(id="msg_123", role=ConversationRole.USER, content="test")
        ConversationMessage(id="a", role=ConversationRole.USER, content="test")  # Minimum
        ConversationMessage(id="x" * 128, role=ConversationRole.USER, content="test")  # Maximum

        # Invalid IDs
        with pytest.raises(ValidationError):
            ConversationMessage(id="", role=ConversationRole.USER, content="test")

        with pytest.raises(ValidationError):
            ConversationMessage(id="x" * 129, role=ConversationRole.USER, content="test")  # Too long


class TestConversationState:
    """Test ConversationState model."""

    def test_basic_conversation_state(self):
        """Test basic conversation state creation."""
        state = ConversationState(context_id="conv_123", user_id="user_456", session_id="session_789")

        assert state.context_id == "conv_123"
        assert state.user_id == "user_456"
        assert state.session_id == "session_789"
        assert len(state.variables) == 0
        assert len(state.history) == 0
        assert state.max_history_size == 100
        assert state.auto_summarize is True

    def test_add_message(self):
        """Test adding messages to conversation."""
        state = ConversationState(context_id="test")

        message1 = ConversationMessage(id="msg1", role=ConversationRole.USER, content="Hello")
        message2 = ConversationMessage(id="msg2", role=ConversationRole.ASSISTANT, content="Hi there!")

        state.add_message(message1)
        state.add_message(message2)

        assert len(state.history) == 2
        assert state.history[0].id == "msg1"
        assert state.history[1].id == "msg2"
        assert state.last_activity > state.created_at

    def test_message_history_limit(self):
        """Test message history size limiting."""
        state = ConversationState(context_id="test", max_history_size=3)

        # Add more messages than the limit
        for i in range(5):
            message = ConversationMessage(id=f"msg{i}", role=ConversationRole.USER, content=f"Message {i}")
            state.add_message(message)

        # Should only keep the last 3 messages (or half when auto-summarizing)
        assert len(state.history) <= 3
        assert state.archived_messages > 0

    def test_set_and_get_variable(self):
        """Test setting and getting state variables."""
        state = ConversationState(context_id="test")

        # Set variables
        state.set_variable("user_name", "John", ttl=3600)
        state.set_variable("user_age", 25)
        state.set_variable("preferences", {"theme": "dark"})

        # Get variables
        assert state.get_variable("user_name") == "John"
        assert state.get_variable("user_age") == 25
        assert state.get_variable("preferences")["theme"] == "dark"
        assert state.get_variable("nonexistent", "default") == "default"

        # Check variable objects
        assert len(state.variables) == 3
        assert state.variables["user_name"].ttl == 3600
        assert state.variables["user_age"].ttl is None

    def test_variable_count_limit(self):
        """Test variable count limiting."""
        state = ConversationState(context_id="test", max_variable_count=2)

        # Set variables up to limit
        state.set_variable("var1", "value1")
        state.set_variable("var2", "value2")

        # Exceeding limit should raise error
        with pytest.raises(ValueError) as exc_info:
            state.set_variable("var3", "value3")
        assert "Maximum variable count" in str(exc_info.value)

        # Updating existing variable should work
        state.set_variable("var1", "new_value1")
        assert state.get_variable("var1") == "new_value1"

    def test_delete_variable(self):
        """Test deleting state variables."""
        state = ConversationState(context_id="test")

        state.set_variable("test_var", "test_value")
        assert state.get_variable("test_var") == "test_value"

        # Delete existing variable
        result = state.delete_variable("test_var")
        assert result is True
        assert state.get_variable("test_var") is None

        # Delete non-existent variable
        result = state.delete_variable("nonexistent")
        assert result is False

    def test_cleanup_expired_variables(self):
        """Test cleaning up expired variables."""
        state = ConversationState(context_id="test")

        # Set variables with different TTLs
        past_time = datetime.utcnow() - timedelta(seconds=10)

        # Create expired variable manually
        expired_var = StateVariable(
            key="expired", value="old_value", type_name=StateVariableType.STRING, ttl=5, updated_at=past_time
        )
        state.variables["expired"] = expired_var

        # Create fresh variable
        state.set_variable("fresh", "new_value", ttl=3600)

        # Cleanup expired variables
        removed_count = state.cleanup_expired_variables()

        assert removed_count == 1
        assert "expired" not in state.variables
        assert "fresh" in state.variables

    def test_summary_stats(self):
        """Test conversation summary statistics."""
        state = ConversationState(context_id="test")

        # Add some messages
        messages = [
            ConversationMessage(id="1", role=ConversationRole.USER, content="Hello", tokens=2),
            ConversationMessage(id="2", role=ConversationRole.ASSISTANT, content="Hi!", tokens=1),
            ConversationMessage(id="3", role=ConversationRole.USER, content="How are you?", tokens=3),
            ConversationMessage(id="4", role=ConversationRole.ASSISTANT, content="I'm good!", tokens=2),
        ]

        for msg in messages:
            state.add_message(msg)

        # Add some tags
        state.tags = ["greeting", "casual"]

        # Get summary
        summary = state.get_summary_stats()

        assert summary.total_messages == 4
        assert summary.user_messages == 2
        assert summary.assistant_messages == 2
        assert summary.total_tokens == 8
        assert summary.first_message_at == messages[0].timestamp
        assert summary.last_message_at == messages[-1].timestamp
        assert summary.topics == ["greeting", "casual"]

    def test_context_id_validation(self):
        """Test context ID validation."""
        # Valid IDs
        ConversationState(context_id="conv_123")
        ConversationState(context_id="a")  # Minimum
        ConversationState(context_id="x" * 128)  # Maximum

        # Invalid IDs
        with pytest.raises(ValidationError):
            ConversationState(context_id="")

        with pytest.raises(ValidationError):
            ConversationState(context_id="x" * 129)

    def test_limits_validation(self):
        """Test conversation limits validation."""
        # Valid limits
        ConversationState(context_id="test", max_history_size=1, max_variable_count=1)
        ConversationState(context_id="test", max_history_size=10000, max_variable_count=10000)

        # Invalid limits
        with pytest.raises(ValidationError):
            ConversationState(context_id="test", max_history_size=0)

        with pytest.raises(ValidationError):
            ConversationState(context_id="test", max_variable_count=0)

        with pytest.raises(ValidationError):
            ConversationState(context_id="test", max_history_size=10001)


class TestStateBackendConfig:
    """Test state backend configuration."""

    def test_memory_backend_config(self):
        """Test memory backend configuration."""
        config = StateBackendConfig(type=StateBackendType.MEMORY, max_size=5000, ttl=1800)

        assert config.type == StateBackendType.MEMORY
        assert config.max_size == 5000
        assert config.ttl == 1800

    def test_redis_backend_config(self):
        """Test Redis backend configuration."""
        config = StateBackendConfig(
            type=StateBackendType.REDIS,
            host="localhost",
            port=6379,
            database="0",
            redis_settings={"db": 0, "decode_responses": True},
        )

        assert config.type == StateBackendType.REDIS
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.redis_settings["db"] == 0

    def test_file_backend_config(self):
        """Test file backend configuration."""
        config = StateBackendConfig(type=StateBackendType.FILE, file_path="/var/lib/agentup/state.db", compression=True)

        assert config.type == StateBackendType.FILE
        assert config.file_path == "/var/lib/agentup/state.db"
        assert config.compression is True

    def test_database_backend_config(self):
        """Test database backend configuration."""
        config = StateBackendConfig(
            type=StateBackendType.DATABASE,
            connection_string="postgresql://user:pass@localhost/agentup",
            table_name="conversation_states",
            connection_pool_size=20,
        )

        assert config.type == StateBackendType.DATABASE
        assert "postgresql://" in config.connection_string
        assert config.table_name == "conversation_states"
        assert config.connection_pool_size == 20

    def test_backend_validation(self):
        """Test backend configuration validation."""
        # Valid values
        StateBackendConfig(type=StateBackendType.MEMORY, ttl=1, max_size=1)
        StateBackendConfig(type=StateBackendType.REDIS, port=1)
        StateBackendConfig(type=StateBackendType.REDIS, port=65535)

        # Invalid values
        with pytest.raises(ValidationError):
            StateBackendConfig(type=StateBackendType.MEMORY, ttl=0)

        with pytest.raises(ValidationError):
            StateBackendConfig(type=StateBackendType.MEMORY, max_size=0)

        with pytest.raises(ValidationError):
            StateBackendConfig(type=StateBackendType.REDIS, port=0)

        with pytest.raises(ValidationError):
            StateBackendConfig(type=StateBackendType.REDIS, port=65536)


class TestStateOperation:
    """Test state operation tracking."""

    def test_state_operation_creation(self):
        """Test creating state operations."""
        operation = StateOperation(
            operation_id="op_123",
            operation_type=StateOperationType.SET,
            context_id="conv_456",
            key="user_name",
            success=True,
            user_id="user_789",
        )

        assert operation.operation_id == "op_123"
        assert operation.operation_type == StateOperationType.SET
        assert operation.context_id == "conv_456"
        assert operation.key == "user_name"
        assert operation.success is True
        assert operation.user_id == "user_789"
        assert isinstance(operation.timestamp, datetime)

    def test_failed_operation(self):
        """Test failed state operation."""
        operation = StateOperation(
            operation_id="op_fail",
            operation_type=StateOperationType.GET,
            context_id="conv_123",
            key="missing_key",
            success=False,
            error_message="Key not found",
            duration_ms=5.2,
        )

        assert operation.success is False
        assert operation.error_message == "Key not found"
        assert operation.duration_ms == 5.2


class TestStateMetrics:
    """Test state metrics model."""

    def test_state_metrics(self):
        """Test state metrics creation."""
        metrics = StateMetrics(
            total_contexts=150,
            total_variables=1200,
            total_messages=5000,
            avg_variables_per_context=8.0,
            avg_messages_per_context=33.3,
            avg_get_latency_ms=2.5,
            avg_set_latency_ms=3.8,
            backend_type=StateBackendType.REDIS,
            backend_health="healthy",
            measurement_window=timedelta(hours=1),
        )

        assert metrics.total_contexts == 150
        assert metrics.avg_variables_per_context == 8.0
        assert metrics.backend_type == StateBackendType.REDIS
        assert metrics.backend_health == "healthy"
        assert metrics.measurement_window == timedelta(hours=1)


class TestStateConfig:
    """Test complete state configuration."""

    def test_default_state_config(self):
        """Test default state configuration."""
        backend = StateBackendConfig(type=StateBackendType.MEMORY)
        config = StateConfig(backend=backend)

        assert config.enabled is True
        assert config.backend.type == StateBackendType.MEMORY
        assert config.default_max_history == 100
        assert config.default_max_variables == 1000
        assert config.cleanup_enabled is True
        assert config.cache_enabled is True
        assert config.metrics_enabled is True

    def test_custom_state_config(self):
        """Test custom state configuration."""
        backend = StateBackendConfig(type=StateBackendType.REDIS, host="redis.example.com", port=6379)
        config = StateConfig(
            enabled=True,
            backend=backend,
            default_max_history=200,
            default_max_variables=2000,
            cleanup_interval=600,
            cache_size=2000,
            operation_logging=True,
        )

        assert config.backend.type == StateBackendType.REDIS
        assert config.backend.host == "redis.example.com"
        assert config.default_max_history == 200
        assert config.default_max_variables == 2000
        assert config.cleanup_interval == 600
        assert config.operation_logging is True

    def test_state_config_validation(self):
        """Test state configuration validation."""
        backend = StateBackendConfig(type=StateBackendType.MEMORY)

        # Valid configurations
        StateConfig(backend=backend, default_max_history=1, cache_size=1)

        # Invalid configurations
        with pytest.raises(ValidationError):
            StateConfig(backend=backend, default_max_history=0)

        with pytest.raises(ValidationError):
            StateConfig(backend=backend, default_max_variables=0)

        with pytest.raises(ValidationError):
            StateConfig(backend=backend, cache_size=0)


class TestModelIntegration:
    """Test model integration and complex scenarios."""

    def test_full_conversation_workflow(self):
        """Test a complete conversation workflow."""
        # Create conversation state
        state = ConversationState(context_id="full_test", user_id="user123", max_history_size=5)

        # Set initial variables
        state.set_variable("user_name", "Alice")
        state.set_variable("language", "en")
        state.set_variable("theme", "dark")

        # Add conversation messages
        messages = [
            ConversationMessage(id="1", role=ConversationRole.USER, content="Hi, I'm Alice"),
            ConversationMessage(id="2", role=ConversationRole.ASSISTANT, content="Hello Alice! How can I help?"),
            ConversationMessage(id="3", role=ConversationRole.USER, content="What's the weather like?"),
            ConversationMessage(id="4", role=ConversationRole.ASSISTANT, content="Let me check that for you."),
            ConversationMessage(
                id="5", role=ConversationRole.FUNCTION, content="Sunny, 72°F", function_name="get_weather"
            ),
            ConversationMessage(id="6", role=ConversationRole.ASSISTANT, content="It's sunny and 72°F today!"),
        ]

        for msg in messages:
            state.add_message(msg)

        # Verify state
        assert len(state.variables) == 3
        assert state.get_variable("user_name") == "Alice"
        assert len(state.history) <= 5  # Should respect limit

        # Get summary
        summary = state.get_summary_stats()
        assert summary.total_messages >= 3  # Some may be archived
        # Note: Due to history size limit, some USER messages may have been archived
        # The total count should still be correct due to our fix
        assert summary.total_messages == 6  # All 6 messages should be counted (current + archived)
        assert summary.assistant_messages >= 1

    def test_state_persistence_simulation(self):
        """Test state persistence-like operations."""
        # Simulate saving/loading state
        original_state = ConversationState(context_id="persist_test", user_id="user456")

        original_state.set_variable("session_start", datetime.utcnow().isoformat())
        original_state.add_message(ConversationMessage(id="msg1", role=ConversationRole.USER, content="Test message"))

        # Serialize to dict (simulating persistence)
        state_dict = original_state.dict()

        # Deserialize from dict (simulating loading)
        loaded_state = ConversationState(**state_dict)

        assert loaded_state.context_id == original_state.context_id
        assert loaded_state.user_id == original_state.user_id
        assert len(loaded_state.variables) == len(original_state.variables)
        assert len(loaded_state.history) == len(original_state.history)

    def test_variable_type_detection(self):
        """Test automatic variable type detection."""
        state = ConversationState(context_id="type_test")

        # Test different value types
        test_values = [
            ("string_var", "hello", StateVariableType.STRING),
            ("int_var", 42, StateVariableType.INTEGER),
            ("float_var", 3.14, StateVariableType.FLOAT),
            ("bool_var", True, StateVariableType.BOOLEAN),
            ("list_var", [1, 2, 3], StateVariableType.LIST),
            ("dict_var", {"key": "value"}, StateVariableType.DICT),
            ("bytes_var", b"binary", StateVariableType.BINARY),
        ]

        for key, value, expected_type in test_values:
            state.set_variable(key, value)
            assert state.variables[key].type_name == expected_type
            assert state.variables[key].value == value
