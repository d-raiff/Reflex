class ReflexError(Exception):
    """Base class for all alias-related errors."""
    pass

class ReflexNameConflictError(ReflexError):
    """Raised when an alias name collides with an existing attribute or alias."""
    pass

class ReflexArgumentError(ReflexError):
    """Raised when the alias maps invalid or unsupported arguments."""
    pass

class ReflexConfigurationError(ReflexError):
    """Raised when decorator configuration or options are invalid."""
    pass