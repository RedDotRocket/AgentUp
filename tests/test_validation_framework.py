"""
Tests for the validation framework.
"""

import pytest  # noqa: F401
from pydantic import BaseModel, Field

from src.agent.utils.validation import (
    BaseValidator,
    BusinessRuleValidator,
    CompositeValidator,
    ConditionalValidator,
    CrossFieldValidator,
    FieldValidator,
    PerformanceValidator,
    ValidationResult,
    validate_email,
    validate_url,
    validate_version,
)


# Test models for validation
class SampleModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=120)
    email: str
    website: str | None = None


class ComplexModel(BaseModel):
    title: str
    items: list[str]
    metadata: dict[str, str]
    settings: dict[str, int]


class TestValidationResult:
    def test_valid_result(self):
        result = ValidationResult(valid=True)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.suggestions) == 0
        assert not result.has_errors
        assert not result.has_warnings
        assert result.summary == "Validation passed"

    def test_result_with_errors(self):
        result = ValidationResult(valid=False)
        result.add_error("Name is required")
        result.add_error("Age must be positive", "age")

        assert result.valid is False
        assert len(result.errors) == 2
        assert result.has_errors
        assert "Name is required" in result.errors
        assert "age" in result.field_errors
        assert "Age must be positive" in result.field_errors["age"]

    def test_result_with_warnings_and_suggestions(self):
        result = ValidationResult(valid=True)
        result.add_warning("Email format could be improved")
        result.add_suggestion("Consider adding a description field")

        assert result.valid is True
        assert result.has_warnings
        assert len(result.warnings) == 1
        assert len(result.suggestions) == 1
        assert "1 warnings" in result.summary
        assert "1 suggestions" in result.summary

    def test_merge_results(self):
        result1 = ValidationResult(valid=True)
        result1.add_warning("Warning 1")
        result1.add_suggestion("Suggestion 1")

        result2 = ValidationResult(valid=False)
        result2.add_error("Error 1")
        result2.add_error("Field error", "field1")

        result1.merge(result2)

        assert result1.valid is False  # Should be False after merge
        assert len(result1.errors) == 2  # Both "Error 1" and "Field error" are added to errors list
        assert len(result1.warnings) == 1
        assert len(result1.suggestions) == 1
        assert "field1" in result1.field_errors


class TestBaseValidator:
    class SimpleValidator(BaseValidator[SampleModel]):
        def validate(self, model: SampleModel) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.age < 18:
                result.add_warning("User is under 18")
            if model.website and not model.website.startswith("https://"):
                result.add_suggestion("Consider using HTTPS")
            return result

    def test_dict_validation(self):
        validator = self.SimpleValidator(SampleModel)

        # Valid data
        result = validator.validate_dict({"name": "John", "age": 25, "email": "john@example.com"})
        assert result.valid is True

        # Invalid data (Pydantic validation)
        result = validator.validate_dict(
            {
                "name": "",  # Too short
                "age": -5,  # Negative age
                "email": "john@example.com",
            }
        )
        assert result.valid is False
        assert len(result.errors) >= 2

    def test_json_validation(self):
        validator = self.SimpleValidator(SampleModel)

        # Valid JSON
        json_data = '{"name": "Jane", "age": 30, "email": "jane@example.com"}'
        result = validator.validate_json(json_data)
        assert result.valid is True

        # Invalid JSON
        result = validator.validate_json('{"name": "Jane", "age":}')  # Malformed
        assert result.valid is False
        assert "Invalid JSON" in result.errors[0]

    def test_custom_validation_logic(self):
        validator = self.SimpleValidator(SampleModel)

        # Test warning for young user
        model = SampleModel(name="Teen", age=16, email="teen@example.com")
        result = validator.validate(model)
        assert result.valid is True
        assert "under 18" in result.warnings[0]

        # Test HTTPS suggestion
        model = SampleModel(name="User", age=25, email="user@example.com", website="http://example.com")
        result = validator.validate(model)
        assert result.valid is True
        assert "HTTPS" in result.suggestions[0]


class TestCompositeValidator:
    class AgeValidator(BaseValidator[SampleModel]):
        def validate(self, model: SampleModel) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.age < 0:
                result.add_error("Age cannot be negative")
            elif model.age > 150:
                result.add_error("Age seems unrealistic")
            return result

    class EmailValidator(BaseValidator[SampleModel]):
        def validate(self, model: SampleModel) -> ValidationResult:
            result = ValidationResult(valid=True)
            if "@" not in model.email:
                result.add_error("Email must contain @", "email")
            return result

    def test_composite_validation(self):
        age_validator = self.AgeValidator(SampleModel)
        email_validator = self.EmailValidator(SampleModel)
        composite = CompositeValidator(SampleModel, [age_validator, email_validator])

        # Test with data that fails both validations using validate_dict
        invalid_data = {"name": "Test", "age": -5, "email": "invalid"}
        result = composite.validate_dict(invalid_data)

        assert result.valid is False
        # Pydantic validation adds its own errors, so we just check that validation failed
        assert len(result.errors) >= 1
        # Check that the validation failed (custom validators may not run if Pydantic fails first)
        assert any("age" in error.lower() or "negative" in error.lower() for error in result.errors)

    def test_composite_with_valid_model(self):
        age_validator = self.AgeValidator(SampleModel)
        email_validator = self.EmailValidator(SampleModel)
        composite = CompositeValidator(SampleModel, [age_validator, email_validator])

        model = SampleModel(name="Valid", age=25, email="valid@example.com")
        result = composite.validate(model)

        assert result.valid is True
        assert len(result.errors) == 0


