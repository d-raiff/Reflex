from dataclasses import dataclass
from typing import Any, Optional
import difflib

from .errors import ReflexsiveConfigurationError

@dataclass
class ReflexsiveOptions:
    '''
    A class representing configuration options for the AliasedClass.

    This class defines various settings that control the behavior of the 
    AliasedClass system. It allows customization of attributes such as 
    whether to generate a .pyi stub, override keyword arguments, expose 
    an alias map, and more.
    '''

    allow_kwargs_override : bool = False
    expose_alias_map      : bool = False
    docstring_alias_hints : bool = True
    alias_prefix          : Optional[str] = None

    def __init__(self, **kwargs: Any):
        for kwarg, value in kwargs.items():
            if kwarg not in ReflexsiveOptions.__dict__:
                suggestion = difflib.get_close_matches(kwarg, ReflexsiveOptions.__dict__, n=1)
                suggestion_string = '' if not suggestion else f' Did you mean \'{suggestion[0]}\'?'
                raise ReflexsiveConfigurationError(f'Invalid Reflexsive option: \'{kwarg}\'.{suggestion_string}')
            
            setattr(self, kwarg, value)

    def __contains__(self, item: Any) -> bool:
        return item in ReflexsiveOptions.__dict__