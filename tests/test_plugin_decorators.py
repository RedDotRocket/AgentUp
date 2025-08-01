"""
Test suite for the @capability decorator and metadata validation.

Tests the core decorator functionality that replaces the Pluggy hook system.
"""

from src.agent.plugins.decorators import (
    CapabilityMetadata,
    ai_function,
    capability,
    get_capability_metadata,
    is_capability_handler,
    validate_capability_metadata,
)
from src.agent.plugins.models import CapabilityType


class TestCapabilityDecorator:
    """Test the @capability decorator functionality."""

    def test_basic_capability_decorator(self):
        """Test basic @capability decorator application."""

        @capability("test_id", name="Test Capability", description="Test description")
        def test_method():
            return "test result"

        # Check that decorator was applied
        assert hasattr(test_method, "_agentup_capabilities")
        assert hasattr(test_method, "_is_agentup_capability")
        assert test_method._is_agentup_capability is True

        # Check metadata
        capabilities = get_capability_metadata(test_method)
        assert len(capabilities) == 1

        cap_meta = capabilities[0]
        assert cap_meta.id == "test_id"
        assert cap_meta.name == "Test Capability"
        assert cap_meta.description == "Test description"
        assert cap_meta.method_name == "test_method"

    def test_capability_decorator_with_all_parameters(self):
        """Test @capability decorator with all parameters."""

        @capability(
            "full_test",
            name="Full Test",
            description="Full test description",
            scopes=["test:read", "test:write"],
            ai_function=True,
            ai_parameters={"type": "object", "properties": {"param": {"type": "string"}}},
            input_mode="json",
            output_mode="stream",
            tags=["test", "example"],
            priority=75,
            middleware=[{"type": "rate_limit", "limit": 10}],
            config_schema={"type": "object"},
            state_schema={"type": "object", "properties": {"count": {"type": "integer"}}},
            streaming=True,
            multimodal=True,
        )
        def full_test_method():
            pass

        capabilities = get_capability_metadata(full_test_method)
        cap_meta = capabilities[0]

        assert cap_meta.id == "full_test"
        assert cap_meta.name == "Full Test"
        assert cap_meta.description == "Full test description"
        assert cap_meta.scopes == ["test:read", "test:write"]
        assert cap_meta.ai_function is True
        assert cap_meta.ai_parameters == {"type": "object", "properties": {"param": {"type": "string"}}}
        assert cap_meta.input_mode == "json"
        assert cap_meta.output_mode == "stream"
        assert cap_meta.tags == ["test", "example"]
        assert cap_meta.priority == 75
        assert cap_meta.middleware == [{"type": "rate_limit", "limit": 10}]
        assert cap_meta.config_schema == {"type": "object"}
        assert cap_meta.state_schema == {"type": "object", "properties": {"count": {"type": "integer"}}}
        assert cap_meta.streaming is True
        assert cap_meta.multimodal is True

    def test_capability_decorator_defaults(self):
        """Test @capability decorator with minimal parameters using defaults."""

        @capability("minimal")
        def minimal_method():
            """Method docstring"""
            pass

        capabilities = get_capability_metadata(minimal_method)
        cap_meta = capabilities[0]

        assert cap_meta.id == "minimal"
        assert cap_meta.name == "Minimal"  # Generated from ID
        assert cap_meta.description == "Method docstring"  # From docstring
        assert cap_meta.scopes == []
        assert cap_meta.ai_function is False
        assert cap_meta.ai_parameters == {}
        assert cap_meta.input_mode == "text"
        assert cap_meta.output_mode == "text"
        assert cap_meta.tags == []
        assert cap_meta.priority == 50
        assert cap_meta.middleware == []
        assert cap_meta.streaming is False
        assert cap_meta.multimodal is False

    def test_capability_decorator_fallback_description(self):
        """Test @capability decorator fallback description generation."""

        @capability("no_desc")
        def method_without_docstring():
            pass

        capabilities = get_capability_metadata(method_without_docstring)
        cap_meta = capabilities[0]

        assert cap_meta.description == "Capability no_desc"  # Fallback description

    def test_multiple_capabilities_on_single_method(self):
        """Test applying multiple @capability decorators to one method."""

        @capability("first", name="First Capability")
        @capability("second", name="Second Capability")
        def multi_capability_method():
            pass

        capabilities = get_capability_metadata(multi_capability_method)
        assert len(capabilities) == 2

        # Should be in reverse order due to decorator stacking
        assert capabilities[0].id == "second"
        assert capabilities[1].id == "first"

    def test_is_capability_handler_utility(self):
        """Test is_capability_handler utility function."""

        @capability("test")
        def decorated_method():
            pass

        def regular_method():
            pass

        assert is_capability_handler(decorated_method) is True
        assert is_capability_handler(regular_method) is False


