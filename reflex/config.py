from dataclasses import dataclass
from typing import Optional
import difflib

from .errors import AliasConfigurationError

@dataclass
class ReflexOptions:
    '''
    A class representing configuration options for the AliasedClass.

    This class defines various settings that control the behavior of the 
    AliasedClass system. It allows customization of attributes such as 
    whether to generate a .pyi stub, override keyword arguments, expose 
    an alias map, and more.
    '''
    
    __slots__ = (
        'allow_kwargs_override',
        'expose_alias_map',
        'docstring_alias_hints',
        'alias_prefix',    
    )

    allow_kwargs_override : bool = False
    expose_alias_map      : bool = False
    docstring_alias_hints : bool = True
    alias_prefix          : Optional[str] = None

    def __init__(self, **kwargs):
        for kwarg, value in kwargs.items():
            if kwarg not in self.__slots__:
                suggestion = difflib.get_close_matches(kwarg, self.__slots__, n=1)
                suggestion_string = '' if not suggestion else f' Did you mean \'{suggestion[0]}\'?'
                raise AliasConfigurationError(f'Invalid AliasedClass option: \'{kwarg}\'.{suggestion_string}')
            
            setattr(self, kwarg, value)

    def __contains__(self, item):
        return item in self.__slots__