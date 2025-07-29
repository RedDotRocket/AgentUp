"""
Tests for plugins models and validators.
"""

import pytest
from a2a.types import Task, TaskState, TaskStatus
from pydantic import ValidationError

from src.agent.plugins.models import (
    AIFunction,
    AIFunctionValidator,
    CapabilityContext,
    CapabilityInfo,
    CapabilityInfoValidator,
    CapabilityResult,
    CapabilityType,
    PluginInfo,
    PluginInfoValidator,
    PluginStatus,
    PluginValidationResult,
    create_plugin_validator,
)


class TestPluginStatus:
    def test_plugin_status_values(self):
        assert PluginStatus.LOADED == "loaded"
        assert PluginStatus.ENABLED == "enabled"
        assert PluginStatus.DISABLED == "disabled"
        assert PluginStatus.ERROR == "error"


class TestCapabilityType:
    def test_capability_type_values(self):
        assert CapabilityType.TEXT == "text"
        assert CapabilityType.MULTIMODAL == "multimodal"
        assert CapabilityType.AI_FUNCTION == "ai_function"
        assert CapabilityType.STREAMING == "streaming"
        assert CapabilityType.STATEFUL == "stateful"


class TestPluginInfo:
    def test_plugin_info_creation(self):
        plugin = PluginInfo(name="test-plugin", version="1.0.0", author="Test Author", description="A test plugin")

        assert plugin.name == "test-plugin"
        assert plugin.version == "1.0.0"
        assert plugin.author == "Test Author"
        assert plugin.description == "A test plugin"
        assert plugin.status == PluginStatus.LOADED
        assert plugin.error is None

    def test_plugin_name_validation(self):
        # Valid names
        valid_names = ["test-plugin", "my_plugin", "plugin123", "simple"]
        for name in valid_names:
            plugin = PluginInfo(name=name, version="1.0.0")
            assert plugin.name == name

        # Invalid names
        invalid_names = ["Test-Plugin", "PLUGIN", "123plugin", "-invalid", "plugin!"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                PluginInfo(name=name, version="1.0.0")

    def test_version_validation(self):
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-alpha", "1.0.0-beta.1", "1.0.0+build.123"]
        for version in valid_versions:
            plugin = PluginInfo(name="test-plugin", version=version)
            assert plugin.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                PluginInfo(name="test-plugin", version=version)

    def test_plugin_status_consistency(self):
        # ERROR status without error message should fail
        with pytest.raises(ValidationError) as exc_info:
            PluginInfo(name="test-plugin", version="1.0.0", status=PluginStatus.ERROR)
        assert "ERROR status requires error message" in str(exc_info.value)

        # ERROR status with error message should succeed
        plugin = PluginInfo(
            name="test-plugin", version="1.0.0", status=PluginStatus.ERROR, error="Plugin failed to load"
        )
        assert plugin.error == "Plugin failed to load"

        # Non-error status with error message should clear error
        plugin = PluginInfo(name="test-plugin", version="1.0.0", status=PluginStatus.LOADED, error="Previous error")
        assert plugin.error is None


class TestCapabilityInfo:
    def test_capability_info_creation(self):
        capability = CapabilityInfo(
            id="text_processor",
            name="Text Processor",
            version="1.0.0",
            description="Processes text input",
            capabilities=[CapabilityType.TEXT],
        )

        assert capability.id == "text_processor"
        assert capability.name == "Text Processor"
        assert capability.version == "1.0.0"
        assert capability.description == "Processes text input"
        assert CapabilityType.TEXT in capability.capabilities
        assert capability.priority == 50

    def test_capability_id_validation(self):
        # Valid IDs
        valid_ids = ["text_processor", "AI-Function", "simple123", "MyCapability"]
        for cap_id in valid_ids:
            capability = CapabilityInfo(id=cap_id, name="Test Capability", version="1.0.0")
            assert capability.id == cap_id

        # Invalid IDs
        invalid_ids = ["123invalid", "-invalid", "cap id", "cap!"]
        for cap_id in invalid_ids:
            with pytest.raises(ValidationError):
                CapabilityInfo(id=cap_id, name="Test Capability", version="1.0.0")

    def test_version_validation(self):
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-alpha"]
        for version in valid_versions:
            capability = CapabilityInfo(id="test_capability", name="Test Capability", version=version)
            assert capability.version == version

        # Invalid versions
        invalid_versions = ["1.0", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                CapabilityInfo(id="test_capability", name="Test Capability", version=version)

    def test_mode_validation(self):
        # Valid modes
        valid_modes = ["text", "json", "binary", "stream", "multimodal"]
        for mode in valid_modes:
            capability = CapabilityInfo(
                id="test_capability", name="Test Capability", version="1.0.0", input_mode=mode, output_mode=mode
            )
            assert capability.input_mode == mode
            assert capability.output_mode == mode

        # Invalid mode
        with pytest.raises(ValidationError):
            CapabilityInfo(id="test_capability", name="Test Capability", version="1.0.0", input_mode="invalid_mode")

    def test_priority_validation(self):
        # Valid priority
        capability = CapabilityInfo(id="test_capability", name="Test Capability", version="1.0.0", priority=75)
        assert capability.priority == 75

        # Invalid priority (negative)
        with pytest.raises(ValidationError):
            CapabilityInfo(id="test_capability", name="Test Capability", version="1.0.0", priority=-1)

        # Invalid priority (too high)
        with pytest.raises(ValidationError):
            CapabilityInfo(id="test_capability", name="Test Capability", version="1.0.0", priority=150)

    def test_tags_validation(self):
        # Valid tags
        valid_tags = ["nlp", "text-processing", "ai_function"]
        capability = CapabilityInfo(id="test_capability", name="Test Capability", version="1.0.0", tags=valid_tags)
        assert capability.tags == valid_tags

        # Invalid tags
        invalid_tags = ["tag!", "tag with spaces", ""]
        with pytest.raises(ValidationError):
            CapabilityInfo(id="test_capability", name="Test Capability", version="1.0.0", tags=invalid_tags)


class TestAIFunction:
    def test_ai_function_creation(self):
        def dummy_handler(task, context):
            return {"result": "test"}

        function = AIFunction(
            name="get_weather",
            description="Get current weather for a location",
            parameters={
                "type": "object",
                "properties": {"location": {"type": "string", "description": "City name"}},
                "required": ["location"],
            },
            handler=dummy_handler,
        )

        assert function.name == "get_weather"
        assert function.description == "Get current weather for a location"
        assert function.parameters["type"] == "object"
        assert callable(function.handler)

    def test_function_name_validation(self):
        def dummy_handler(task, context):
            return {}

        # Valid names
        valid_names = ["get_weather", "calculate_sum", "process_data", "_private_func"]
        for name in valid_names:
            function = AIFunction(
                name=name, description="Test function description", parameters={"type": "object"}, handler=dummy_handler
            )
            assert function.name == name

        # Invalid names (not Python identifiers)
        invalid_names = ["123invalid", "get-weather", "function name", "func!"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                AIFunction(
                    name=name,
                    description="Test function description",
                    parameters={"type": "object"},
                    handler=dummy_handler,
                )

        # Reserved names
        reserved_names = ["eval", "exec", "import", "__import__", "compile"]
        for name in reserved_names:
            with pytest.raises(ValidationError) as exc_info:
                AIFunction(
                    name=name,
                    description="Test function description",
                    parameters={"type": "object"},
                    handler=dummy_handler,
                )
            assert f"Function name '{name}' is reserved" in str(exc_info.value)

    def test_description_validation(self):
        def dummy_handler(task, context):
            return {}

        # Valid description
        function = AIFunction(
            name="test_function",
            description="This is a valid description that meets the minimum length requirement",
            parameters={"type": "object"},
            handler=dummy_handler,
        )
        assert len(function.description) >= 10

        # Too short description
        with pytest.raises(ValidationError):
            AIFunction(
                name="test_function",
                description="Short",  # < 10 characters
                parameters={"type": "object"},
                handler=dummy_handler,
            )

    def test_parameters_schema_validation(self):
        def dummy_handler(task, context):
            return {}

        # Valid schema
        function = AIFunction(
            name="test_function",
            description="Test function description",
            parameters={"type": "object", "properties": {}},
            handler=dummy_handler,
        )
        assert "type" in function.parameters

        # Missing type property
        with pytest.raises(ValidationError) as exc_info:
            AIFunction(
                name="test_function",
                description="Test function description",
                parameters={"properties": {}},
                handler=dummy_handler,
            )
        assert "Parameters schema must have 'type' property" in str(exc_info.value)


class TestCapabilityContext:
    def test_capability_context_creation(self):
        task = Task(id="test-task", context_id="test-context", status=TaskStatus(state=TaskState.submitted))

        context = CapabilityContext(task=task, config={"setting": "value"}, state={"current": "state"})

        assert context.task.id == "test-task"
        assert context.config["setting"] == "value"
        assert context.state["current"] == "state"
        assert context.services == {}
        assert context.metadata == {}


class TestCapabilityResult:
    def test_capability_result_creation(self):
        result = CapabilityResult(content="Operation completed successfully", success=True, metadata={"duration": 0.5})

        assert result.content == "Operation completed successfully"
        assert result.success is True
        assert result.error is None
        assert result.metadata["duration"] == 0.5

    def test_result_consistency_validation(self):
        # Failed result without error message should fail
        with pytest.raises(ValidationError) as exc_info:
            CapabilityResult(content="Failed result", success=False)
        assert "Failed execution must have error message" in str(exc_info.value)

        # Failed result with error message should succeed
        result = CapabilityResult(content="Failed result", success=False, error="Operation failed")
        assert result.error == "Operation failed"

        # Successful result with error message should clear error
        result = CapabilityResult(content="Successful result", success=True, error="Previous error")
        assert result.error is None


class TestPluginValidationResult:
    def test_validation_result_creation(self):
        result = PluginValidationResult(valid=True, warnings=["Minor issue"], suggestions=["Consider improvement"])

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert len(result.suggestions) == 1

    def test_validation_result_properties(self):
        result = PluginValidationResult(valid=False, errors=["Critical error"], warnings=["Warning message"])

        assert result.has_errors is True
        assert result.has_warnings is True
        assert "1 errors" in result.summary

        # Test successful validation
        success_result = PluginValidationResult(valid=True)
        assert success_result.has_errors is False
        assert success_result.has_warnings is False
        assert success_result.summary == "Validation passed"


class TestValidators:
    def test_plugin_info_validator(self):
        validator = PluginInfoValidator(PluginInfo)

        # Test suspicious name warning
        suspicious_plugin = PluginInfo(name="malware-detector", version="1.0.0")
        result = validator.validate(suspicious_plugin)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "suspicious pattern" in result.warnings[0]

        # Test missing author suggestion
        enabled_plugin = PluginInfo(name="test-plugin", version="1.0.0", status=PluginStatus.ENABLED)
        result = validator.validate(enabled_plugin)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "author information" in result.suggestions[0]

        # Test long error message warning
        error_plugin = PluginInfo(
            name="test-plugin",
            version="1.0.0",
            status=PluginStatus.ERROR,
            error="x" * 600,  # Very long error
        )
        result = validator.validate(error_plugin)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "very long" in result.warnings[0]

    def test_capability_info_validator(self):
        validator = CapabilityInfoValidator(CapabilityInfo)

        # Test missing description suggestion for AI functions
        ai_capability = CapabilityInfo(
            id="ai_function", name="AI Function", version="1.0.0", capabilities=[CapabilityType.AI_FUNCTION]
        )
        result = validator.validate(ai_capability)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "should have descriptions" in result.suggestions[0]

        # Test low priority warning for AI functions
        low_priority_ai = CapabilityInfo(
            id="ai_function",
            name="AI Function",
            version="1.0.0",
            capabilities=[CapabilityType.AI_FUNCTION],
            priority=10,
        )
        result = validator.validate(low_priority_ai)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "higher priority" in result.warnings[0]

        # Test excessive scopes warning
        many_scopes_capability = CapabilityInfo(
            id="capability", name="Capability", version="1.0.0", required_scopes=[f"scope_{i}" for i in range(15)]
        )
        result = validator.validate(many_scopes_capability)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "many scopes" in result.warnings[0]

        # Test meaningless tags suggestion
        meaningless_tags_capability = CapabilityInfo(
            id="capability", name="Capability", version="1.0.0", tags=["test", "debug", "useful-tag"]
        )
        result = validator.validate(meaningless_tags_capability)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "more descriptive tag" in result.suggestions[0]

    def test_ai_function_validator(self):
        validator = AIFunctionValidator(AIFunction)

        def dummy_handler(task, context):
            return {}

        # Test dangerous function name warning
        dangerous_function = AIFunction(
            name="delete_files",
            description="This function deletes files from the system",
            parameters={"type": "object"},
            handler=dummy_handler,
        )
        result = validator.validate(dangerous_function)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "dangerous pattern" in result.warnings[0]

        # Test complex parameters warning
        complex_params = {"type": "object", "properties": {f"param_{i}": {"type": "string"} for i in range(100)}}
        complex_function = AIFunction(
            name="complex_function",
            description="A function with very complex parameters",
            parameters=complex_params,
            handler=dummy_handler,
        )
        result = validator.validate(complex_function)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "very complex" in result.warnings[0]

        # Test missing examples suggestion
        complex_no_examples = AIFunction(
            name="complex_function",
            description="A function with complex parameters but no examples",
            parameters=complex_params,
            handler=dummy_handler,
            examples=[],
        )
        result = validator.validate(complex_no_examples)
        assert result.valid is True
        assert len(result.suggestions) > 0
        assert "usage examples" in result.suggestions[0]

    def test_composite_plugin_validator(self):
        composite_validator = create_plugin_validator()

        # Test with valid plugin
        plugin = PluginInfo(name="test-plugin", version="1.0.0", author="Test Author")
        result = composite_validator.validate(plugin)
        assert result.valid is True

        # Test with plugin that triggers warnings
        suspicious_plugin = PluginInfo(name="virus-scanner", version="1.0.0", status=PluginStatus.ENABLED)
        result = composite_validator.validate(suspicious_plugin)
        assert result.valid is True
        assert len(result.warnings) > 0  # Should have warnings about suspicious name
        assert len(result.suggestions) > 0  # Should have suggestion about missing author


class TestModelSerialization:
    def test_plugin_info_serialization(self):
        plugin = PluginInfo(name="test-plugin", version="1.0.0", author="Test Author", status=PluginStatus.ENABLED)

        # Test model_dump
        data = plugin.model_dump()
        assert data["name"] == "test-plugin"
        assert data["version"] == "1.0.0"
        assert data["author"] == "Test Author"
        assert data["status"] == "enabled"

        # Test model_dump_json
        json_str = plugin.model_dump_json()
        assert "test-plugin" in json_str
        assert "enabled" in json_str

        # Test round trip
        plugin2 = PluginInfo.model_validate(data)
        assert plugin == plugin2

        plugin3 = PluginInfo.model_validate_json(json_str)
        assert plugin == plugin3

    def test_capability_info_serialization(self):
        capability = CapabilityInfo(
            id="text_processor",
            name="Text Processor",
            version="1.0.0",
            capabilities=[CapabilityType.TEXT, CapabilityType.AI_FUNCTION],
            priority=75,
        )

        # Test model_dump with exclude_unset
        data = capability.model_dump(exclude_unset=True)
        assert "id" in data
        assert "name" in data
        assert "capabilities" in data
        assert "priority" in data

        # Test round trip
        capability2 = CapabilityInfo.model_validate(data)
        assert capability.id == capability2.id
        assert capability.name == capability2.name
        assert capability.capabilities == capability2.capabilities
        assert capability.priority == capability2.priority

    def test_ai_function_serialization(self):
        def dummy_handler(task, context):
            return {"result": "test"}

        function = AIFunction(
            name="test_function",
            description="Test function for serialization",
            parameters={"type": "object", "properties": {}},
            handler=dummy_handler,
        )

        # Test model_dump (handler should be included as arbitrary type)
        data = function.model_dump()
        assert data["name"] == "test_function"
        assert data["description"] == "Test function for serialization"
        assert data["parameters"]["type"] == "object"
        # Handler should be present but may not be serializable
        assert "handler" in data
