"""
Tests for API models and validators.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.agent.api.model import (
    A2ATaskState,
    APIError,
    APIErrorValidator,
    ErrorType,
    HealthCheckResponse,
    MetricsResponse,
    PaginatedResponse,
    PaginationParams,
    PaginationValidator,
    TaskPriority,
    TaskRequest,
    TaskRequestValidator,
    TaskResponse,
    create_api_validator,
)


class TestA2ATaskState:
    """Test A2ATaskState enum (imported from a2a.types)."""

    def test_task_state_values(self):
        """Test task state enum values."""
        # A2ATaskState is now imported from a2a.types as TaskState
        # Verify the expected values are available
        assert hasattr(A2ATaskState, "submitted")
        assert hasattr(A2ATaskState, "working")
        assert hasattr(A2ATaskState, "completed")
        assert hasattr(A2ATaskState, "failed")
        assert hasattr(A2ATaskState, "canceled")

        # Test that we can use the enum values
        assert A2ATaskState.submitted.value == "submitted"
        assert A2ATaskState.working.value == "working"
        assert A2ATaskState.completed.value == "completed"
        assert A2ATaskState.failed.value == "failed"
        assert A2ATaskState.canceled.value == "canceled"


class TestTaskPriority:
    """Test TaskPriority enum."""

    def test_task_priority_values(self):
        """Test task priority enum values."""
        assert TaskPriority.LOW == "low"
        assert TaskPriority.NORMAL == "normal"
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.URGENT == "urgent"


class TestErrorType:
    """Test ErrorType enum."""

    def test_error_type_values(self):
        """Test error type enum values."""
        assert ErrorType.VALIDATION_ERROR == "validation_error"
        assert ErrorType.AUTHENTICATION_ERROR == "authentication_error"
        assert ErrorType.AUTHORIZATION_ERROR == "authorization_error"
        assert ErrorType.RATE_LIMIT_ERROR == "rate_limit_error"
        assert ErrorType.INTERNAL_ERROR == "internal_error"
        assert ErrorType.NOT_FOUND_ERROR == "not_found_error"
        assert ErrorType.TIMEOUT_ERROR == "timeout_error"


class TestTaskRequest:
    """Test TaskRequest model."""

    def test_task_request_creation(self):
        """Test basic task request creation."""
        request = TaskRequest(
            task_id="task-123",
            function_name="test_function",
            parameters={"input": "test"},
            timeout=60,
            priority=TaskPriority.NORMAL,
        )

        assert request.task_id == "task-123"
        assert request.function_name == "test_function"
        assert request.parameters["input"] == "test"
        assert request.timeout == 60
        assert request.priority == TaskPriority.NORMAL
        assert request.callback_url is None
        assert request.user_id is None

    def test_task_id_validation(self):
        """Test task ID validation."""
        # Valid task IDs
        valid_ids = ["task-123", "task_456", "TASK789", "a1b2c3"]
        for task_id in valid_ids:
            request = TaskRequest(task_id=task_id, function_name="test_func")
            assert request.task_id == task_id

        # Invalid task IDs
        invalid_ids = ["task 123", "task@123", "task#123", ""]
        for task_id in invalid_ids:
            with pytest.raises(ValidationError):
                TaskRequest(task_id=task_id, function_name="test_func")

    def test_function_name_validation(self):
        """Test function name validation."""
        # Valid function names
        valid_names = ["test_function", "calculate_sum", "_private", "func123"]
        for name in valid_names:
            request = TaskRequest(task_id="test-123", function_name=name)
            assert request.function_name == name

        # Invalid function names
        invalid_names = ["123invalid", "func-name", "func name", "func!"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                TaskRequest(task_id="test-123", function_name=name)

    def test_callback_url_validation(self):
        """Test callback URL validation."""
        # Valid URLs
        valid_urls = ["http://example.com", "https://api.example.com/callback"]
        for url in valid_urls:
            request = TaskRequest(task_id="test-123", function_name="test_func", callback_url=url)
            assert request.callback_url == url

        # Invalid URLs
        invalid_urls = ["ftp://example.com", "example.com", "not-a-url"]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                TaskRequest(task_id="test-123", function_name="test_func", callback_url=url)

    def test_parameters_size_validation(self):
        """Test parameters size validation."""
        # Large parameters (> 100KB)
        large_params = {"data": "x" * 100001}
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(task_id="test-123", function_name="test_func", parameters=large_params)
        assert "Parameters too large" in str(exc_info.value)

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        request = TaskRequest(task_id="test-123", function_name="test_func", timeout=300)
        assert request.timeout == 300

        # Invalid timeout (too small)
        with pytest.raises(ValidationError):
            TaskRequest(task_id="test-123", function_name="test_func", timeout=0)

        # Invalid timeout (too large)
        with pytest.raises(ValidationError):
            TaskRequest(task_id="test-123", function_name="test_func", timeout=4000)


class TestTaskResponse:
    """Test TaskResponse model."""

    def test_task_response_creation(self):
        """Test basic task response creation."""
        response = TaskResponse(
            task_id="task-123", status=A2ATaskState.completed, result={"output": "success"}, progress=1.0
        )

        assert response.task_id == "task-123"
        assert response.status == A2ATaskState.completed
        assert response.result["output"] == "success"
        assert response.progress == 1.0
        assert response.error is None

    def test_progress_validation(self):
        """Test progress validation."""
        # Valid progress
        response = TaskResponse(task_id="task-123", status=A2ATaskState.working, progress=0.5)
        assert response.progress == 0.5

        # Invalid progress (negative)
        with pytest.raises(ValidationError):
            TaskResponse(task_id="task-123", status=A2ATaskState.working, progress=-0.1)

        # Invalid progress (> 1.0)
        with pytest.raises(ValidationError):
            TaskResponse(task_id="task-123", status=A2ATaskState.working, progress=1.5)

    def test_task_response_validation(self):
        """Test task response consistency validation."""
        # Failed task without error message should fail
        with pytest.raises(ValidationError) as exc_info:
            TaskResponse(task_id="task-123", status=A2ATaskState.failed)
        assert "Failed tasks must have error message" in str(exc_info.value)

        # Failed task with error message should succeed
        response = TaskResponse(task_id="task-123", status=A2ATaskState.failed, error="Task failed")
        assert response.error == "Task failed"

        # Successful task with error should clear error
        response = TaskResponse(task_id="task-123", status=A2ATaskState.completed, error="Previous error")
        assert response.error is None

        # Running task with 0 progress should be adjusted
        response = TaskResponse(task_id="task-123", status=A2ATaskState.working, progress=0.0)
        assert response.progress == 0.1

    def test_duration_calculation(self):
        """Test duration calculation."""
        start_time = datetime.utcnow()
        response = TaskResponse(task_id="task-123", status=A2ATaskState.completed, started_at=start_time)
        # Should have completion time set automatically
        assert response.completed_at is not None
        assert response.duration_seconds is not None
        assert response.duration_seconds >= 0

    def test_is_complete_property(self):
        """Test is_complete property."""
        # Completed task
        response = TaskResponse(task_id="task-123", status=A2ATaskState.completed)
        assert response.is_complete is True

        # Failed task
        response = TaskResponse(task_id="task-123", status=A2ATaskState.failed, error="Failed")
        assert response.is_complete is True

        # Running task
        response = TaskResponse(task_id="task-123", status=A2ATaskState.working)
        assert response.is_complete is False


class TestAPIError:
    """Test APIError model."""

    def test_api_error_creation(self):
        """Test basic API error creation."""
        error = APIError(
            error_type=ErrorType.VALIDATION_ERROR, error_code="INVALID_INPUT", message="Invalid input provided"
        )

        assert error.error_type == ErrorType.VALIDATION_ERROR
        assert error.error_code == "INVALID_INPUT"
        assert error.message == "Invalid input provided"
        assert isinstance(error.timestamp, datetime)

    def test_error_code_validation(self):
        """Test error code validation."""
        # Valid error codes
        valid_codes = ["VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_ERROR_123"]
        for code in valid_codes:
            error = APIError(error_type=ErrorType.VALIDATION_ERROR, error_code=code, message="Test error")
            assert error.error_code == code

        # Invalid error codes
        invalid_codes = ["validation_error", "notFound", "123INVALID", "error-code"]
        for code in invalid_codes:
            with pytest.raises(ValidationError):
                APIError(error_type=ErrorType.VALIDATION_ERROR, error_code=code, message="Test error")

    def test_message_validation(self):
        """Test error message validation."""
        # Valid message
        error = APIError(
            error_type=ErrorType.VALIDATION_ERROR, error_code="INVALID_INPUT", message="This is a valid error message"
        )
        assert len(error.message) >= 5

        # Too short message
        with pytest.raises(ValidationError):
            APIError(error_type=ErrorType.VALIDATION_ERROR, error_code="INVALID_INPUT", message="Hi")

        # Too long message
        with pytest.raises(ValidationError):
            APIError(error_type=ErrorType.VALIDATION_ERROR, error_code="INVALID_INPUT", message="x" * 501)


class TestPaginationParams:
    """Test PaginationParams model."""

    def test_pagination_params_creation(self):
        """Test basic pagination params creation."""
        params = PaginationParams(page=2, per_page=20, sort_by="created_at", sort_order="desc")

        assert params.page == 2
        assert params.per_page == 20
        assert params.sort_by == "created_at"
        assert params.sort_order == "desc"

    def test_pagination_validation(self):
        """Test pagination validation."""
        # Valid pagination
        params = PaginationParams(page=1, per_page=50)
        assert params.page == 1
        assert params.per_page == 50

        # Invalid page (< 1)
        with pytest.raises(ValidationError):
            PaginationParams(page=0, per_page=50)

        # Invalid per_page (< 1)
        with pytest.raises(ValidationError):
            PaginationParams(page=1, per_page=0)

        # Invalid per_page (> 1000)
        with pytest.raises(ValidationError):
            PaginationParams(page=1, per_page=1001)

    def test_offset_and_limit_properties(self):
        """Test offset and limit properties."""
        params = PaginationParams(page=3, per_page=20)
        assert params.offset == 40  # (3-1) * 20
        assert params.limit == 20


class TestPaginatedResponse:
    """Test PaginatedResponse model."""

    def test_paginated_response_creation(self):
        """Test basic paginated response creation."""
        response = PaginatedResponse(
            items=[1, 2, 3], total=100, page=1, per_page=10, pages=10, has_next=True, has_prev=False
        )

        assert len(response.items) == 3
        assert response.total == 100
        assert response.page == 1
        assert response.per_page == 10
        assert response.pages == 10
        assert response.has_next is True
        assert response.has_prev is False

    def test_create_class_method(self):
        """Test create class method."""
        items = ["item1", "item2", "item3"]
        pagination = PaginationParams(page=2, per_page=5)

        response = PaginatedResponse.create(items=items, total=13, pagination=pagination)

        assert response.items == items
        assert response.total == 13
        assert response.page == 2
        assert response.per_page == 5
        assert response.pages == 3  # ceil(13/5)
        assert response.has_next is True  # page 2 < 3 pages
        assert response.has_prev is True  # page 2 > 1


class TestHealthCheckResponse:
    """Test HealthCheckResponse model."""

    def test_health_check_response_creation(self):
        """Test basic health check response creation."""
        response = HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            uptime_seconds=3600.5,
            services={
                "database": {"status": "healthy", "response_time": 0.05},
                "cache": {"status": "degraded", "response_time": 0.2},
            },
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.uptime_seconds == 3600.5
        assert "database" in response.services
        assert response.is_healthy is True

    def test_is_healthy_property(self):
        """Test is_healthy property."""
        # Healthy status
        response = HealthCheckResponse(status="healthy", version="1.0.0", uptime_seconds=100)
        assert response.is_healthy is True

        # Degraded status
        response = HealthCheckResponse(status="degraded", version="1.0.0", uptime_seconds=100)
        assert response.is_healthy is False

        # Unhealthy status
        response = HealthCheckResponse(status="unhealthy", version="1.0.0", uptime_seconds=100)
        assert response.is_healthy is False


class TestMetricsResponse:
    """Test MetricsResponse model."""

    def test_metrics_response_creation(self):
        """Test basic metrics response creation."""
        response = MetricsResponse(
            request_count=1000,
            error_count=50,
            average_response_time_ms=150.5,
            active_tasks=5,
            completed_tasks=995,
            failed_tasks=50,
        )

        assert response.request_count == 1000
        assert response.error_count == 50
        assert response.average_response_time_ms == 150.5
        assert response.active_tasks == 5
        assert response.completed_tasks == 995
        assert response.failed_tasks == 50

    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        response = MetricsResponse(request_count=1000, error_count=50)
        assert response.error_rate == 5.0  # 50/1000 * 100

        # Test with zero requests
        response = MetricsResponse(request_count=0, error_count=0)
        assert response.error_rate == 0.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        response = MetricsResponse(request_count=1000, error_count=50)
        assert response.success_rate == 95.0  # 100 - 5.0


class TestValidators:
    """Test API validators."""

    def test_task_request_validator(self):
        """Test task request validator."""
        validator = TaskRequestValidator(TaskRequest)

        # Test dangerous function name warning
        dangerous_request = TaskRequest(task_id="test-123", function_name="delete_files")
        result = validator.validate(dangerous_request)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "dangerous pattern" in result.warnings[0]

        # Test timeout warnings
        short_timeout_request = TaskRequest(task_id="test-123", function_name="test_func", timeout=2)
        result = validator.validate(short_timeout_request)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "short timeout" in result.warnings[0]

        long_timeout_request = TaskRequest(task_id="test-123", function_name="test_func", timeout=2000)
        result = validator.validate(long_timeout_request)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "long timeout" in result.warnings[0]

        # Test many parameters warning
        many_params = {f"param_{i}": f"value_{i}" for i in range(25)}
        complex_request = TaskRequest(task_id="test-123", function_name="test_func", parameters=many_params)
        result = validator.validate(complex_request)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "Large number of parameters" in result.warnings[0]

        # Test urgent priority suggestion
        urgent_request = TaskRequest(task_id="test-123", function_name="test_func", priority=TaskPriority.URGENT)
        result = validator.validate(urgent_request)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "associated user" in result.suggestions[0]

    def test_api_error_validator(self):
        """Test API error validator."""
        validator = APIErrorValidator(APIError)

        # Test vague error message suggestion
        vague_error = APIError(error_type=ErrorType.VALIDATION_ERROR, error_code="ERROR", message="Error occurred")
        result = validator.validate(vague_error)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "more specific" in result.suggestions[0]

        # Test error type consistency warning
        inconsistent_error = APIError(
            error_type=ErrorType.VALIDATION_ERROR, error_code="AUTH_FAILED", message="Authentication failed"
        )
        result = validator.validate(inconsistent_error)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "doesn't match message" in result.warnings[0]

        # Test sensitive information warning
        sensitive_error = APIError(
            error_type=ErrorType.INTERNAL_ERROR,
            error_code="DATABASE_ERROR",
            message="Failed to connect using password 'secret123'",
        )
        result = validator.validate(sensitive_error)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "sensitive information" in result.warnings[0]

    def test_pagination_validator(self):
        """Test pagination validator."""
        validator = PaginationValidator(PaginationParams)

        # Test large page size warning
        large_page = PaginationParams(page=1, per_page=500)
        result = validator.validate(large_page)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "Large page size" in result.warnings[0]

        # Test sort field validation
        invalid_sort = PaginationParams(page=1, per_page=20, sort_by="invalid@field")
        result = validator.validate(invalid_sort)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "alphanumeric" in result.warnings[0]

    def test_composite_api_validator(self):
        """Test composite API validator."""
        composite_validator = create_api_validator()

        # Test with valid request
        request = TaskRequest(task_id="test-123", function_name="safe_function")
        result = composite_validator.validate(request)
        assert result.valid is True

        # Test with request that triggers warnings
        dangerous_request = TaskRequest(task_id="test-123", function_name="eval_expression", timeout=1)
        result = composite_validator.validate(dangerous_request)
        assert result.valid is True
        assert len(result.warnings) > 0  # Should have warnings about dangerous name and short timeout


class TestModelSerialization:
    """Test Pydantic v2 serialization methods."""

    def test_task_request_serialization(self):
        """Test task request serialization."""
        request = TaskRequest(
            task_id="task-123", function_name="test_function", parameters={"input": "test"}, priority=TaskPriority.HIGH
        )

        # Test model_dump
        data = request.model_dump()
        assert data["task_id"] == "task-123"
        assert data["function_name"] == "test_function"
        assert data["parameters"]["input"] == "test"
        assert data["priority"] == "high"

        # Test model_dump_json
        json_str = request.model_dump_json()
        assert "task-123" in json_str
        assert "test_function" in json_str

        # Test round trip
        request2 = TaskRequest.model_validate(data)
        assert request == request2

        request3 = TaskRequest.model_validate_json(json_str)
        assert request == request3

    def test_api_error_serialization(self):
        """Test API error serialization."""
        error = APIError(
            error_type=ErrorType.VALIDATION_ERROR,
            error_code="INVALID_INPUT",
            message="Invalid input provided",
            details={"field": "username", "issue": "too_short"},
        )

        # Test model_dump
        data = error.model_dump()
        assert "error_type" in data
        assert "error_code" in data
        assert "message" in data
        assert "details" in data
        assert "timestamp" in data

        # Test round trip
        error2 = APIError.model_validate(data)
        assert error.error_type == error2.error_type
        assert error.error_code == error2.error_code
        assert error.message == error2.message
        assert error.details == error2.details

    def test_health_check_response_serialization(self):
        """Test health check response serialization."""
        response = HealthCheckResponse(
            status="healthy", version="1.0.0", uptime_seconds=3600, services={"db": {"status": "healthy"}}
        )

        # Test model_dump
        data = response.model_dump()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["uptime_seconds"] == 3600
        assert "db" in data["services"]

        # Test round trip preserves all data
        response2 = HealthCheckResponse.model_validate(data)
        assert response.status == response2.status
        assert response.version == response2.version
        assert response.uptime_seconds == response2.uptime_seconds
        assert response.services == response2.services