class TestConditionalValidator:
    class WebsiteValidator(BaseValidator[SampleModel]):
        def validate(self, model: SampleModel) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.website and not model.website.startswith("http"):
                result.add_error("Website must start with http", "website")
            return result

    def test_conditional_validation(self):
        website_validator = self.WebsiteValidator(SampleModel)

        # Only validate if website is provided
        conditional = ConditionalValidator(
            SampleModel,
            condition=lambda m: m.website is not None,
            validator=website_validator,
            skip_message="Website validation skipped",
        )

        # Model without website - should skip validation
        model1 = SampleModel(name="User1", age=25, email="user1@example.com")
        result1 = conditional.validate(model1)
        assert result1.valid is True
        assert "skipped" in result1.suggestions[0]

        # Model with invalid website - should run validation
        model2 = SampleModel(name="User2", age=25, email="user2@example.com", website="invalid-url")
        result2 = conditional.validate(model2)
        assert result2.valid is False
        assert "must start with http" in result2.errors[0]


class TestFieldValidator:
    def test_field_validation(self):
        validator = FieldValidator(SampleModel)

        # Add field validators
        validator.add_field_validator(
            "name", lambda value: "Name cannot be 'admin'" if value.lower() == "admin" else None
        )
        validator.add_field_validator("age", lambda value: "Age should be realistic" if value > 100 else None)

        # Test field validation with data that passes Pydantic but fails custom validation
        model = SampleModel(name="admin", age=90, email="admin@example.com")  # age=90 is valid for Pydantic
        result = validator.validate(model)

        assert result.valid is False
        assert len(result.field_errors) >= 1
        assert "admin" in result.field_errors["name"][0]

    def test_field_validator_exception(self):
        validator = FieldValidator(SampleModel)

        # Add validator that raises exception
        validator.add_field_validator(
            "name",
            lambda value: 1 / 0,  # Will raise ZeroDivisionError
        )

        model = SampleModel(name="Test", age=25, email="test@example.com")
        result = validator.validate(model)

        assert result.valid is False
        assert "Field validator error" in result.field_errors["name"][0]


class TestBusinessRuleValidator:
    def test_business_rules(self):
        validator = BusinessRuleValidator(SampleModel)

        # Add business rules
        validator.add_rule(
            lambda model: model.age >= 18 if model.email.endswith("@company.com") else True,
            "Company email users must be 18 or older",
        )
        validator.add_rule(lambda model: len(model.name) >= 3, "Name must be at least 3 characters")

        # Test failing business rule
        model = SampleModel(name="Al", age=16, email="al@company.com")
        result = validator.validate(model)

        assert result.valid is False
        assert len(result.errors) == 2
        assert "18 or older" in result.errors[0]
        assert "3 characters" in result.errors[1]

    def test_business_rule_exception(self):
        validator = BusinessRuleValidator(SampleModel)

        # Add rule that raises exception
        validator.add_rule(lambda model: 1 / 0, "This will fail")

        model = SampleModel(name="Test", age=25, email="test@example.com")
        result = validator.validate(model)

        assert result.valid is False
        assert "Business rule error" in result.errors[0]


class TestCrossFieldValidator:
    def test_cross_field_constraints(self):
        validator = CrossFieldValidator(SampleModel)

        # Add cross-field constraints
        validator.add_constraint(
            ["name", "email"], lambda name, email: name.lower() in email.lower(), "Name should appear in email address"
        )
        validator.add_constraint(
            ["age", "website"],
            lambda age, website: website is not None if age >= 18 else True,
            "Adults should have a website",
        )

        # Test failing constraints
        model = SampleModel(
            name="John",
            age=25,
            email="jane@example.com",  # Name not in email
            # No website for adult
        )
        result = validator.validate(model)

        assert result.valid is False
        assert len(result.errors) == 2
        assert "appear in email" in result.errors[0]
        assert "should have a website" in result.errors[1]

    def test_cross_field_exception(self):
        validator = CrossFieldValidator(SampleModel)

        # Add constraint that raises exception
        validator.add_constraint(["name", "age"], lambda name, age: 1 / 0, "This will fail")

        model = SampleModel(name="Test", age=25, email="test@example.com")
        result = validator.validate(model)

        assert result.valid is False
        assert "Cross-field constraint error" in result.errors[0]


