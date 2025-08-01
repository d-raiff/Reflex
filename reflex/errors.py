class AliasError(Exception):
    """Base class for all alias-related errors."""
    pass

class AliasNameConflictError(AliasError):
    """Raised when an alias name collides with an existing attribute or alias."""
    pass

class AliasArgumentError(AliasError):
    """Raised when the alias maps invalid or unsupported arguments."""
    pass

class AliasConfigurationError(AliasError):
    """Raised when decorator configuration or options are invalid."""
    pass