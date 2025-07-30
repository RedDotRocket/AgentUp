"""
Pydantic models for AgentUp services system.

This module defines all service-related data structures using Pydantic models
for type safety and validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ..types import JsonValue
from ..utils.validation import BaseValidator, CompositeValidator, ValidationResult


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceType(str, Enum):
    LLM = "llm"
    CACHE = "cache"
    DATABASE = "database"
    MCP = "mcp"
    SECURITY = "security"
    STORAGE = "storage"
    MIDDLEWARE = "middleware"
    CUSTOM = "custom"


class ServiceRegistration(BaseModel):
    name: str = Field(..., description="Service name", min_length=1, max_length=100)
    service_type: ServiceType = Field(..., description="Service type")
    version: str = Field(..., description="Service version")
    endpoint: str | None = Field(None, description="Service endpoint URL")
    health_check_url: str | None = Field(None, description="Health check endpoint")
    capabilities: list[str] = Field(default_factory=list, description="Service capabilities")
    metadata: dict[str, str] = Field(default_factory=dict, description="Service metadata")
    enabled: bool = Field(True, description="Whether service is enabled")
    priority: int = Field(50, description="Service priority (lower = higher priority)")
    dependencies: list[str] = Field(default_factory=list, description="Service dependencies")

    @field_validator("endpoint", "health_check_url")
    @classmethod
    def validate_urls(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[\w\.-]+)?(\+[\w\.-]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", v):
            raise ValueError("Service name must start with letter, contain only alphanumeric, hyphens, underscores")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("Priority must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def validate_service_config(self) -> ServiceRegistration:
        if self.service_type == ServiceType.MCP and not self.endpoint:
            raise ValueError("MCP services must have an endpoint")

        if self.health_check_url and not self.endpoint:
            raise ValueError("Health check URL requires service endpoint")

        return self


class ServiceHealth(BaseModel):
    service_name: str = Field(..., description="Service name")
    status: ServiceStatus = Field(..., description="Health status")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check time")
    response_time_ms: float | None = Field(None, description="Response time in milliseconds", ge=0)
    error_message: str | None = Field(None, description="Error message if unhealthy")
    details: dict[str, JsonValue] = Field(default_factory=dict, description="Additional health details")
    check_count: int = Field(0, description="Number of health checks performed", ge=0)
    consecutive_failures: int = Field(0, description="Consecutive failure count", ge=0)

    @field_validator("response_time_ms")
    @classmethod
    def validate_response_time(cls, v: float | None) -> float | None:
        if v is not None and v > 300000:  # 5 minutes in ms
            raise ValueError("Response time seems unreasonably high")
        return v

    @model_validator(mode="after")
    def validate_health_consistency(self) -> ServiceHealth:
        if self.status == ServiceStatus.UNHEALTHY and not self.error_message:
            raise ValueError("Unhealthy status requires error message")

        if self.status == ServiceStatus.HEALTHY and self.error_message:
            self.error_message = None  # Clear error message for healthy services

        return self


class ServiceMetrics(BaseModel):
    service_name: str = Field(..., description="Service name")
    uptime_seconds: float = Field(0, description="Service uptime in seconds", ge=0)
    request_count: int = Field(0, description="Total request count", ge=0)
    error_count: int = Field(0, description="Total error count", ge=0)
    average_response_time_ms: float = Field(0, description="Average response time", ge=0)
    peak_response_time_ms: float = Field(0, description="Peak response time", ge=0)
    memory_usage_mb: float | None = Field(None, description="Memory usage in MB", ge=0)
    cpu_usage_percent: float | None = Field(None, description="CPU usage percentage", ge=0, le=100)
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Metrics last updated")

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100

    @property
    def availability_percent(self) -> float:
        if self.request_count == 0:
            return 100.0
        successful_requests = self.request_count - self.error_count
        return (successful_requests / self.request_count) * 100

    @model_validator(mode="after")
    def validate_metrics_consistency(self) -> ServiceMetrics:
        if self.error_count > self.request_count:
            raise ValueError("Error count cannot exceed request count")

        if self.peak_response_time_ms < self.average_response_time_ms:
            raise ValueError("Peak response time cannot be less than average")

        return self


class ServiceDependency(BaseModel):
    service_name: str = Field(..., description="Service name")
    depends_on: str = Field(..., description="Dependency service name")
    dependency_type: str = Field("required", description="Dependency type")
    timeout_seconds: int = Field(30, description="Dependency check timeout", gt=0)
    retry_attempts: int = Field(3, description="Retry attempts for dependency", ge=0)
    critical: bool = Field(True, description="Whether dependency is critical")

    @field_validator("dependency_type")
    @classmethod
    def validate_dependency_type(cls, v: str) -> str:
        valid_types = {"required", "optional", "weak", "strong"}
        if v not in valid_types:
            raise ValueError(f"Dependency type must be one of {valid_types}")
        return v


class ServiceConfiguration(BaseModel):
    registration: ServiceRegistration = Field(..., description="Service registration data")
    health_config: dict[str, Any] = Field(
        default_factory=lambda: {"check_interval": 30, "timeout": 10, "failure_threshold": 3, "recovery_threshold": 2},
        description="Health check configuration",
    )
    metrics_config: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "collection_interval": 60, "retention_days": 30},
        description="Metrics collection configuration",
    )
    dependencies: list[ServiceDependency] = Field(default_factory=list, description="Service dependencies")
    custom_config: dict[str, JsonValue] = Field(default_factory=dict, description="Service-specific configuration")

    @model_validator(mode="after")
    def validate_configuration(self) -> ServiceConfiguration:
        # Validate health check configuration
        health_config = self.health_config
        if health_config.get("check_interval", 0) <= 0:
            raise ValueError("Health check interval must be positive")

        if health_config.get("failure_threshold", 0) <= 0:
            raise ValueError("Failure threshold must be positive")

        # Validate metrics configuration
        metrics_config = self.metrics_config
        if metrics_config.get("enabled") and not isinstance(metrics_config.get("collection_interval"), int):
            raise ValueError("Metrics collection interval must be an integer")

        return self


# Service Validators using validation framework


class ServiceRegistrationValidator(BaseValidator[ServiceRegistration]):
    def validate(self, model: ServiceRegistration) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for reserved service names
        reserved_names = {"system", "admin", "root", "config", "health", "metrics"}
        if model.name.lower() in reserved_names:
            result.add_error(f"Service name '{model.name}' is reserved", "name")

        # Validate capabilities format
        for capability in model.capabilities:
            if not capability or not capability.replace("_", "").replace("-", "").isalnum():
                result.add_error(f"Invalid capability format: '{capability}'", "capabilities")

        # Check dependency cycles (basic check)
        if model.name in model.dependencies:
            result.add_error("Service cannot depend on itself", "dependencies")

        # Validate metadata keys
        for key in model.metadata.keys():
            if not key.replace("_", "").replace("-", "").isalnum():
                result.add_error(f"Invalid metadata key format: '{key}'", "metadata")

        return result


class ServiceHealthValidator(BaseValidator[ServiceHealth]):
    def validate(self, model: ServiceHealth) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check if consecutive failures are reasonable
        if model.consecutive_failures > 100:
            result.add_warning("Very high consecutive failure count - service may be persistently down")

        # Validate status transitions
        if model.status == ServiceStatus.DEGRADED and model.response_time_ms and model.response_time_ms < 100:
            result.add_suggestion("Fast response time with degraded status - consider if status is accurate")

        # Check for stale health data
        from datetime import datetime, timedelta

        if datetime.utcnow() - model.last_check > timedelta(hours=1):
            result.add_warning("Health check data is over 1 hour old")

        return result


class ServiceConfigurationValidator(BaseValidator[ServiceConfiguration]):
    def validate(self, model: ServiceConfiguration) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Validate service registration
        reg_validator = ServiceRegistrationValidator(ServiceRegistration)
        reg_result = reg_validator.validate(model.registration)
        result.merge(reg_result)

        # Check dependency cycles across all dependencies
        dependency_names = {dep.depends_on for dep in model.dependencies}
        if model.registration.name in dependency_names:
            result.add_error("Circular dependency detected", "dependencies")

        # Validate health check configuration consistency
        health_config = model.health_config
        check_interval = health_config.get("check_interval", 30)
        timeout = health_config.get("timeout", 10)

        if timeout >= check_interval:
            result.add_error("Health check timeout must be less than check interval")

        # Validate critical dependencies have reasonable timeouts
        for dep in model.dependencies:
            if dep.critical and dep.timeout_seconds > 60:
                result.add_warning(f"Critical dependency '{dep.depends_on}' has long timeout")

        return result


# Composite validator for all service models
def create_service_validator() -> CompositeValidator[ServiceConfiguration]:
    validators = [
        ServiceConfigurationValidator(ServiceConfiguration),
    ]
    return CompositeValidator(ServiceConfiguration, validators)


# Re-export key models
__all__ = [
    "ServiceStatus",
    "ServiceType",
    "ServiceRegistration",
    "ServiceHealth",
    "ServiceMetrics",
    "ServiceDependency",
    "ServiceConfiguration",
]
