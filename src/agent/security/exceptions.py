class SecurityException(Exception):
    def __init__(self, message: str, details: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details  # Internal details, never exposed to clients


class AuthenticationFailedException(SecurityException):
    pass


class AuthorizationFailedException(SecurityException):
    pass


class InvalidCredentialsException(AuthenticationFailedException):
    pass


class MissingCredentialsException(AuthenticationFailedException):
    pass


class InvalidAuthenticationTypeException(SecurityException):
    pass


class SecurityConfigurationException(SecurityException):
    pass


class AuthenticatorNotFound(SecurityException):
    pass