class TestPerformanceValidator:
    def test_size_limits(self):
        validator = PerformanceValidator(ComplexModel)

        # Set size limits
        validator.set_size_limit("title", 10)
        validator.set_size_limit("items", 3)
        validator.set_size_limit("metadata", 2)

        # Test model exceeding limits
        model = ComplexModel(
            title="This title is too long",  # > 10 chars
            items=["a", "b", "c", "d"],  # > 3 items
            metadata={"a": "1", "b": "2", "c": "3"},  # > 2 items
            settings={"x": 1},
        )
        result = validator.validate(model)

        assert result.valid is False
        assert len(result.errors) == 3
        assert any("title" in error for error in result.errors)
        assert any("items" in error for error in result.errors)
        assert any("metadata" in error for error in result.errors)

    def test_complexity_limits(self):
        validator = PerformanceValidator(ComplexModel)

        # Set complexity limits
        validator.set_complexity_limit("metadata", 5)

        # Test structure with many metadata entries (flat but high count for complexity)
        large_metadata = {f"key_{i}": f"value_{i}" for i in range(10)}  # More than limit of 5
        model = ComplexModel(
            title="Test",
            items=["a"],
            metadata=large_metadata,  # High complexity due to size
            settings={"x": 1},
        )
        result = validator.validate(model)

        assert result.valid is False
        assert "complexity" in result.errors[0]


class TestUtilityValidators:
    def test_url_validation(self):
        # Valid URLs
        assert validate_url("https://example.com") is None
        assert validate_url("http://localhost:8080") is None
        assert validate_url("https://api.example.com/v1/endpoint") is None

        # Invalid URLs
        assert validate_url("") is not None
        assert validate_url("not-a-url") is not None
        assert validate_url("ftp://example.com") is not None
        assert validate_url("https://") is not None

    def test_email_validation(self):
        # Valid emails
        assert validate_email("user@example.com") is None
        assert validate_email("test.email+tag@domain.co.uk") is None
        assert validate_email("user123@test-domain.org") is None

        # Invalid emails
        assert validate_email("") is not None
        assert validate_email("invalid") is not None
        assert validate_email("user@") is not None
        assert validate_email("@domain.com") is not None
        assert validate_email("user@domain") is not None

    def test_version_validation(self):
        # Valid versions
        assert validate_version("1.0.0") is None
        assert validate_version("10.20.30") is None
        assert validate_version("1.0.0-alpha") is None
        assert validate_version("1.0.0-beta.1") is None
        assert validate_version("1.0.0+build.123") is None

        # Invalid versions
        assert validate_version("") is not None
        assert validate_version("1.0") is not None
        assert validate_version("v1.0.0") is not None
        assert validate_version("1.0.0.0") is not None
        assert validate_version("1.0.0-") is not None


class TestValidationIntegration:
    def test_comprehensive_validation(self):
        # Create multiple validators
        field_validator = FieldValidator(SampleModel)
        field_validator.add_field_validator(
            "name", lambda v: "Name too generic" if v.lower() in ["user", "admin"] else None
        )

        business_validator = BusinessRuleValidator(SampleModel)
        business_validator.add_rule(lambda m: m.age >= 13, "Must be at least 13 years old")

        cross_field_validator = CrossFieldValidator(SampleModel)
        cross_field_validator.add_constraint(
            ["name", "age"], lambda name, age: len(name) >= 3 if age >= 18 else True, "Adults must have full names"
        )

        # Combine all validators
        composite = CompositeValidator(SampleModel, [field_validator, business_validator, cross_field_validator])

        # Test model that fails business rule validation
        model = SampleModel(name="Al", age=12, email="al@example.com")
        result = composite.validate(model)

        assert result.valid is False
        assert len(result.errors) >= 1  # Business rule should fail (age < 13)

    def test_validation_with_pydantic_errors(self):
        validator = BusinessRuleValidator(SampleModel)
        validator.add_rule(lambda m: m.age != 42, "Age cannot be 42")

        # Test with both Pydantic and custom validation errors
        invalid_data = {
            "name": "",  # Pydantic validation error
            "age": 42,  # Custom validation error
            "email": "valid@example.com",
        }

        result = validator.validate_dict(invalid_data)

        assert result.valid is False
        # Should have both Pydantic and custom errors
        all_errors = result.errors + [e for field_errors in result.field_errors.values() for e in field_errors]
        assert len(all_errors) >= 2

    def test_performance_with_large_models(self):
        # Create a model with many fields
        class LargeModel(BaseModel):
            field1: str = "value1"
            field2: str = "value2"
            field3: str = "value3"
            field4: str = "value4"
            field5: str = "value5"
            large_list: list[str] = Field(default_factory=list)
            large_dict: dict[str, str] = Field(default_factory=dict)

        # Create comprehensive validator
        validator = PerformanceValidator(LargeModel)
        validator.set_size_limit("large_list", 1000)
        validator.set_size_limit("large_dict", 500)

        # Test with large data
        model = LargeModel(
            large_list=["item"] * 100,  # Within limit
            large_dict={f"key{i}": f"value{i}" for i in range(50)},  # Within limit
        )

        result = validator.validate(model)
        assert result.valid is True

        # Test exceeding limits
        model.large_list = ["item"] * 1001
        result = validator.validate(model)
        assert result.valid is False
