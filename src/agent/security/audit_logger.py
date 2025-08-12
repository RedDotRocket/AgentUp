from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecurityEventType(str, Enum):
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_SUCCESS = "authorization_success"
    AUTHORIZATION_FAILURE = "authorization_failure"
    SCOPE_VALIDATION_SUCCESS = "scope_validation_success"
    SCOPE_VALIDATION_FAILURE = "scope_validation_failure"
    FUNCTION_ACCESS_GRANTED = "function_access_granted"
    FUNCTION_ACCESS_DENIED = "function_access_denied"
    SECURITY_CONFIGURATION_ERROR = "security_configuration_error"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"


class SecurityAuditLogger:
    def __init__(self):
        self._audit_logger = structlog.get_logger("security.audit")

    def log_security_event(
        self,
        event_type: SecurityEventType,
        user_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
        risk_level: str = "low",
    ) -> None:
        # Sanitize sensitive information
        sanitized_details = self._sanitize_details(details or {})
        sanitized_user_id = self._sanitize_user_id(user_id)

        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "success": success,
            "risk_level": risk_level,
        }

        # Add non-sensitive contextual information
        if sanitized_user_id:
            event_data["user_id"] = sanitized_user_id
        if client_ip:
            event_data["client_ip"] = self._sanitize_ip(client_ip)
        if user_agent:
            event_data["user_agent"] = self._sanitize_user_agent(user_agent)
        if resource:
            event_data["resource"] = resource
        if action:
            event_data["action"] = action
        if sanitized_details:
            event_data["details"] = sanitized_details

        # Log at appropriate level based on success and risk
        if success and risk_level == "low":
            self._audit_logger.info("Security event", **event_data)
        elif not success or risk_level in ["medium", "high"]:
            self._audit_logger.warning("Security event", **event_data)
        else:
            self._audit_logger.error("Critical security event", **event_data)

    def log_authentication_success(
        self, user_id: str, client_ip: str | None = None, auth_method: str | None = None
    ) -> None:
        self.log_security_event(
            SecurityEventType.AUTHENTICATION_SUCCESS,
            user_id=user_id,
            client_ip=client_ip,
            details={"auth_method": auth_method} if auth_method else None,
            risk_level="low",
        )

    def log_authentication_failure(self, client_ip: str | None = None, reason: str | None = None) -> None:
        self.log_security_event(
            SecurityEventType.AUTHENTICATION_FAILURE,
            client_ip=client_ip,
            success=False,
            details={"reason": reason} if reason else None,
            risk_level="medium",
        )

    def log_authorization_failure(
        self, user_id: str, resource: str, action: str, missing_scopes: list[str] | None = None
    ) -> None:
        details = {}
        if missing_scopes:
            details["missing_scopes_count"] = len(missing_scopes)  # Don't log actual scope names

        self.log_security_event(
            SecurityEventType.AUTHORIZATION_FAILURE,
            user_id=user_id,
            resource=resource,
            action=action,
            success=False,
            details=details,
            risk_level="medium",
        )

    def log_function_access_denied(self, user_id: str, function_name: str, required_scopes_count: int = 0) -> None:
        self.log_security_event(
            SecurityEventType.FUNCTION_ACCESS_DENIED,
            user_id=user_id,
            resource=function_name,
            action="execute",
            success=False,
            details={"required_scopes_count": required_scopes_count},
            risk_level="low",
        )

    def log_privilege_escalation_attempt(self, user_id: str, attempted_scope: str) -> None:
        self.log_security_event(
            SecurityEventType.PRIVILEGE_ESCALATION_ATTEMPT,
            user_id=user_id,
            action="scope_escalation",
            success=False,
            details={"attempted_scope_category": self._categorize_scope(attempted_scope)},
            risk_level="high",
        )

    def log_configuration_error(self, component: str, error_type: str, details: dict[str, Any] | None = None) -> None:
        self.log_security_event(
            SecurityEventType.SECURITY_CONFIGURATION_ERROR,
            resource=component,
            success=False,
            details={"error_type": error_type, **(self._sanitize_details(details) if details else {})},
            risk_level="high",
        )

    def _sanitize_user_id(self, user_id: str | None) -> str | None:
        if not user_id:
            return None

        # Hash or truncate sensitive user IDs
        if len(user_id) > 20:
            # Long user IDs (like API keys) should be hashed/truncated
            return f"user_{hash(user_id) % 10000:04d}"
        else:
            # Short user IDs are probably safe
            return user_id

    def _sanitize_ip(self, ip: str) -> str:
        # Mask the last octet for IPv4
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
        return ip  # Return as-is for IPv6 or invalid IPs

    def _sanitize_user_agent(self, user_agent: str) -> str:
        # Just keep the first part (browser/client name)
        return user_agent.split()[0] if user_agent else "unknown"

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}

        for key, value in details.items():
            # Skip sensitive keys
            if any(sensitive in key.lower() for sensitive in ["key", "token", "password", "secret", "credential"]):
                sanitized[f"{key}_present"] = value is not None
            elif key.lower() == "scopes" and isinstance(value, list):
                # Don't log actual scope names, just counts
                sanitized["scopes_count"] = len(value)
            elif isinstance(value, str) and len(value) > 100:
                # Truncate long strings
                sanitized[key] = value[:97] + "..."
            else:
                sanitized[key] = value

        return sanitized

    def _categorize_scope(self, scope: str) -> str:
        scope_lower = scope.lower()

        if "admin" in scope_lower or "*" in scope:
            return "admin_level"
        elif "write" in scope_lower or "edit" in scope_lower:
            return "write_level"
        elif "read" in scope_lower:
            return "read_level"
        else:
            return "other"


# Global audit logger instance
_security_audit_logger: SecurityAuditLogger | None = None


def get_security_audit_logger() -> SecurityAuditLogger:
    global _security_audit_logger
    if _security_audit_logger is None:
        _security_audit_logger = SecurityAuditLogger()
    return _security_audit_logger


def log_security_event(*args, **kwargs) -> None:
    get_security_audit_logger().log_security_event(*args, **kwargs)