class TestAIFunctionDecorator:
    """Test the @ai_function decorator functionality."""

    def test_ai_function_decorator_basic(self):
        """Test basic @ai_function decorator."""

        @ai_function(
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            name="test_ai",
            description="Test AI function",
        )
        def ai_test_method():
            pass

        capabilities = get_capability_metadata(ai_test_method)
        assert len(capabilities) == 1

        cap_meta = capabilities[0]
        assert cap_meta.id == "ai_test_method"  # From method name
        assert cap_meta.name == "test_ai"
        assert cap_meta.description == "Test AI function"
        assert cap_meta.ai_function is True
        assert cap_meta.ai_parameters == {"type": "object", "properties": {"text": {"type": "string"}}}

    def test_ai_function_decorator_defaults(self):
        """Test @ai_function decorator with defaults."""

        @ai_function(parameters={"type": "object"})
        def analyze_text():
            """Analyze the given text"""
            pass

        capabilities = get_capability_metadata(analyze_text)
        cap_meta = capabilities[0]

        assert cap_meta.id == "analyze_text"
        assert cap_meta.name == "Analyze Text"  # Generated from method name
        assert cap_meta.description == "Analyze the given text"  # From docstring
        assert cap_meta.ai_function is True
        assert cap_meta.ai_parameters == {"type": "object"}


class TestCapabilityMetadata:
    """Test CapabilityMetadata dataclass and methods."""

    def test_capability_metadata_creation(self):
        """Test CapabilityMetadata creation with required fields."""
        metadata = CapabilityMetadata(
            id="test_cap", name="Test Capability", description="A test capability", method_name="test_method"
        )

        assert metadata.id == "test_cap"
        assert metadata.name == "Test Capability"
        assert metadata.description == "A test capability"
        assert metadata.method_name == "test_method"
        assert metadata.scopes == []  # Default empty list
        assert metadata.handler is None

    def test_to_capability_types_conversion(self):
        """Test CapabilityMetadata.to_capability_types() method."""
        # Basic text capability
        basic_meta = CapabilityMetadata(id="basic", name="Basic", description="Basic", method_name="basic")
        types = basic_meta.to_capability_types()
        assert CapabilityType.TEXT in types
        assert len(types) == 1

        # AI function capability
        ai_meta = CapabilityMetadata(id="ai", name="AI", description="AI", method_name="ai", ai_function=True)
        types = ai_meta.to_capability_types()
        assert CapabilityType.TEXT in types
        assert CapabilityType.AI_FUNCTION in types

        # Streaming capability
        stream_meta = CapabilityMetadata(
            id="stream", name="Stream", description="Stream", method_name="stream", streaming=True
        )
        types = stream_meta.to_capability_types()
        assert CapabilityType.TEXT in types
        assert CapabilityType.STREAMING in types

        # Multimodal capability
        multi_meta = CapabilityMetadata(
            id="multi", name="Multi", description="Multi", method_name="multi", multimodal=True
        )
        types = multi_meta.to_capability_types()
        assert CapabilityType.TEXT in types
        assert CapabilityType.MULTIMODAL in types

        # Stateful capability
        state_meta = CapabilityMetadata(
            id="state", name="State", description="State", method_name="state", state_schema={"type": "object"}
        )
        types = state_meta.to_capability_types()
        assert CapabilityType.TEXT in types
        assert CapabilityType.STATEFUL in types

        # Combined capability
        combined_meta = CapabilityMetadata(
            id="combined",
            name="Combined",
            description="Combined",
            method_name="combined",
            ai_function=True,
            streaming=True,
            multimodal=True,
            state_schema={"type": "object"},
        )
        types = combined_meta.to_capability_types()
        assert CapabilityType.TEXT in types
        assert CapabilityType.AI_FUNCTION in types
        assert CapabilityType.STREAMING in types
        assert CapabilityType.MULTIMODAL in types
        assert CapabilityType.STATEFUL in types


