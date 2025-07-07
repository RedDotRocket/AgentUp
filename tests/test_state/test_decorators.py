from unittest.mock import AsyncMock, Mock, patch

import pytest
from a2a.types import Message, Part, Role, Task, TaskState, TaskStatus, TextPart

from src.agent.state.decorators import (
    _create_state_wrapper,
    _inject_state_if_supported,
    _preserve_ai_attributes,
    stateful,
    stateful_conversation,
    stateful_session,
    stateful_user,
    with_state,
)


def create_test_task(task_id: str = "test-123", context_id: str = "context-123") -> Task:
    """Create a test Task with all required fields."""
    return Task(id=task_id, contextId=context_id, status=TaskStatus(state=TaskState.submitted), history=[])


def create_test_message(role: Role = Role.user, text: str = "Hello") -> Message:
    """Create a test Message with all required fields."""
    text_part = Part(root=TextPart(text=text))
    return Message(messageId="msg-123", role=role, parts=[text_part])


class TestPreserveAIAttributes:
    """Test AI attribute preservation functionality."""

    def test_preserve_ai_attributes_with_attributes(self):
        """Test that AI attributes are preserved correctly."""

        # Create original function with AI attributes
        async def original_func():
            pass

        original_func._is_ai_function = True
        original_func._ai_function_schema = {"type": "function", "name": "test"}

        # Create wrapper
        async def wrapper():
            pass

        # Apply preservation
        _preserve_ai_attributes(wrapper, original_func)

        # Verify attributes were preserved
        assert hasattr(wrapper, "_is_ai_function")
        assert wrapper._is_ai_function is True
        assert hasattr(wrapper, "_ai_function_schema")
        assert wrapper._ai_function_schema == {"type": "function", "name": "test"}

    def test_preserve_ai_attributes_without_attributes(self):
        """Test that function without AI attributes doesn't cause errors."""

        async def original_func():
            pass

        async def wrapper():
            pass

        # Apply preservation (should not raise)
        _preserve_ai_attributes(wrapper, original_func)

        # Verify no attributes were added
        assert not hasattr(wrapper, "_is_ai_function")
        assert not hasattr(wrapper, "_ai_function_schema")


class TestInjectStateIfSupported:
    """Test state injection functionality."""

    def test_inject_state_with_context_support(self):
        """Test state injection for function that accepts context."""

        async def handler(task: Task, context=None):
            return "test"

        task = create_test_task()
        backend = "memory"
        backend_config = {}
        context_id = "test-context"
        kwargs = {}

        with patch("src.agent.state.decorators.get_context_manager") as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            _inject_state_if_supported(handler, task, backend, backend_config, context_id, kwargs)

            # Verify context was injected
            assert "context" in kwargs
            assert kwargs["context"] == mock_context
            mock_get_context.assert_called_once_with(backend)

    def test_inject_state_with_context_id_support(self):
        """Test state injection for function that accepts context_id."""

        async def handler(task: Task, context_id=None):
            return "test"

        task = create_test_task()
        backend = "memory"
        backend_config = {}
        context_id = "test-context"
        kwargs = {}

        with patch("src.agent.state.decorators.get_context_manager") as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            _inject_state_if_supported(handler, task, backend, backend_config, context_id, kwargs)

            # Verify context_id was injected
            assert "context_id" in kwargs
            assert kwargs["context_id"] == context_id

    def test_inject_state_with_both_parameters(self):
        """Test state injection for function that accepts both context and context_id."""

        async def handler(task: Task, context=None, context_id=None):
            return "test"

        task = create_test_task()
        backend = "memory"
        backend_config = {}
        context_id = "test-context"
        kwargs = {}

        with patch("src.agent.state.decorators.get_context_manager") as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            _inject_state_if_supported(handler, task, backend, backend_config, context_id, kwargs)

            # Verify both were injected
            assert "context" in kwargs
            assert "context_id" in kwargs
            assert kwargs["context"] == mock_context
            assert kwargs["context_id"] == context_id

    def test_inject_state_no_support(self):
        """Test state injection for function that doesn't accept state parameters."""

        async def handler(task: Task):
            return "test"

        task = create_test_task()
        backend = "memory"
        backend_config = {}
        context_id = "test-context"
        kwargs = {}

        with patch("src.agent.state.decorators.get_context_manager") as mock_get_context:
            _inject_state_if_supported(handler, task, backend, backend_config, context_id, kwargs)

            # Verify nothing was injected
            assert len(kwargs) == 0
            mock_get_context.assert_not_called()


