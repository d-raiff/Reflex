class ReflexsiveError(Exception):
    """Base class for all alias-related errors."""
    pass

class ReflexsiveNameConflictError(ReflexsiveError):
    """Raised when an alias name collides with an existing attribute or alias."""
    pass

class ReflexsiveArgumentError(ReflexsiveError):
    """Raised when the alias maps invalid or unsupported arguments."""
    pass

class ReflexsiveConfigurationError(ReflexsiveError):
    """Raised when decorator configuration or options are invalid."""
    pass