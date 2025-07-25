"""
Validation framework for AgentUp Pydantic models.

This module provides base validation classes and utilities for comprehensive
model validation beyond Pydantic's built-in capabilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ValidationError

# Generic type for model validators
T = TypeVar("T", bound=BaseModel)


class ValidationResult(BaseModel):
    """Result of model validation with detailed feedback."""

    valid: bool = Field(..., description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions")
    field_errors: dict[str, list[str]] = Field(default_factory=dict, description="Field-specific errors")

    def add_error(self, message: str, field: str | None = None) -> None:
        """Add a validation error."""
        self.valid = False
        self.errors.append(message)
        if field:
            if field not in self.field_errors:
                self.field_errors[field] = []
            self.field_errors[field].append(message)

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    def add_suggestion(self, message: str) -> None:
        """Add an improvement suggestion."""
        self.suggestions.append(message)

    def merge(self, other: ValidationResult) -> None:
        """Merge another validation result into this one."""
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.suggestions.extend(other.suggestions)

        # Merge field errors
        for field, field_errors in other.field_errors.items():
            if field not in self.field_errors:
                self.field_errors[field] = []
            self.field_errors[field].extend(field_errors)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0 or len(self.field_errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    @property
    def summary(self) -> str:
        """Get a summary of the validation result."""
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} errors")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warnings")
        if self.suggestions:
            parts.append(f"{len(self.suggestions)} suggestions")

        if not parts:
            return "Validation passed"
        return f"Validation completed with {', '.join(parts)}"


class BaseValidator(ABC, Generic[T]):
    """Abstract base validator for all models."""

    def __init__(self, model_class: type[T]):
        """Initialize validator with model class."""
        self.model_class = model_class

    @abstractmethod
    def validate(self, model: T) -> ValidationResult:
        """Validate a model instance.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult with validation details
        """
        pass

    def validate_dict(self, data: dict[str, Any]) -> ValidationResult:
        """Validate a dictionary against the model.

        Args:
            data: Dictionary data to validate

        Returns:
            ValidationResult with validation details
        """
        try:
            model = self.model_class(**data)
            return self.validate(model)
        except ValidationError as e:
            result = ValidationResult(valid=False)
            for error in e.errors():
                field_path = ".".join(str(loc) for loc in error["loc"])
                message = f"{field_path}: {error['msg']}"
                result.add_error(message, field_path)
            return result
        except Exception as e:
            result = ValidationResult(valid=False)
            result.add_error(f"Unexpected validation error: {str(e)}")
            return result

    def validate_json(self, json_data: str) -> ValidationResult:
        """Validate JSON string against the model.

        Args:
            json_data: JSON string to validate

        Returns:
            ValidationResult with validation details
        """
        try:
            import json

            data = json.loads(json_data)
            return self.validate_dict(data)
        except json.JSONDecodeError as e:
            result = ValidationResult(valid=False)
            result.add_error(f"Invalid JSON: {str(e)}")
            return result


class CompositeValidator(BaseValidator[T]):
    """Composite validator that runs multiple validators."""

    def __init__(self, model_class: type[T], validators: list[BaseValidator[T]]):
        """Initialize with list of validators.

        Args:
            model_class: The model class to validate
            validators: List of validators to run
        """
        super().__init__(model_class)
        self.validators = validators

    def validate(self, model: T) -> ValidationResult:
        """Run all validators and combine results.

        Args:
            model: The model instance to validate

        Returns:
            Combined ValidationResult from all validators
        """
        result = ValidationResult(valid=True)

        for validator in self.validators:
            sub_result = validator.validate(model)
            result.merge(sub_result)

        return result


class ConditionalValidator(BaseValidator[T]):
    """Validator that applies conditions before validation."""

    def __init__(
        self, model_class: type[T], condition: callable, validator: BaseValidator[T], skip_message: str | None = None
    ):
        """Initialize conditional validator.

        Args:
            model_class: The model class to validate
            condition: Function that takes model and returns bool
            validator: Validator to run if condition is true
            skip_message: Message to add if validation is skipped
        """
        super().__init__(model_class)
        self.condition = condition
        self.validator = validator
        self.skip_message = skip_message

    def validate(self, model: T) -> ValidationResult:
        """Validate model if condition is met.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult from conditional validation
        """
        if not self.condition(model):
            result = ValidationResult(valid=True)
            if self.skip_message:
                result.add_suggestion(self.skip_message)
            return result

        return self.validator.validate(model)


class FieldValidator(BaseValidator[T]):
    """Validator for specific model fields."""

    def __init__(self, model_class: type[T]):
        """Initialize field validator."""
        super().__init__(model_class)
        self.field_validators: dict[str, list[callable]] = {}

    def add_field_validator(self, field_name: str, validator_func: callable) -> None:
        """Add a validator function for a specific field.

        Args:
            field_name: Name of the field to validate
            validator_func: Function that takes field value and returns str|None (error message)
        """
        if field_name not in self.field_validators:
            self.field_validators[field_name] = []
        self.field_validators[field_name].append(validator_func)

    def validate(self, model: T) -> ValidationResult:
        """Validate model fields.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult with field validation details
        """
        result = ValidationResult(valid=True)

        for field_name, validators in self.field_validators.items():
            if not hasattr(model, field_name):
                continue

            field_value = getattr(model, field_name)

            for validator_func in validators:
                try:
                    error_message = validator_func(field_value)
                    if error_message:
                        result.add_error(error_message, field_name)
                except Exception as e:
                    result.add_error(f"Field validator error: {str(e)}", field_name)

        return result


class SchemaValidator(BaseValidator[T]):
    """Validator for JSON Schema compliance."""

    def __init__(self, model_class: type[T], schema: dict[str, Any]):
        """Initialize with JSON schema.

        Args:
            model_class: The model class to validate
            schema: JSON schema to validate against
        """
        super().__init__(model_class)
        self.schema = schema

        try:
            import jsonschema

            self.jsonschema = jsonschema
        except ImportError:
            raise ImportError("jsonschema package required for SchemaValidator") from None

    def validate(self, model: T) -> ValidationResult:
        """Validate model against JSON schema.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult with schema validation details
        """
        result = ValidationResult(valid=True)

        try:
            # Convert model to dict for schema validation
            model_dict = model.dict()
            self.jsonschema.validate(model_dict, self.schema)
        except self.jsonschema.ValidationError as e:
            result.add_error(f"Schema validation error: {e.message}", e.absolute_path)
        except Exception as e:
            result.add_error(f"Schema validation failed: {str(e)}")

        return result


class BusinessRuleValidator(BaseValidator[T]):
    """Validator for business logic rules."""

    def __init__(self, model_class: type[T]):
        """Initialize business rule validator."""
        super().__init__(model_class)
        self.rules: list[callable] = []

    def add_rule(self, rule_func: callable, error_message: str | None = None) -> None:
        """Add a business rule validation function.

        Args:
            rule_func: Function that takes model and returns bool (True = valid)
            error_message: Custom error message if rule fails
        """

        def wrapper(model):
            try:
                if not rule_func(model):
                    return error_message or f"Business rule validation failed: {rule_func.__name__}"
                return None
            except Exception as e:
                return f"Business rule error: {str(e)}"

        self.rules.append(wrapper)

    def validate(self, model: T) -> ValidationResult:
        """Validate model against business rules.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult with business rule validation details
        """
        result = ValidationResult(valid=True)

        for rule in self.rules:
            error_message = rule(model)
            if error_message:
                result.add_error(error_message)

        return result


class CrossFieldValidator(BaseValidator[T]):
    """Validator for cross-field dependencies and constraints."""

    def __init__(self, model_class: type[T]):
        """Initialize cross-field validator."""
        super().__init__(model_class)
        self.constraints: list[callable] = []

    def add_constraint(self, fields: list[str], constraint_func: callable, error_message: str | None = None) -> None:
        """Add a cross-field constraint.

        Args:
            fields: List of field names involved in constraint
            constraint_func: Function that takes field values and returns bool
            error_message: Custom error message if constraint fails
        """

        def wrapper(model):
            try:
                field_values = {}
                for field in fields:
                    if hasattr(model, field):
                        field_values[field] = getattr(model, field)

                if not constraint_func(**field_values):
                    return error_message or f"Cross-field constraint failed for fields: {', '.join(fields)}"
                return None
            except Exception as e:
                return f"Cross-field constraint error: {str(e)}"

        self.constraints.append(wrapper)

    def validate(self, model: T) -> ValidationResult:
        """Validate model cross-field constraints.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult with cross-field validation details
        """
        result = ValidationResult(valid=True)

        for constraint in self.constraints:
            error_message = constraint(model)
            if error_message:
                result.add_error(error_message)

        return result


class PerformanceValidator(BaseValidator[T]):
    """Validator for performance characteristics."""

    def __init__(self, model_class: type[T]):
        """Initialize performance validator."""
        super().__init__(model_class)
        self.size_limits: dict[str, int] = {}
        self.complexity_limits: dict[str, int] = {}

    def set_size_limit(self, field_name: str, max_size: int) -> None:
        """Set size limit for a field.

        Args:
            field_name: Name of the field
            max_size: Maximum allowed size
        """
        self.size_limits[field_name] = max_size

    def set_complexity_limit(self, field_name: str, max_complexity: int) -> None:
        """Set complexity limit for a field.

        Args:
            field_name: Name of the field
            max_complexity: Maximum allowed complexity
        """
        self.complexity_limits[field_name] = max_complexity

    def validate(self, model: T) -> ValidationResult:
        """Validate model performance characteristics.

        Args:
            model: The model instance to validate

        Returns:
            ValidationResult with performance validation details
        """
        result = ValidationResult(valid=True)

        # Check size limits
        for field_name, max_size in self.size_limits.items():
            if not hasattr(model, field_name):
                continue

            field_value = getattr(model, field_name)
            size = self._calculate_size(field_value)

            if size > max_size:
                result.add_error(f"Field '{field_name}' size ({size}) exceeds limit ({max_size})", field_name)

        # Check complexity limits
        for field_name, max_complexity in self.complexity_limits.items():
            if not hasattr(model, field_name):
                continue

            field_value = getattr(model, field_name)
            complexity = self._calculate_complexity(field_value)

            if complexity > max_complexity:
                result.add_error(
                    f"Field '{field_name}' complexity ({complexity}) exceeds limit ({max_complexity})", field_name
                )

        return result

    def _calculate_size(self, value: Any) -> int:
        """Calculate size of a value."""
        if isinstance(value, str):
            return len(value)
        elif isinstance(value, list | dict | set):
            return len(value)
        elif isinstance(value, bytes):
            return len(value)
        else:
            return 1

    def _calculate_complexity(self, value: Any) -> int:
        """Calculate complexity of a value."""
        if isinstance(value, dict):
            return sum(1 + self._calculate_complexity(v) for v in value.values())
        elif isinstance(value, list):
            return sum(1 + self._calculate_complexity(item) for item in value)
        else:
            return 1


# Utility functions for common validation patterns
def validate_url(url: str) -> str | None:
    """Validate URL format.

    Args:
        url: URL to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not url:
        return "URL cannot be empty"

    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"

    # Basic URL format check
    import re

    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    if not url_pattern.match(url):
        return "Invalid URL format"

    return None


def validate_email(email: str) -> str | None:
    """Validate email format.

    Args:
        email: Email to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not email:
        return "Email cannot be empty"

    import re

    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    if not email_pattern.match(email):
        return "Invalid email format"

    return None


def validate_version(version: str) -> str | None:
    """Validate semantic version format.

    Args:
        version: Version string to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not version:
        return "Version cannot be empty"

    import re

    version_pattern = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)"
        r")?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    if not version_pattern.match(version):
        return "Invalid semantic version format (expected: major.minor.patch)"

    return None


# Re-export key classes
__all__ = [
    "ValidationResult",
    "BaseValidator",
    "CompositeValidator",
    "ConditionalValidator",
    "FieldValidator",
    "SchemaValidator",
    "BusinessRuleValidator",
    "CrossFieldValidator",
    "PerformanceValidator",
    "validate_url",
    "validate_email",
    "validate_version",
]