class TestCreateStateWrapper:
    """Test state wrapper creation functionality."""

    @pytest.mark.asyncio
    async def test_create_state_wrapper_success(self):
        """Test successful state wrapper creation and execution."""

        # Create mock function
        async def mock_handler(task: Task, context=None):
            return f"Handled: {task.id}"

        # Create wrapper
        backend = "memory"
        backend_config = {}

        def context_id_generator(task):
            return f"context-{task.id}"

        error_prefix = "Test"

        wrapped_func = _create_state_wrapper(mock_handler, backend, backend_config, context_id_generator, error_prefix)

        # Test execution
        task = create_test_task()

        with patch("src.agent.state.decorators._inject_state_if_supported") as mock_inject:
            _result = await wrapped_func(task)

            # Verify function was called correctly
            assert _result == "Handled: test-123"
            mock_inject.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_state_wrapper_with_exception(self):
        """Test state wrapper handles exceptions gracefully."""

        # Create mock function that raises an exception on first call (with context)
        # but succeeds on second call (without context)
        async def mock_handler(task: Task, context=None):
            if context:
                raise RuntimeError("State error")
            return f"Fallback: {task.id}"

        # Create wrapper
        backend = "memory"
        backend_config = {}

        def context_id_generator(task):
            return f"context-{task.id}"

        error_prefix = "Test"

        wrapped_func = _create_state_wrapper(mock_handler, backend, backend_config, context_id_generator, error_prefix)

        # Test execution with exception
        task = create_test_task()

        with patch("src.agent.state.decorators._inject_state_if_supported") as mock_inject:
            with patch("src.agent.state.decorators.logger") as mock_logger:
                # Mock injection to add context (triggering exception)
                mock_inject.side_effect = lambda f, t, b, bc, ci, k: k.update({"context": Mock()})

                _result = await wrapped_func(task)

                # Verify fallback was called
                assert _result == "Fallback: test-123"
                mock_logger.error.assert_called_once()


class TestWithStateDecorator:
    """Test with_state decorator functionality."""

    @pytest.mark.asyncio
    async def test_with_state_enabled(self):
        """Test with_state decorator when state is enabled."""
        # Create state config
        state_configs = [{"enabled": True, "backend": "memory", "config": {"max_size": 1000}}]

        # Create handler
        @with_state(state_configs)
        async def test_handler(task: Task, context=None):
            return f"Handler: {task.id}"

        # Test execution
        task = create_test_task()

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            mock_create_wrapper.return_value = AsyncMock(return_value="Wrapped result")

            # The decorator should create a wrapper
            _result = await test_handler(task)
            assert _result == "Wrapped result"
            mock_create_wrapper.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_state_disabled(self):
        """Test with_state decorator when state is disabled."""
        # Create state config with disabled state
        state_configs = [{"enabled": False, "backend": "memory", "config": {}}]

        # Create handler
        @with_state(state_configs)
        async def test_handler(task: Task):
            return f"Handler: {task.id}"

        # Test execution
        task = create_test_task()
        _result = await test_handler(task)

        # Should return original function result
        assert _result == "Handler: test-123"

    @pytest.mark.asyncio
    async def test_with_state_empty_config(self):
        """Test with_state decorator with empty config."""

        # Create handler with empty config
        @with_state([])
        async def test_handler(task: Task):
            return f"Handler: {task.id}"

        # Test execution
        task = create_test_task()
        _result = await test_handler(task)

        # Should return original function result
        assert _result == "Handler: test-123"


class TestStatefulConversationDecorator:
    """Test stateful_conversation decorator functionality."""

    @pytest.mark.asyncio
    async def test_stateful_conversation_context_id(self):
        """Test stateful_conversation generates correct context ID."""
        # Test with conversation_id (using metadata since A2A Task doesn't allow custom attributes)
        task = create_test_task()
        task.metadata = {"conversation_id": "conv-456"}

        # Create the decorator and extract the context_id_generator
        decorator = stateful_conversation(backend="memory")

        # Create a simple function to decorate
        async def test_function(task: Task):
            return "test"

        # Mock _create_state_wrapper to capture the context_id_generator
        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return test_function  # Return original function

            mock_create_wrapper.side_effect = capture_generator

            # Apply decorator (this triggers _create_state_wrapper)
            _decorated_func = decorator(test_function)

            # Verify context ID generation
            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "conversation:conv-456"

    @pytest.mark.asyncio
    async def test_stateful_conversation_fallback_to_task_id(self):
        """Test stateful_conversation falls back to task ID when no conversation_id."""
        # Test without conversation_id
        task = create_test_task()

        # Create the decorator and extract the context_id_generator
        decorator = stateful_conversation(backend="memory")

        # Create a simple function to decorate
        async def test_function(task: Task):
            return "test"

        # Mock _create_state_wrapper to capture the context_id_generator
        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return test_function

            mock_create_wrapper.side_effect = capture_generator

            # Apply decorator (this triggers _create_state_wrapper)
            _decorated_func = decorator(test_function)

            # Verify context ID generation falls back to contextId
            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "conversation:context-123"


class TestStatefulUserDecorator:
    """Test stateful_user decorator functionality."""

    @pytest.mark.asyncio
    async def test_stateful_user_with_user_id(self):
        """Test stateful_user generates correct context ID with user_id."""
        # Test with user_id
        task = create_test_task()
        task.metadata = {"user_id": "user-789"}

        decorator = stateful_user(backend="memory")

        async def test_function(task: Task):
            return "test"

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return test_function

            mock_create_wrapper.side_effect = capture_generator
            _decorated_func = decorator(test_function)

            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "user:user-789"

    @pytest.mark.asyncio
    async def test_stateful_user_anonymous(self):
        """Test stateful_user falls back to anonymous when no user_id."""
        # Test without user_id
        task = create_test_task()

        decorator = stateful_user(backend="memory")

        async def test_function(task: Task):
            return "test"

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return test_function

            mock_create_wrapper.side_effect = capture_generator
            _decorated_func = decorator(test_function)

            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "user:anonymous"


