"""
Tests for core models and validators.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.agent.core.model import (
    ExecutionContext,
    ExecutionContextValidator,
    ExecutionResult,
    ExecutionResultValidator,
    ExecutionStatus,
    FunctionParameter,
    FunctionRegistry,
    FunctionSignature,
    FunctionSignatureValidator,
    FunctionType,
    ParameterType,
    create_core_validator,
)


class TestExecutionStatus:
    """Test ExecutionStatus enum."""

    def test_execution_status_values(self):
        """Test execution status enum values."""
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.COMPLETED == "completed"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.TIMEOUT == "timeout"
        assert ExecutionStatus.CANCELLED == "cancelled"


class TestFunctionType:
    """Test FunctionType enum."""

    def test_function_type_values(self):
        """Test function type enum values."""
        assert FunctionType.BUILTIN == "builtin"
        assert FunctionType.PLUGIN == "plugin"
        assert FunctionType.LLM_FUNCTION == "llm_function"
        assert FunctionType.ASYNC == "async"
        assert FunctionType.STREAMING == "streaming"


class TestParameterType:
    """Test ParameterType enum."""

    def test_parameter_type_values(self):
        """Test parameter type enum values."""
        assert ParameterType.STRING == "string"
        assert ParameterType.INTEGER == "integer"
        assert ParameterType.FLOAT == "float"
        assert ParameterType.BOOLEAN == "boolean"
        assert ParameterType.ARRAY == "array"
        assert ParameterType.OBJECT == "object"
        assert ParameterType.ANY == "any"


class TestFunctionParameter:
    """Test FunctionParameter model."""

    def test_function_parameter_creation(self):
        """Test basic function parameter creation."""
        param = FunctionParameter(
            name="input_text",
            type=ParameterType.STRING,
            description="Input text to process",
            required=True,
            min_length=1,
            max_length=1000,
        )

        assert param.name == "input_text"
        assert param.type == ParameterType.STRING
        assert param.description == "Input text to process"
        assert param.required is True
        assert param.min_length == 1
        assert param.max_length == 1000
        assert param.default is None

    def test_parameter_name_validation(self):
        """Test parameter name validation."""
        # Valid names
        valid_names = ["param", "param_name", "_private", "param123", "camelCase"]
        for name in valid_names:
            param = FunctionParameter(name=name, type=ParameterType.STRING)
            assert param.name == name

        # Invalid names
        invalid_names = ["123invalid", "param-name", "param name", "param!", ""]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                FunctionParameter(name=name, type=ParameterType.STRING)

    def test_parameter_constraints_validation(self):
        """Test parameter constraints validation."""
        # Valid numeric constraints
        param = FunctionParameter(name="number", type=ParameterType.INTEGER, min_value=1, max_value=100)
        assert param.min_value == 1
        assert param.max_value == 100

        # Invalid numeric constraints (min > max)
        with pytest.raises(ValidationError) as exc_info:
            FunctionParameter(name="number", type=ParameterType.INTEGER, min_value=100, max_value=1)
        assert "min_value cannot be greater than max_value" in str(exc_info.value)

        # Valid length constraints
        param = FunctionParameter(name="text", type=ParameterType.STRING, min_length=5, max_length=50)
        assert param.min_length == 5
        assert param.max_length == 50

        # Invalid length constraints (min > max)
        with pytest.raises(ValidationError) as exc_info:
            FunctionParameter(name="text", type=ParameterType.STRING, min_length=50, max_length=5)
        assert "min_length cannot be greater than max_length" in str(exc_info.value)

    def test_default_value_handling(self):
        """Test default value handling."""
        # Parameter with default should not be required
        param = FunctionParameter(
            name="optional_param",
            type=ParameterType.STRING,
            required=True,  # This should be set to False automatically
            default="default_value",
        )
        assert param.required is False
        assert param.default == "default_value"


class TestFunctionSignature:
    """Test FunctionSignature model."""

    def test_function_signature_creation(self):
        """Test basic function signature creation."""
        signature = FunctionSignature(
            name="process_text",
            module="text_processor",
            function_type=FunctionType.PLUGIN,
            description="Process text input",
            version="1.2.0",
        )

        assert signature.name == "process_text"
        assert signature.module == "text_processor"
        assert signature.function_type == FunctionType.PLUGIN
        assert signature.description == "Process text input"
        assert signature.version == "1.2.0"
        assert len(signature.parameters) == 0
        assert signature.deprecated is False

    def test_function_name_validation(self):
        """Test function name validation."""
        # Valid names
        valid_names = ["func", "my_function", "_private", "func123"]
        for name in valid_names:
            signature = FunctionSignature(name=name, module="test_module", function_type=FunctionType.BUILTIN)
            assert signature.name == name

        # Invalid names
        invalid_names = ["123invalid", "func-name", "func name", "func!", ""]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                FunctionSignature(name=name, module="test_module", function_type=FunctionType.BUILTIN)

        # Reserved names
        reserved_names = ["eval", "exec", "import", "__import__", "compile", "open"]
        for name in reserved_names:
            with pytest.raises(ValidationError) as exc_info:
                FunctionSignature(name=name, module="test_module", function_type=FunctionType.BUILTIN)
            assert f"Function name '{name}' is reserved" in str(exc_info.value)

    def test_module_path_validation(self):
        """Test module path validation."""
        # Valid module paths
        valid_paths = ["module", "my_module", "package.module", "deep.package.module"]
        for path in valid_paths:
            signature = FunctionSignature(name="test_func", module=path, function_type=FunctionType.BUILTIN)
            assert signature.module == path

        # Invalid module paths
        invalid_paths = ["123invalid", "module-name", "module name", "module!", ""]
        for path in invalid_paths:
            with pytest.raises(ValidationError):
                FunctionSignature(name="test_func", module=path, function_type=FunctionType.BUILTIN)

    def test_tags_validation(self):
        """Test tags validation."""
        # Valid tags
        valid_tags = ["nlp", "text-processing", "ai_function", "utility"]
        signature = FunctionSignature(
            name="test_func", module="test_module", function_type=FunctionType.BUILTIN, tags=valid_tags
        )
        assert signature.tags == valid_tags

        # Invalid tags
        invalid_tags = ["tag!", "tag with spaces", "", "tag@123"]
        with pytest.raises(ValidationError):
            FunctionSignature(
                name="test_func", module="test_module", function_type=FunctionType.BUILTIN, tags=invalid_tags
            )

    def test_version_validation(self):
        """Test semantic version validation."""
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-alpha", "1.0.0-beta.1", "1.0.0+build.123"]
        for version in valid_versions:
            signature = FunctionSignature(
                name="test_func", module="test_module", function_type=FunctionType.BUILTIN, version=version
            )
            assert signature.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                FunctionSignature(
                    name="test_func", module="test_module", function_type=FunctionType.BUILTIN, version=version
                )

    def test_parameter_properties(self):
        """Test parameter properties."""
        param1 = FunctionParameter(name="required_param", type=ParameterType.STRING, required=True)
        param2 = FunctionParameter(name="optional_param", type=ParameterType.STRING, required=False)

        signature = FunctionSignature(
            name="test_func", module="test_module", function_type=FunctionType.BUILTIN, parameters=[param1, param2]
        )

        required_params = signature.required_parameters
        optional_params = signature.optional_parameters

        assert len(required_params) == 1
        assert required_params[0].name == "required_param"
        assert len(optional_params) == 1
        assert optional_params[0].name == "optional_param"


class TestExecutionContext:
    """Test ExecutionContext model."""

    def test_execution_context_creation(self):
        """Test basic execution context creation."""
        context = ExecutionContext(
            request_id="req-123",
            function_name="test_function",
            user_id="user-456",
            session_id="session-789",
            timeout_seconds=60,
            max_retries=3,
        )

        assert context.request_id == "req-123"
        assert context.function_name == "test_function"
        assert context.user_id == "user-456"
        assert context.session_id == "session-789"
        assert context.timeout_seconds == 60
        assert context.max_retries == 3
        assert context.retry_count == 0
        assert isinstance(context.started_at, datetime)

    def test_request_id_validation(self):
        """Test request ID validation."""
        # Valid request IDs
        valid_ids = ["req-123", "req_456", "REQUEST789", "a1b2c3"]
        for req_id in valid_ids:
            context = ExecutionContext(request_id=req_id, function_name="test_func")
            assert context.request_id == req_id

        # Invalid request IDs
        invalid_ids = ["req 123", "req@123", "req#123", ""]
        for req_id in invalid_ids:
            with pytest.raises(ValidationError):
                ExecutionContext(request_id=req_id, function_name="test_func")

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        context = ExecutionContext(request_id="req-123", function_name="test_func", timeout_seconds=300)
        assert context.timeout_seconds == 300

        # Invalid timeout (too small)
        with pytest.raises(ValidationError):
            ExecutionContext(request_id="req-123", function_name="test_func", timeout_seconds=0)

        # Invalid timeout (too large)
        with pytest.raises(ValidationError):
            ExecutionContext(request_id="req-123", function_name="test_func", timeout_seconds=4000)

    def test_retry_properties(self):
        """Test retry properties."""
        # Initial context (no retries)
        context = ExecutionContext(request_id="req-123", function_name="test_func", retry_count=0, max_retries=3)
        assert context.is_retry is False
        assert context.can_retry is True

        # Context with retries
        context = ExecutionContext(request_id="req-123", function_name="test_func", retry_count=2, max_retries=3)
        assert context.is_retry is True
        assert context.can_retry is True

        # Context at max retries
        context = ExecutionContext(request_id="req-123", function_name="test_func", retry_count=3, max_retries=3)
        assert context.is_retry is True
        assert context.can_retry is False

    def test_elapsed_seconds_property(self):
        """Test elapsed seconds calculation."""
        context = ExecutionContext(request_id="req-123", function_name="test_func")
        elapsed = context.elapsed_seconds
        assert elapsed >= 0
        assert elapsed < 1  # Should be very small for new context


class TestExecutionResult:
    """Test ExecutionResult model."""

    def test_execution_result_creation(self):
        """Test basic execution result creation."""
        start_time = datetime.utcnow()
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_function",
            status=ExecutionStatus.COMPLETED,
            result={"output": "success"},
            started_at=start_time,
        )

        assert result.request_id == "req-123"
        assert result.function_name == "test_function"
        assert result.status == ExecutionStatus.COMPLETED
        assert result.result["output"] == "success"
        assert result.started_at == start_time
        assert result.error is None

    def test_result_properties(self):
        """Test result properties."""
        # Successful result
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )
        assert result.is_successful is True
        assert result.is_failed is False

        # Failed result
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.FAILED,
            error="Function failed",
            started_at=datetime.utcnow(),
        )
        assert result.is_successful is False
        assert result.is_failed is True

        # Timeout result
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.TIMEOUT,
            error="Function timed out",
            started_at=datetime.utcnow(),
        )
        assert result.is_successful is False
        assert result.is_failed is True

    def test_execution_result_validation(self):
        """Test execution result consistency validation."""
        # Failed execution without error message should fail
        with pytest.raises(ValidationError) as exc_info:
            ExecutionResult(
                request_id="req-123",
                function_name="test_func",
                status=ExecutionStatus.FAILED,
                started_at=datetime.utcnow(),
            )
        assert "Failed executions must have error message" in str(exc_info.value)

        # Failed execution with error message should succeed
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.FAILED,
            error="Function failed",
            started_at=datetime.utcnow(),
        )
        assert result.error == "Function failed"

        # Successful execution with error should clear error
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.COMPLETED,
            error="Previous error",
            started_at=datetime.utcnow(),
        )
        assert result.error is None

        # Completed execution should have completion time set
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )
        assert result.completed_at is not None

    def test_duration_calculation(self):
        """Test duration calculation."""
        start_time = datetime.utcnow()
        result = ExecutionResult(
            request_id="req-123", function_name="test_func", status=ExecutionStatus.COMPLETED, started_at=start_time
        )

        # Should have completion time and execution time set automatically
        assert result.completed_at is not None
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

        # Test duration_seconds property
        duration = result.duration_seconds
        assert duration is not None
        assert duration >= 0


class TestFunctionRegistry:
    """Test FunctionRegistry model."""

    def test_function_registry_creation(self):
        """Test basic function registry creation."""
        registry = FunctionRegistry()

        assert len(registry.functions) == 0
        assert isinstance(registry.last_updated, datetime)
        assert registry.version == "1.0.0"
        assert registry.function_count == 0

    def test_register_function(self):
        """Test function registration."""
        registry = FunctionRegistry()
        signature = FunctionSignature(name="test_func", module="test_module", function_type=FunctionType.BUILTIN)

        registry.register_function(signature)

        assert len(registry.functions) == 1
        assert "test_func" in registry.functions
        assert registry.functions["test_func"] == signature
        assert registry.function_count == 1

    def test_unregister_function(self):
        """Test function unregistration."""
        registry = FunctionRegistry()
        signature = FunctionSignature(name="test_func", module="test_module", function_type=FunctionType.BUILTIN)

        # Register and then unregister
        registry.register_function(signature)
        assert registry.function_count == 1

        success = registry.unregister_function("test_func")
        assert success is True
        assert registry.function_count == 0
        assert "test_func" not in registry.functions

        # Try to unregister non-existent function
        success = registry.unregister_function("nonexistent")
        assert success is False

    def test_get_function(self):
        """Test getting function by name."""
        registry = FunctionRegistry()
        signature = FunctionSignature(name="test_func", module="test_module", function_type=FunctionType.BUILTIN)

        registry.register_function(signature)

        # Get existing function
        retrieved = registry.get_function("test_func")
        assert retrieved == signature

        # Get non-existent function
        retrieved = registry.get_function("nonexistent")
        assert retrieved is None

    def test_list_functions(self):
        """Test listing functions."""
        registry = FunctionRegistry()

        builtin_func = FunctionSignature(
            name="builtin_func", module="builtin_module", function_type=FunctionType.BUILTIN
        )
        plugin_func = FunctionSignature(name="plugin_func", module="plugin_module", function_type=FunctionType.PLUGIN)

        registry.register_function(builtin_func)
        registry.register_function(plugin_func)

        # List all functions
        all_functions = registry.list_functions()
        assert len(all_functions) == 2
        assert builtin_func in all_functions
        assert plugin_func in all_functions

        # List functions by type
        builtin_functions = registry.list_functions(FunctionType.BUILTIN)
        assert len(builtin_functions) == 1
        assert builtin_functions[0] == builtin_func

        plugin_functions = registry.list_functions(FunctionType.PLUGIN)
        assert len(plugin_functions) == 1
        assert plugin_functions[0] == plugin_func


class TestValidators:
    """Test core validators."""

    def test_function_signature_validator(self):
        """Test function signature validator."""
        validator = FunctionSignatureValidator(FunctionSignature)

        # Test dangerous function name warning
        dangerous_signature = FunctionSignature(
            name="delete_everything", module="dangerous_module", function_type=FunctionType.BUILTIN
        )
        result = validator.validate(dangerous_signature)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "dangerous pattern" in result.warnings[0]

        # Test large parameter count warning
        many_params = [FunctionParameter(name=f"param_{i}", type=ParameterType.STRING) for i in range(25)]
        complex_signature = FunctionSignature(
            name="complex_func", module="test_module", function_type=FunctionType.BUILTIN, parameters=many_params
        )
        result = validator.validate(complex_signature)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "Large number of parameters" in result.warnings[0]

        # Test missing description for LLM function
        llm_signature = FunctionSignature(name="ai_func", module="ai_module", function_type=FunctionType.LLM_FUNCTION)
        result = validator.validate(llm_signature)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "should have descriptions" in result.suggestions[0]

        # Test deprecated function without explanation
        deprecated_signature = FunctionSignature(
            name="old_func", module="test_module", function_type=FunctionType.BUILTIN, deprecated=True
        )
        result = validator.validate(deprecated_signature)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "deprecation reason" in result.warnings[0]

        # Test missing examples on complex function
        complex_no_examples = FunctionSignature(
            name="complex_func", module="test_module", function_type=FunctionType.BUILTIN, parameters=many_params
        )
        result = validator.validate(complex_no_examples)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "usage examples" in result.suggestions[0]

    def test_execution_context_validator(self):
        """Test execution context validator."""
        validator = ExecutionContextValidator(ExecutionContext)

        # Test short timeout warning
        short_timeout_context = ExecutionContext(request_id="req-123", function_name="test_func", timeout_seconds=2)
        result = validator.validate(short_timeout_context)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "short timeout" in result.warnings[0]

        # Test long timeout warning
        long_timeout_context = ExecutionContext(request_id="req-123", function_name="test_func", timeout_seconds=2000)
        result = validator.validate(long_timeout_context)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "long timeout" in result.warnings[0]

        # Test high retry count warning
        high_retry_context = ExecutionContext(request_id="req-123", function_name="test_func", max_retries=15)
        result = validator.validate(high_retry_context)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "High retry count" in result.warnings[0]

        # Test retry count exceeding max retries
        invalid_retry_context = ExecutionContext(
            request_id="req-123", function_name="test_func", retry_count=5, max_retries=3
        )
        result = validator.validate(invalid_retry_context)
        assert result.valid is False
        assert len(result.errors) > 0
        assert "cannot exceed max retries" in result.errors[0]

    def test_execution_result_validator(self):
        """Test execution result validator."""
        validator = ExecutionResultValidator(ExecutionResult)

        # Test long execution time warning
        long_execution_result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.utcnow(),
            execution_time_ms=400000,  # > 5 minutes
        )
        result = validator.validate(long_execution_result)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "long execution time" in result.warnings[0]

        # Test high memory usage warning
        high_memory_result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.utcnow(),
            memory_usage_mb=1500,  # > 1GB
        )
        result = validator.validate(high_memory_result)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "High memory usage" in result.warnings[0]

        # Test missing error type suggestion
        error_without_type = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.FAILED,
            error="Something went wrong",
            started_at=datetime.utcnow(),
        )
        result = validator.validate(error_without_type)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "error type" in result.suggestions[0]

        # Test sensitive information in error message
        sensitive_error_result = ExecutionResult(
            request_id="req-123",
            function_name="test_func",
            status=ExecutionStatus.FAILED,
            error="Failed to authenticate with password 'secret123'",
            started_at=datetime.utcnow(),
        )
        result = validator.validate(sensitive_error_result)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "sensitive information" in result.warnings[0]

    def test_composite_core_validator(self):
        """Test composite core validator."""
        composite_validator = create_core_validator()

        # Test with valid function signature
        signature = FunctionSignature(
            name="safe_function",
            module="safe_module",
            function_type=FunctionType.BUILTIN,
            description="A safe function for testing",
        )
        result = composite_validator.validate(signature)
        assert result.valid is True

        # Test with function signature that triggers warnings
        dangerous_signature = FunctionSignature(
            name="delete_files", module="file_module", function_type=FunctionType.BUILTIN
        )
        result = composite_validator.validate(dangerous_signature)
        assert result.valid is True
        assert len(result.warnings) > 0  # Should have warnings about dangerous name


class TestModelSerialization:
    """Test Pydantic v2 serialization methods."""

    def test_function_signature_serialization(self):
        """Test function signature serialization."""
        param = FunctionParameter(name="input_text", type=ParameterType.STRING, description="Input text", required=True)
        signature = FunctionSignature(
            name="process_text",
            module="text_processor",
            function_type=FunctionType.PLUGIN,
            parameters=[param],
            description="Process text input",
            tags=["nlp", "text"],
            version="1.0.0",
        )

        # Test model_dump
        data = signature.model_dump()
        assert data["name"] == "process_text"
        assert data["module"] == "text_processor"
        assert data["function_type"] == "plugin"
        assert len(data["parameters"]) == 1
        assert data["parameters"][0]["name"] == "input_text"

        # Test model_dump_json
        json_str = signature.model_dump_json()
        assert "process_text" in json_str
        assert "text_processor" in json_str

        # Test round trip
        signature2 = FunctionSignature.model_validate(data)
        assert signature == signature2

        signature3 = FunctionSignature.model_validate_json(json_str)
        assert signature == signature3

    def test_execution_context_serialization(self):
        """Test execution context serialization."""
        context = ExecutionContext(
            request_id="req-123",
            function_name="test_function",
            user_id="user-456",
            timeout_seconds=300,
            metadata={"source": "api", "version": "1.0"},
        )

        # Test model_dump
        data = context.model_dump()
        assert "request_id" in data
        assert "function_name" in data
        assert "user_id" in data
        assert "timeout_seconds" in data
        assert "metadata" in data
        assert "started_at" in data

        # Test round trip
        context2 = ExecutionContext.model_validate(data)
        assert context.request_id == context2.request_id
        assert context.function_name == context2.function_name
        assert context.user_id == context2.user_id
        assert context.timeout_seconds == context2.timeout_seconds
        assert context.metadata == context2.metadata

    def test_execution_result_serialization(self):
        """Test execution result serialization."""
        result = ExecutionResult(
            request_id="req-123",
            function_name="test_function",
            status=ExecutionStatus.COMPLETED,
            result={"output": "success", "count": 42},
            started_at=datetime.utcnow(),
            execution_time_ms=150.5,
            metadata={"cached": True},
        )

        # Test model_dump
        data = result.model_dump()
        assert data["request_id"] == "req-123"
        assert data["function_name"] == "test_function"
        assert data["status"] == "completed"
        assert data["result"]["output"] == "success"
        assert data["result"]["count"] == 42
        assert data["execution_time_ms"] == 150.5

        # Test round trip preserves all data
        result2 = ExecutionResult.model_validate(data)
        assert result.request_id == result2.request_id
        assert result.function_name == result2.function_name
        assert result.status == result2.status
        assert result.result == result2.result
        assert result.execution_time_ms == result2.execution_time_ms
        assert result.metadata == result2.metadata

    def test_function_registry_serialization(self):
        """Test function registry serialization."""
        registry = FunctionRegistry(version="2.0.0")

        signature1 = FunctionSignature(name="func1", module="module1", function_type=FunctionType.BUILTIN)
        signature2 = FunctionSignature(name="func2", module="module2", function_type=FunctionType.PLUGIN)

        registry.register_function(signature1)
        registry.register_function(signature2)

        # Test model_dump
        data = registry.model_dump()
        assert data["version"] == "2.0.0"
        assert len(data["functions"]) == 2
        assert "func1" in data["functions"]
        assert "func2" in data["functions"]

        # Test round trip
        registry2 = FunctionRegistry.model_validate(data)
        assert registry.version == registry2.version
        assert registry.function_count == registry2.function_count
        assert registry.functions.keys() == registry2.functions.keys()
