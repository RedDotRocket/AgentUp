"""Security utilities for AgentUp authentication."""

import logging
import re
import secrets
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def secure_compare(a: str | None, b: str | None) -> bool:
    """Perform constant-time string comparison to prevent timing attacks.

    Args:
        a: First string to compare
        b: Second string to compare

    Returns:
        bool: True if strings are equal, False otherwise
    """
    if a is None or b is None:
        return False

    # Convert to bytes for secure comparison
    try:
        a_bytes = a.encode("utf-8")
        b_bytes = b.encode("utf-8")
        return secrets.compare_digest(a_bytes, b_bytes)
    except (UnicodeError, AttributeError):
        return False


def sanitize_header_value(value: str) -> str:
    """Sanitize header value for logging and validation.

    Args:
        value: Raw header value

    Returns:
        str: Sanitized value safe for logging
    """
    if not value:
        return ""

    # Remove non-printable characters and limit length
    sanitized = re.sub(r"[^\x20-\x7E]", "", value)
    return sanitized[:100]  # Limit to 100 chars for logging


def mask_credential(credential: str, visible_chars: int = 4) -> str:
    """Mask credential for safe logging.

    Args:
        credential: The credential to mask
        visible_chars: Number of characters to show at the end

    Returns:
        str: Masked credential safe for logging
    """
    if not credential:
        return "[empty]"

    if len(credential) <= visible_chars:
        return "*" * len(credential)

    visible_part = credential[-visible_chars:]
    masked_part = "*" * (len(credential) - visible_chars)
    return f"{masked_part}{visible_part}"


def validate_api_key_format(api_key: str) -> bool:
    """Validate API key format.

    Args:
        api_key: The API key to validate

    Returns:
        bool: True if format is valid
    """
    if not api_key:
        return False

    # Basic validation: printable ASCII, reasonable length
    if not (8 <= len(api_key) <= 128):
        return False

    # Must contain only printable ASCII characters
    if not all(ord(c) >= 32 and ord(c) <= 126 for c in api_key):
        return False

    return True


def validate_bearer_token_format(token: str) -> bool:
    """Validate Bearer token format.

    Args:
        token: The Bearer token to validate

    Returns:
        bool: True if format is valid
    """
    if not token:
        return False

    # Basic validation for JWT-like tokens
    if not (16 <= len(token) <= 2048):
        return False

    # Must contain only URL-safe characters for JWT
    if not re.match(r"^[A-Za-z0-9_\-\.]+$", token):
        return False

    return True


def extract_bearer_token(auth_header: str) -> str | None:
    """Extract Bearer token from Authorization header.

    Args:
        auth_header: The Authorization header value

    Returns:
        Optional[str]: The extracted token, or None if invalid
    """
    if not auth_header:
        return None

    # Check for Bearer prefix (case-insensitive)
    if not auth_header.lower().startswith("bearer "):
        return None

    # Extract token part
    token = auth_header[7:].strip()  # Remove 'Bearer ' prefix

    if not token:
        return None

    return token


def log_security_event(
    event_type: str, request_info: dict[str, Any], success: bool, details: str | None = None
) -> None:
    """Log security events for audit purposes.

    Args:
        event_type: Type of security event (e.g., 'authentication', 'authorization')
        request_info: Information about the request (never include credentials)
        success: Whether the security operation succeeded
        details: Additional details for debugging (never include secrets)
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "success": success,
        "client_ip": request_info.get("client_ip", "unknown"),
        "user_agent": sanitize_header_value(request_info.get("user_agent", "")),
        "endpoint": request_info.get("endpoint", ""),
        "method": request_info.get("method", ""),
    }

    if details:
        log_entry["details"] = details

    if success:
        logger.info(f"Security event: {event_type}", extra=log_entry)
    else:
        logger.warning(f"Security event failed: {event_type}", extra=log_entry)


def get_request_info(request) -> dict[str, Any]:
    """Extract safe request information for logging.

    Args:
        request: FastAPI Request object

    Returns:
        dict[str, Any]: Safe request information (no credentials)
    """
    try:
        return {
            "client_ip": getattr(request.client, "host", "unknown") if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
            "endpoint": str(request.url.path) if request.url else "",
            "method": request.method if hasattr(request, "method") else "",
        }
    except Exception:
        # Fallback if request object is malformed
        return {
            "client_ip": "unknown",
            "user_agent": "unknown",
            "endpoint": "unknown",
            "method": "unknown",
        }