class TestStatefulSessionDecorator:
    """Test stateful_session decorator functionality."""

    @pytest.mark.asyncio
    async def test_stateful_session_with_session_id(self):
        """Test stateful_session generates correct context ID with session_id."""

        # Create handler
        @stateful_session(backend="memory")
        async def test_handler(task: Task, context=None, context_id=None):
            return f"Context: {context_id}"

        # Test with session_id
        task = create_test_task()
        task.metadata = {"session_id": "session-abc"}

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            # Mock wrapper to capture context_id_generator
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return AsyncMock(return_value="Test result")

            mock_create_wrapper.side_effect = capture_generator

            _result = await test_handler(task)

            # Verify context ID generation
            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "session:session-abc"

    @pytest.mark.asyncio
    async def test_stateful_session_fallback_to_task_id(self):
        """Test stateful_session falls back to task ID when no session_id."""

        # Create handler
        @stateful_session(backend="memory")
        async def test_handler(task: Task, context=None, context_id=None):
            return f"Context: {context_id}"

        # Test without session_id
        task = create_test_task()

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            # Mock wrapper to capture context_id_generator
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return AsyncMock(return_value="Test result")

            mock_create_wrapper.side_effect = capture_generator

            _result = await test_handler(task)

            # Verify context ID generation
            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "session:test-123"


class TestStatefulLegacyDecorator:
    """Test legacy stateful decorator functionality."""

    @pytest.mark.asyncio
    async def test_stateful_legacy_with_context_id(self):
        """Test legacy stateful decorator generates correct context ID."""

        # Create handler
        @stateful(storage="memory")
        async def test_handler(task: Task, context=None, context_id=None):
            return f"Context: {context_id}"

        # Test with context_id
        task = create_test_task()
        task.metadata = {"context_id": "custom-context"}

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            # Mock wrapper to capture context_id_generator
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return AsyncMock(return_value="Test result")

            mock_create_wrapper.side_effect = capture_generator

            _result = await test_handler(task)

            # Verify context ID generation
            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "custom-context"

    @pytest.mark.asyncio
    async def test_stateful_legacy_fallback_to_task_id(self):
        """Test legacy stateful decorator falls back to task ID."""

        # Create handler
        @stateful(storage="memory")
        async def test_handler(task: Task, context=None, context_id=None):
            return f"Context: {context_id}"

        # Test without context_id
        task = create_test_task()

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            # Mock wrapper to capture context_id_generator
            captured_generator = None

            def capture_generator(func, backend, backend_config, context_id_generator, error_prefix):
                nonlocal captured_generator
                captured_generator = context_id_generator
                return AsyncMock(return_value="Test result")

            mock_create_wrapper.side_effect = capture_generator

            _result = await test_handler(task)

            # Verify context ID generation
            assert captured_generator is not None
            context_id = captured_generator(task)
            assert context_id == "test-123"


class TestIntegrationScenarios:
    """Test integration scenarios with real A2A Task objects."""

    @pytest.mark.asyncio
    async def test_real_task_with_state(self):
        """Test state decorator with real A2A Task structure."""
        # Create a real A2A Task with proper Message and Part structure
        message = create_test_message(text="Hello, remember my name is Alice")
        task = create_test_task(task_id="task-123")
        task.history = [message]

        # Create a stateful handler
        @with_state([{"enabled": True, "backend": "memory", "config": {}}])
        async def stateful_handler(task: Task, context=None, context_id=None):
            if context and context_id:
                return f"Stateful: {context_id} - {task.id}"
            return f"Stateless: {task.id}"

        # Mock the context manager
        with patch("src.agent.state.decorators.get_context_manager") as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            result = await stateful_handler(task)

            # Verify state was injected
            assert "Stateful:" in result
            assert "task-123" in result
            mock_get_context.assert_called_once_with("memory")

    @pytest.mark.asyncio
    async def test_multiple_decorators_composition(self):
        """Test that multiple state decorators can be composed."""

        # Create handler with multiple decorators
        @stateful_conversation(backend="memory")
        @stateful_user(backend="file", storage_dir="/tmp")
        async def multi_stateful_handler(task: Task, context=None, context_id=None):
            return f"Multi: {context_id}"

        # Test execution
        task = create_test_task()
        task.metadata = {"conversation_id": "conv-456", "user_id": "user-789"}

        with patch("src.agent.state.decorators._create_state_wrapper") as mock_create_wrapper:
            # Mock to return the original function (simplified test)
            mock_create_wrapper.return_value = AsyncMock(return_value="Multi decorator result")

            _result = await multi_stateful_handler(task)

            # Verify decorator was applied (outermost decorator wins)
            assert _result == "Multi decorator result"
            # Should have been called twice (once for each decorator)
            assert mock_create_wrapper.call_count == 2
