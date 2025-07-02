class SecurityException(Exception):
    """Base exception for all security-related errors."""

    def __init__(self, message: str, details: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details  # Internal details, never exposed to clients


class AuthenticationFailedException(SecurityException):
    """Raised when authentication fails."""

    pass


class AuthorizationFailedException(SecurityException):
    """Raised when authorization fails (user authenticated but lacks permission)."""

    pass


class InvalidCredentialsException(AuthenticationFailedException):
    """Raised when provided credentials are invalid."""

    pass


class MissingCredentialsException(AuthenticationFailedException):
    """Raised when required credentials are not provided."""

    pass


class InvalidAuthenticationTypeException(SecurityException):
    """Raised when an unsupported authentication type is requested."""

    pass


class SecurityConfigurationException(SecurityException):
    """Raised when security configuration is invalid."""

    pass


class AuthenticatorNotFound(SecurityException):
    """Raised when a requested authenticator is not available."""

    pass
