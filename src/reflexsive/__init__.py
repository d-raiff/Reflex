from .core import Reflexsive
from .config import ReflexsiveOptions
from .stubgen import (
    stub_generate_signature,
    stub_render_imports,
    stub_write_file,
    stub_update_class,
)
from .errors import (
    ReflexsiveArgumentError,
    ReflexsiveConfigurationError,
    ReflexsiveNameConflictError,
)

__name__ = 'reflexsive'

__version__ = 'v0.0.0.post0'
__version_tuple__ = ('v', 0, 0, 'post0')

__version_short__ = '.'.join(__version__.split('.')[:-1])
__version_tuple_short__ = __version_tuple__[:-1]

__all__ = [
    # Public core API
    "Reflexsive",
    "ReflexsiveOptions",

    # Stub generation
    "stub_generate_signature",
    "stub_render_imports",
    "stub_write_file",
    "stub_update_class",
    
    # Exceptions
    "ReflexsiveArgumentError",
    "ReflexsiveConfigurationError",
    "ReflexsiveNameConflictError",
]