class TestCapabilityValidation:
    """Test validate_capability_metadata function."""

    def test_valid_capability_metadata(self):
        """Test validation of valid capability metadata."""
        valid_meta = CapabilityMetadata(
            id="valid_capability",
            name="Valid Capability",
            description="A valid capability",
            method_name="valid_method",
            scopes=["resource:action"],
            ai_function=True,
            ai_parameters={"type": "object", "properties": {"param": {"type": "string"}}},
            input_mode="text",
            output_mode="json",
            tags=["valid", "test"],
            priority=75,
        )

        errors = validate_capability_metadata(valid_meta)
        assert errors == []

    def test_invalid_capability_id(self):
        """Test validation of invalid capability IDs."""
        # Empty ID
        invalid_meta = CapabilityMetadata(id="", name="Test", description="Test", method_name="test")
        errors = validate_capability_metadata(invalid_meta)
        assert any("Invalid capability ID" in error for error in errors)

        # Invalid characters
        invalid_meta.id = "invalid!@#"
        errors = validate_capability_metadata(invalid_meta)
        assert any("Invalid capability ID" in error for error in errors)

        # Valid IDs should pass
        for valid_id in ["valid", "valid_id", "valid-id", "valid123"]:
            invalid_meta.id = valid_id
            errors = validate_capability_metadata(invalid_meta)
            assert not any("Invalid capability ID" in error for error in errors)

    def test_invalid_input_output_modes(self):
        """Test validation of invalid input/output modes."""
        meta = CapabilityMetadata(
            id="test",
            name="Test",
            description="Test",
            method_name="test",
            input_mode="invalid_mode",
            output_mode="another_invalid",
        )

        errors = validate_capability_metadata(meta)
        assert any("Invalid input_mode" in error for error in errors)
        assert any("Invalid output_mode" in error for error in errors)

    def test_invalid_priority_range(self):
        """Test validation of priority out of range."""
        # Too low
        meta = CapabilityMetadata(id="test", name="Test", description="Test", method_name="test", priority=-1)
        errors = validate_capability_metadata(meta)
        assert any("Invalid priority" in error for error in errors)

        # Too high
        meta.priority = 101
        errors = validate_capability_metadata(meta)
        assert any("Invalid priority" in error for error in errors)

    def test_ai_function_validation(self):
        """Test AI function specific validations."""
        # AI function without parameters
        meta = CapabilityMetadata(id="test", name="Test", description="Test", method_name="test", ai_function=True)
        errors = validate_capability_metadata(meta)
        assert any("AI functions must specify ai_parameters" in error for error in errors)

        # Invalid ai_parameters type
        meta.ai_parameters = "not a dict"
        errors = validate_capability_metadata(meta)
        assert any("ai_parameters must be a dictionary" in error for error in errors)

        # Missing 'type' in ai_parameters
        meta.ai_parameters = {"properties": {}}
        errors = validate_capability_metadata(meta)
        assert any("ai_parameters must have 'type' property" in error for error in errors)

    def test_invalid_tags(self):
        """Test validation of invalid tags."""
        meta = CapabilityMetadata(
            id="test", name="Test", description="Test", method_name="test", tags=["valid", "invalid!@#", ""]
        )

        errors = validate_capability_metadata(meta)
        assert any("Invalid tag format: 'invalid!@#'" in error for error in errors)
        assert any("Invalid tag format: ''" in error for error in errors)

    def test_invalid_scopes(self):
        """Test validation of invalid scopes."""
        meta = CapabilityMetadata(
            id="test", name="Test", description="Test", method_name="test", scopes=["valid:scope", "invalid_scope", ""]
        )

        errors = validate_capability_metadata(meta)
        assert any("Invalid scope format: 'invalid_scope'" in error for error in errors)
        assert any("Invalid scope format: ''" in error for error in errors)


class TestGetCapabilityMetadata:
    """Test get_capability_metadata utility function."""

    def test_get_metadata_from_decorated_function(self):
        """Test getting metadata from decorated function."""

        @capability("test", name="Test")
        def decorated_func():
            pass

        metadata_list = get_capability_metadata(decorated_func)
        assert len(metadata_list) == 1
        assert metadata_list[0].id == "test"

    def test_get_metadata_from_undecorated_function(self):
        """Test getting metadata from undecorated function."""

        def regular_func():
            pass

        metadata_list = get_capability_metadata(regular_func)
        assert metadata_list == []


class TestDecoratorIntegration:
    """Test decorator integration with Plugin system."""

    def test_decorator_preserves_function_metadata(self):
        """Test that decorators preserve original function metadata."""

        @capability("preserve_test", name="Preserve Test")
        def original_function():
            """Original docstring"""
            return "original result"

        # Function should still be callable
        result = original_function()
        assert result == "original result"

        # Original metadata should be preserved
        assert original_function.__name__ == "original_function"
        assert original_function.__doc__ == "Original docstring"

    def test_decorator_handler_binding(self):
        """Test that decorator correctly binds handler reference."""

        @capability("handler_test")
        def test_handler():
            pass

        capabilities = get_capability_metadata(test_handler)
        cap_meta = capabilities[0]

        # Handler should be bound to the original function
        assert cap_meta.handler == test_handler
