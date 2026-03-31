"""
Shared exceptions used across the application.
"""


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded (429)."""
    pass


class TimeoutError(Exception):
    """Raised when request times out."""
    pass


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class NotFoundError(Exception):
    """Raised when resource is not found."""
    pass


class DuplicateError(Exception):
    """Raised when duplicate resource is detected."""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass
