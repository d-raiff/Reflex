import pytest

from reflexsive.core import Reflexsive
from reflexsive.config import ReflexsiveOptions
from reflexsive.errors import ReflexsiveConfigurationError

def test_valid_alias_configuration_options():
    '''
    Verifies that passing an unrecognized option to `@Reflexsive.aliased_class(...)` raises 
    an `AliasConfigurationError`. This protects the configuration surface and 
    prevents silent misconfiguration by rejecting unknown keywords.
    '''
    opt = ReflexsiveOptions(allow_kwargs_override=True, alias_prefix='Sure_')

    assert opt.allow_kwargs_override == True
    assert opt.alias_prefix == 'Sure_'
            
def test_invalid_alias_configuration_option_should_fail():
    '''
    Verifies that passing an unrecognized option to `@Reflexsive.aliased_class(...)` raises 
    an `AliasConfigurationError`. This protects the configuration surface and 
    prevents silent misconfiguration by rejecting unknown keywords.
    '''
    with pytest.raises(ReflexsiveConfigurationError, match='Invalid Reflexsive option: \'unexpose_alias_map\''):
        ReflexsiveOptions(unexpose_alias_map=False, docstring_alias_hints=True)

def test_alias_prefix_option():
    '''
    Tests a complex function signature involving all major argument types: positional, defaulted, `*args`, 
    keyword-only, default keyword-only, and `**kwargs`. Confirms aliasing behaves correctly across this 
    full range.
    '''
    class AliasTest20(Reflexsive, alias_prefix='aliaspy_'):
        @Reflexsive.alias('full', a='a1', b='b1', c='c1', d='d1')
        def full_signature(self, a, b=0, *args, c, d=1, **kwargs):
            return (a, b, args, c, d, kwargs)

    obj = AliasTest20()
    assert obj.aliaspy_full('A', 1, 2, 3, c1='C') == ('A', 1, (2, 3), 'C', 1, {})               # type: ignore
    assert obj.aliaspy_full(a1='A', b1=2, c1='C', d1=4, z=9) == ('A', 2, (), 'C', 4, {'z': 9})  # type: ignore

    with pytest.raises(AttributeError, match='\'AliasTest20\' object has no attribute \'full\''):
        obj.full() # type: ignore

def test_alias_with_kwargs_preserved():
    '''
    Ensures that aliasing a method that accepts `**kwargs` works correctly, and additional keyword arguments 
    are preserved and returned unmodified. Confirms that mapped keys (like `k` → `key`) are properly transformed.
    '''
    class AliasTest21(Reflexsive, allow_kwargs_override=True):
        @Reflexsive.alias('store', key='k')
        def store_value(self, **kwargs):
            return kwargs

    obj = AliasTest21()
    assert obj.store(k='id', extra=42) == {'key': 'id', 'extra': 42} # type: ignore