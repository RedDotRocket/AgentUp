"""
Tests for services models and validators.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from src.agent.services.model import (
    ServiceConfiguration,
    ServiceConfigurationValidator,
    ServiceDependency,
    ServiceHealth,
    ServiceHealthValidator,
    ServiceMetrics,
    ServiceRegistration,
    ServiceRegistrationValidator,
    ServiceStatus,
    ServiceType,
    create_service_validator,
)


class TestServiceStatus:
    def test_service_status_values(self):
        assert ServiceStatus.HEALTHY == "healthy"
        assert ServiceStatus.DEGRADED == "degraded"
        assert ServiceStatus.UNHEALTHY == "unhealthy"
        assert ServiceStatus.UNKNOWN == "unknown"


class TestServiceType:
    def test_service_type_values(self):
        assert ServiceType.LLM == "llm"
        assert ServiceType.CACHE == "cache"
        assert ServiceType.DATABASE == "database"
        assert ServiceType.MCP == "mcp"
        assert ServiceType.SECURITY == "security"
        assert ServiceType.STORAGE == "storage"
        assert ServiceType.MIDDLEWARE == "middleware"
        assert ServiceType.CUSTOM == "custom"


class TestServiceRegistration:
    def test_service_registration_creation(self):
        registration = ServiceRegistration(
            name="test-service",
            service_type=ServiceType.LLM,
            version="1.0.0",
            endpoint="https://api.example.com",
            capabilities=["text", "completion"],
        )

        assert registration.name == "test-service"
        assert registration.service_type == ServiceType.LLM
        assert registration.version == "1.0.0"
        assert registration.endpoint == "https://api.example.com"
        assert registration.capabilities == ["text", "completion"]
        assert registration.enabled is True
        assert registration.priority == 50

    def test_service_registration_url_validation(self):
        # Valid URLs
        registration = ServiceRegistration(
            name="test-service",
            service_type=ServiceType.LLM,
            version="1.0.0",
            endpoint="https://api.example.com",
            health_check_url="http://localhost:8080/health",
        )
        assert registration.endpoint == "https://api.example.com"
        assert registration.health_check_url == "http://localhost:8080/health"

        # Invalid URLs
        with pytest.raises(ValidationError) as exc_info:
            ServiceRegistration(
                name="test-service", service_type=ServiceType.LLM, version="1.0.0", endpoint="invalid-url"
            )
        assert "URL must start with http:// or https://" in str(exc_info.value)

    def test_service_registration_version_validation(self):
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-alpha", "1.0.0-beta.1", "1.0.0+build.123"]
        for version in valid_versions:
            registration = ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version=version)
            assert registration.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version=version)

    def test_service_registration_name_validation(self):
        # Valid names
        valid_names = ["service1", "my-service", "my_service", "Service123"]
        for name in valid_names:
            registration = ServiceRegistration(name=name, service_type=ServiceType.LLM, version="1.0.0")
            assert registration.name == name

        # Invalid names
        invalid_names = ["1service", "-service", "_service", "service!", ""]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ServiceRegistration(name=name, service_type=ServiceType.LLM, version="1.0.0")

    def test_service_registration_priority_validation(self):
        # Valid priority
        registration = ServiceRegistration(
            name="test-service", service_type=ServiceType.LLM, version="1.0.0", priority=25
        )
        assert registration.priority == 25

        # Invalid priority
        with pytest.raises(ValidationError):
            ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version="1.0.0", priority=150)

    def test_mcp_service_validation(self):
        # MCP service without endpoint should fail
        with pytest.raises(ValidationError) as exc_info:
            ServiceRegistration(name="mcp-service", service_type=ServiceType.MCP, version="1.0.0")
        assert "MCP services must have an endpoint" in str(exc_info.value)

        # MCP service with endpoint should succeed
        registration = ServiceRegistration(
            name="mcp-service", service_type=ServiceType.MCP, version="1.0.0", endpoint="https://mcp.example.com"
        )
        assert registration.endpoint == "https://mcp.example.com"

    def test_health_check_url_validation(self):
        with pytest.raises(ValidationError) as exc_info:
            ServiceRegistration(
                name="test-service",
                service_type=ServiceType.LLM,
                version="1.0.0",
                health_check_url="https://health.example.com",
            )
        assert "Health check URL requires service endpoint" in str(exc_info.value)


class TestServiceHealth:
    def test_service_health_creation(self):
        health = ServiceHealth(service_name="test-service", status=ServiceStatus.HEALTHY, response_time_ms=150.5)

        assert health.service_name == "test-service"
        assert health.status == ServiceStatus.HEALTHY
        assert health.response_time_ms == 150.5
        assert health.check_count == 0
        assert health.consecutive_failures == 0
        assert isinstance(health.last_check, datetime)

    def test_service_health_response_time_validation(self):
        # Valid response time
        health = ServiceHealth(service_name="test-service", status=ServiceStatus.HEALTHY, response_time_ms=1000.0)
        assert health.response_time_ms == 1000.0

        # Invalid response time (too high)
        with pytest.raises(ValidationError) as exc_info:
            ServiceHealth(
                service_name="test-service",
                status=ServiceStatus.HEALTHY,
                response_time_ms=400000.0,  # > 5 minutes
            )
        assert "unreasonably high" in str(exc_info.value)

        # Negative response time
        with pytest.raises(ValidationError):
            ServiceHealth(service_name="test-service", status=ServiceStatus.HEALTHY, response_time_ms=-100.0)

    def test_unhealthy_status_validation(self):
        # Unhealthy without error message should fail
        with pytest.raises(ValidationError) as exc_info:
            ServiceHealth(service_name="test-service", status=ServiceStatus.UNHEALTHY)
        assert "Unhealthy status requires error message" in str(exc_info.value)

        # Unhealthy with error message should succeed
        health = ServiceHealth(
            service_name="test-service", status=ServiceStatus.UNHEALTHY, error_message="Connection timeout"
        )
        assert health.error_message == "Connection timeout"

    def test_healthy_status_clears_error(self):
        health = ServiceHealth(
            service_name="test-service", status=ServiceStatus.HEALTHY, error_message="Previous error"
        )
        assert health.error_message is None


class TestServiceMetrics:
    def test_service_metrics_creation(self):
        metrics = ServiceMetrics(
            service_name="test-service",
            uptime_seconds=3600.0,
            request_count=1000,
            error_count=10,
            average_response_time_ms=200.0,
            peak_response_time_ms=500.0,
        )

        assert metrics.service_name == "test-service"
        assert metrics.uptime_seconds == 3600.0
        assert metrics.request_count == 1000
        assert metrics.error_count == 10
        assert metrics.average_response_time_ms == 200.0
        assert metrics.peak_response_time_ms == 500.0

    def test_service_metrics_properties(self):
        metrics = ServiceMetrics(service_name="test-service", request_count=100, error_count=5)

        assert metrics.error_rate == 5.0
        assert metrics.availability_percent == 95.0

        # Test with zero requests
        metrics_zero = ServiceMetrics(service_name="test-service")
        assert metrics_zero.error_rate == 0.0
        assert metrics_zero.availability_percent == 100.0

    def test_metrics_validation(self):
        # Error count greater than request count
        with pytest.raises(ValidationError) as exc_info:
            ServiceMetrics(service_name="test-service", request_count=10, error_count=15)
        assert "Error count cannot exceed request count" in str(exc_info.value)

        # Peak response time less than average
        with pytest.raises(ValidationError) as exc_info:
            ServiceMetrics(service_name="test-service", average_response_time_ms=200.0, peak_response_time_ms=100.0)
        assert "Peak response time cannot be less than average" in str(exc_info.value)

    def test_negative_values_validation(self):
        with pytest.raises(ValidationError):
            ServiceMetrics(service_name="test-service", uptime_seconds=-100.0)

        with pytest.raises(ValidationError):
            ServiceMetrics(
                service_name="test-service",
                cpu_usage_percent=150.0,  # > 100%
            )


class TestServiceDependency:
    def test_service_dependency_creation(self):
        dependency = ServiceDependency(
            service_name="web-service", depends_on="database-service", dependency_type="required", timeout_seconds=30
        )

        assert dependency.service_name == "web-service"
        assert dependency.depends_on == "database-service"
        assert dependency.dependency_type == "required"
        assert dependency.timeout_seconds == 30
        assert dependency.critical is True

    def test_dependency_type_validation(self):
        # Valid types
        valid_types = ["required", "optional", "weak", "strong"]
        for dep_type in valid_types:
            dependency = ServiceDependency(
                service_name="test-service", depends_on="other-service", dependency_type=dep_type
            )
            assert dependency.dependency_type == dep_type

        # Invalid type
        with pytest.raises(ValidationError) as exc_info:
            ServiceDependency(service_name="test-service", depends_on="other-service", dependency_type="invalid")
        assert "Dependency type must be one of" in str(exc_info.value)

    def test_timeout_validation(self):
        # Valid timeout
        dependency = ServiceDependency(service_name="test-service", depends_on="other-service", timeout_seconds=60)
        assert dependency.timeout_seconds == 60

        # Invalid timeout (zero or negative)
        with pytest.raises(ValidationError):
            ServiceDependency(service_name="test-service", depends_on="other-service", timeout_seconds=0)


class TestServiceConfiguration:
    def test_service_configuration_creation(self):
        registration = ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version="1.0.0")

        config = ServiceConfiguration(registration=registration)

        assert config.registration.name == "test-service"
        assert config.health_config["check_interval"] == 30
        assert config.metrics_config["enabled"] is True
        assert len(config.dependencies) == 0

    def test_health_config_validation(self):
        registration = ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version="1.0.0")

        # Invalid health config (negative check interval)
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(registration=registration, health_config={"check_interval": -10})
        assert "Health check interval must be positive" in str(exc_info.value)

        # Invalid failure threshold
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(
                registration=registration, health_config={"check_interval": 30, "failure_threshold": 0}
            )
        assert "Failure threshold must be positive" in str(exc_info.value)

    def test_metrics_config_validation(self):
        registration = ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version="1.0.0")

        # Invalid metrics config (non-integer collection interval)
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(
                registration=registration, metrics_config={"enabled": True, "collection_interval": "invalid"}
            )
        assert "Metrics collection interval must be an integer" in str(exc_info.value)


class TestServiceValidators:
    def test_service_registration_validator(self):
        validator = ServiceRegistrationValidator(ServiceRegistration)

        # Test reserved name rejection
        registration = ServiceRegistration(name="admin", service_type=ServiceType.LLM, version="1.0.0")
        result = validator.validate(registration)
        assert not result.valid
        assert "reserved" in result.field_errors["name"][0]

        # Test invalid capability format
        registration = ServiceRegistration(
            name="test-service",
            service_type=ServiceType.LLM,
            version="1.0.0",
            capabilities=["valid", "invalid!", "also-valid"],
        )
        result = validator.validate(registration)
        assert not result.valid
        assert "Invalid capability format" in result.field_errors["capabilities"][0]

        # Test self-dependency
        registration = ServiceRegistration(
            name="test-service",
            service_type=ServiceType.LLM,
            version="1.0.0",
            dependencies=["test-service", "other-service"],
        )
        result = validator.validate(registration)
        assert not result.valid
        assert "cannot depend on itself" in result.field_errors["dependencies"][0]

    def test_service_health_validator(self):
        validator = ServiceHealthValidator(ServiceHealth)

        # Test high consecutive failures warning
        health = ServiceHealth(
            service_name="test-service",
            status=ServiceStatus.UNHEALTHY,
            error_message="Connection failed",
            consecutive_failures=150,
        )
        result = validator.validate(health)
        assert result.valid
        assert len(result.warnings) > 0
        assert "consecutive failure count" in result.warnings[0]

        # Test degraded status with fast response suggestion
        health = ServiceHealth(service_name="test-service", status=ServiceStatus.DEGRADED, response_time_ms=50.0)
        result = validator.validate(health)
        assert result.valid
        assert len(result.suggestions) > 0
        assert "status is accurate" in result.suggestions[0]

        # Test stale health data warning
        old_time = datetime.utcnow() - timedelta(hours=2)
        health = ServiceHealth(service_name="test-service", status=ServiceStatus.HEALTHY, last_check=old_time)
        result = validator.validate(health)
        assert result.valid
        assert len(result.warnings) > 0
        assert "over 1 hour old" in result.warnings[0]

    def test_service_configuration_validator(self):
        validator = ServiceConfigurationValidator(ServiceConfiguration)

        # Test with valid configuration
        registration = ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version="1.0.0")
        config = ServiceConfiguration(registration=registration)
        result = validator.validate(config)
        assert result.valid

        # Test circular dependency detection
        dependency = ServiceDependency(service_name="test-service", depends_on="test-service")
        config = ServiceConfiguration(registration=registration, dependencies=[dependency])
        result = validator.validate(config)
        assert not result.valid
        assert "Circular dependency detected" in result.errors[0]

        # Test health check timeout >= interval
        config = ServiceConfiguration(
            registration=registration,
            health_config={
                "check_interval": 30,
                "timeout": 35,  # Greater than interval
                "failure_threshold": 3,  # Valid threshold
            },
        )
        result = validator.validate(config)
        assert not result.valid
        assert "timeout must be less than check interval" in result.errors[0]

        # Test critical dependency with long timeout warning
        dependency = ServiceDependency(
            service_name="test-service", depends_on="other-service", timeout_seconds=120, critical=True
        )
        config = ServiceConfiguration(registration=registration, dependencies=[dependency])
        result = validator.validate(config)
        assert result.valid
        assert len(result.warnings) > 0
        assert "long timeout" in result.warnings[0]

    def test_composite_service_validator(self):
        composite_validator = create_service_validator()

        # Test with valid configuration
        registration = ServiceRegistration(name="test-service", service_type=ServiceType.LLM, version="1.0.0")
        config = ServiceConfiguration(registration=registration)
        result = composite_validator.validate(config)
        assert result.valid

        # Test with invalid configuration (reserved name)
        registration = ServiceRegistration(
            name="system",  # Reserved name
            service_type=ServiceType.LLM,
            version="1.0.0",
        )
        config = ServiceConfiguration(registration=registration)
        result = composite_validator.validate(config)
        assert not result.valid


class TestModelSerialization:
    def test_service_registration_serialization(self):
        registration = ServiceRegistration(
            name="test-service", service_type=ServiceType.LLM, version="1.0.0", endpoint="https://api.example.com"
        )

        # Test model_dump
        data = registration.model_dump()
        assert data["name"] == "test-service"
        assert data["service_type"] == "llm"
        assert data["version"] == "1.0.0"

        # Test model_dump_json
        json_str = registration.model_dump_json()
        assert "test-service" in json_str
        assert "llm" in json_str

        # Test round trip
        registration2 = ServiceRegistration.model_validate(data)
        assert registration == registration2

        registration3 = ServiceRegistration.model_validate_json(json_str)
        assert registration == registration3

    def test_service_health_serialization(self):
        health = ServiceHealth(service_name="test-service", status=ServiceStatus.HEALTHY, response_time_ms=150.5)

        # Test model_dump with exclude_unset
        data = health.model_dump(exclude_unset=True)
        assert "service_name" in data
        assert "status" in data
        assert "response_time_ms" in data

        # Test round trip
        health2 = ServiceHealth.model_validate(data)
        assert health.service_name == health2.service_name
        assert health.status == health2.status
        assert health.response_time_ms == health2.response_time_ms
