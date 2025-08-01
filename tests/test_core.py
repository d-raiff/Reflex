import pytest
from reflexsive.core import Reflexsive
from reflexsive.errors import *

def test_original_function_is_unmodified():
    '''
    Verifies that the original function can still be called directly with its original signature,
    unaffected by aliasing. This ensures that the alias decorator does not tamper with the original
    method's behavior or signature.
    '''
    class AliasTest1(Reflexsive):
        @Reflexsive.alias('a1', user='u')
        def login(self, user):
            return f'user:{user}'

    obj = AliasTest1()

    # Direct call to the original method using original name and param
    assert obj.login('carol') == 'user:carol'
    assert obj.login(user='dave') == 'user:dave'

def test_alias_without_arg_map():
    '''
    Tests that an alias can be defined without any keyword argument remapping. The function is invoked positionally 
    using the alias name, confirming that defaults and ordering still apply correctly.
    '''
    class AliasTest2(Reflexsive):
        @Reflexsive.alias('shout')
        def greet(self, name: str) -> str:
            """
            Function to greet the user.
            """
            return f'Hi {name}!'

    obj = AliasTest2()
    assert obj.shout('Bob') == 'Hi Bob!'        # type: ignore
    assert obj.shout(name='Bob') == 'Hi Bob!'   # type: ignore

def test_positional_and_keyword():
    '''
    Tests that aliasing works correctly for both positional and keyword arguments, including defaults. 
    Verifies that the alias (`a1`) properly maps new names (`u`, `p`, `r`) to the original parameters 
    user, password, and role.
    '''
    class AliasTest3(Reflexsive):
        @Reflexsive.alias('a1', user='u', password='p', role='r')
        def auth(self, user, password, role='viewer'):
            return f'{user}:{password}:{role}'

    obj = AliasTest3()
    assert obj.a1('alice', 'pw') == 'alice:pw:viewer'           # type: ignore
    assert obj.a1(u='bob', p='pw', r='admin') == 'bob:pw:admin' # type: ignore

def test_full_signature_variants():
    '''
    Tests a complex function signature involving all major argument types: positional, defaulted, `*args`, 
    keyword-only, default keyword-only, and `**kwargs`. Confirms aliasing behaves correctly across this 
    full range.
    '''
    class AliasTest4(Reflexsive):
        @Reflexsive.alias('full', a='a1', b='b1', c='c1', d='d1')
        def full_signature(self, a, b=0, *args, c, d=1, **kwargs):
            return (a, b, args, c, d, kwargs)

    obj = AliasTest4()
    assert obj.full('A', 1, 2, 3, c1='C') == ('A', 1, (2, 3), 'C', 1, {})              # type: ignore
    assert obj.full(a1='A', b1=2, c1='C', d1=4, z=9) == ('A', 2, (), 'C', 4, {'z': 9}) # type: ignore

def test_original_and_alias_parameter_should_fail():
    '''
    Validates that a `AliasArgumentError` is raised if both an original parameter and its alias are passed simultaneously. 
    Ensures that name collisions between alias and original names are properly detected and rejected.
    '''
    class AliasTest5(Reflexsive):
        @Reflexsive.alias('full', a='a1', b='b1', c='c1', d='d1')
        def full_signature(self, a, b=0, *args, c, d=1, **kwargs):
            return (a, b, args, c, d, kwargs)

    obj = AliasTest5()
    with pytest.raises(ReflexsiveArgumentError, match='Argument \'a\' is not valid in alias \'full\';'):
        obj.full(a='A', a1='AA', c1='C')  # type: ignore

def test_multiple_aliases_per_function():
    '''
    Tests a single function with multiple distinct aliases (`a1` and `a2`) mapping different argument names (`u` 
    and `usr`). Confirms that both aliases invoke the same function correctly using their respective mappings.
    '''
    class AliasTest6(Reflexsive):
        @Reflexsive.alias('a1', user='u')
        @Reflexsive.alias('a2', user='usr')
        def login(self, user):
            return f'user:{user}'

    obj = AliasTest6()
    assert obj.a1('alice') == 'user:alice' # type: ignore
    assert obj.a2(usr='bob') == 'user:bob' # type: ignore

def test_duplicate_alias_names_should_fail():
    '''
    Verifies that applying two aliases with the same alias name (`a1`) to a single function raises a `AliasNameConflictError`.
    This prevents ambiguity about which mapping should take precedence.
    '''
    with pytest.raises(ReflexsiveNameConflictError, match='Alias name \'a1\' is already defined for function \'login\'.'):
        class AliasTest7(Reflexsive):
            @Reflexsive.alias('a1', user='u')
            @Reflexsive.alias('a1', user='usr')
            def login(self, user):
                return f'user:{user}'
            
def test_alias_name_collision_across_functions_should_fail():
    '''
    Checks that two different methods cannot define the same alias name (`conflict`). Ensures that the metaclass 
    detects alias collisions across the class namespace and raises a ValueError.
    '''
    with pytest.raises(ReflexsiveNameConflictError, match='Class \'AliasTest8\' already has alias \'conflict\' from \'method_one\''):
        class AliasTest8(Reflexsive):
            @Reflexsive.alias('conflict', x='a')
            def method_one(self, x):
                return f'one:{x}'

            @Reflexsive.alias('conflict', y='b')
            def method_two(self, y):
                return f'two:{y}'    

def test_alias_with_builtin_param_name():
    '''
    Confirms that aliasing works correctly even when the alias uses a Python built-in name like `list`.
    This ensures there's no unintended shadowing or conflict during alias resolution.
    '''
    class AliasTest9(Reflexsive):
        @Reflexsive.alias('fetch', item='list')
        def get_item(self, item):
            return f'Got {item}'

    obj = AliasTest9()
    assert obj.fetch(list='banana') == 'Got banana'  # type: ignore

def test_alias_missing_required_arg_should_fail():
    '''
    Ensures that calling an alias without providing all required arguments results in a TypeError.
    Validates that Python's normal signature enforcement still applies to aliased methods.
    '''
    class AliasTest10(Reflexsive):
        @Reflexsive.alias('alias', user='u', password='p')
        def login(self, user, password):
            return f'{user}:{password}'

    obj = AliasTest10()
    with pytest.raises(TypeError, match='missing 1 required positional argument:'):
        obj.alias(u='admin')  # type: ignore

def test_alias_extra_argument_should_fail():
    '''
    Verifies that unexpected or extra arguments passed to an aliased method raise a TypeError.
    Ensures that aliasing does not permit argument injection beyond the defined function signature.
    '''
    class AliasTest11(Reflexsive):
        @Reflexsive.alias('sumup', a='x', b='y')
        def add(self, a, b):
            return a + b

    obj = AliasTest11()
    with pytest.raises(TypeError, match='got an unexpected keyword argument'):
        obj.sumup(x=1, y=2, z=3)  # type: ignore

def test_alias_preserves_all_metadata():
    '''
    Ensures that the original function's metadata — including `__name__`, `__doc__`, `__module__`, 
    `__annotations__`, `__defaults__`, `__kwdefaults__`, and `__code__` — are preserved after aliasing. 
    This is important for introspection, debugging, tooling, and stub generation.
    '''
    class AliasTest12(Reflexsive):
        @Reflexsive.alias('shout', name='n')
        def greet(self, name: str = 'world') -> str:
            '''Return greeting'''
            return f'Hi {name}!'

    func = AliasTest12.greet

    assert func.__name__ == 'greet'
    assert func.__doc__ == 'Return greeting'
    assert func.__module__ == __name__
    assert func.__annotations__ == {'name': str, 'return': str}
    assert func.__defaults__ == ('world',)
    assert func.__kwdefaults__ is None  # No keyword-only defaults in this example
    assert isinstance(func.__code__, type((lambda: 0).__code__))  # code object exists
            
def test_staticmethod_alias_positional_and_keyword():
    '''
    Tests aliasing of a static method using both positional and keyword arguments. 
    Confirms that aliasing works without requiring an instance and that parameter 
    remapping (`val` → `v`) is honored.
    '''
    class AliasTest13(Reflexsive):
        @Reflexsive.alias('alias_static', val='v')
        @staticmethod
        def static_method(val):
            return val * 2

    assert AliasTest13.static_method(6) == 12   
    assert AliasTest13.static_method(val=7) == 14 
    assert AliasTest13.alias_static(4) == 8         # type: ignore
    assert AliasTest13.alias_static(v=5) == 10      # type: ignore

def test_staticmethod_alias_decorator_order_reversed():
    '''
    Ensures that the alias decorator works correctly even when applied *after* 
    @staticmethod. Verifies that internal unwrapping logic handles decorator 
    order in both directions.
    '''
    class AliasTest14(Reflexsive):
        @staticmethod
        @Reflexsive.alias('alias_static', val='v')
        def static_method(val):
            return val + 1

    assert AliasTest14.static_method(2) == 3       
    assert AliasTest14.static_method(val=11) == 12 
    assert AliasTest14.alias_static(9) == 10        # type: ignore
    assert AliasTest14.alias_static(v=3) == 4       # type: ignore

def test_classmethod_alias_positional_and_keyword():
    '''
    Tests aliasing of a class method using both positional and keyword args. 
    Ensures `cls` is passed correctly and alias mapping (`msg` → `m`) is respected.
    '''
    class AliasTest15(Reflexsive):
        @Reflexsive.alias('alias_class', msg='m')
        @classmethod
        def class_method(cls, msg):
            return f'{cls.__name__}:{msg}'

    assert AliasTest15.class_method('alias') == 'AliasTest15:alias'   
    assert AliasTest15.class_method(msg='test') == 'AliasTest15:test' 
    assert AliasTest15.alias_class('hello') == 'AliasTest15:hello'    # type: ignore
    assert AliasTest15.alias_class(m='world') == 'AliasTest15:world'  # type: ignore

def test_classmethod_alias_decorator_order_reversed():
    '''
    Verifies that aliasing a class method still works when the decorators are applied 
    in reverse order. Ensures that the alias system unwraps the method properly and 
    rewraps it as a classmethod.
    '''
    class AliasTest16(Reflexsive):
        @classmethod
        @Reflexsive.alias('alias_class', msg='m')
        def class_method(cls, msg):
            return f'{cls.__name__}:{msg}'

    assert AliasTest16.class_method('zig') == 'AliasTest16:zig'     
    assert AliasTest16.class_method(msg='zag') == 'AliasTest16:zag' 
    assert AliasTest16.alias_class('ping') == 'AliasTest16:ping'    # type: ignore
    assert AliasTest16.alias_class(m='pong') == 'AliasTest16:pong'  # type: ignore

def test_staticmethod_and_classmethod_together():
    '''
    Defines one static method and one class method, each with their own alias.
    Confirms that both aliases resolve correctly, operate without an instance,
    and dispatch to the correct method type.
    '''
    class AliasTest17(Reflexsive):
        @Reflexsive.alias('s', x='v')
        @staticmethod
        def stat(x):
            return x + 1

        @Reflexsive.alias('c', y='val')
        @classmethod
        def cls(cls, y):
            return f'{cls.__name__}:{y}'

    assert AliasTest17.s(3) == 4                    # type: ignore
    assert AliasTest17.s(v=10) == 11                # type: ignore
    assert AliasTest17.c('Z') == 'AliasTest17:Z'      # type: ignore
    assert AliasTest17.c(val='Y') == 'AliasTest17:Y'  # type: ignore

def test_alias_star_args_should_fail():
    '''
    Verifies that attempting to alias a variadic positional parameter (`*args`) raises a `AliasArgumentError`.
    This test ensures that aliasing is only allowed for explicitly named parameters and that the system
    correctly rejects attempts to remap `*args`, which do not have a fixed name in the function signature.
    '''
    with pytest.raises(ReflexsiveArgumentError, match='Cannot alias parameter \'args\';'):
        class AliasTest18(Reflexsive):
            @Reflexsive.alias('bad', args='a')
            def method(self, *args):
                return args
        
def test_alias_rejects_non_explicit_parameter_should_fail():
    '''
    Tests that aliasing fails when attempting to map a non-explicit parameter (e.g., from `**kwargs`).
    Verifies that a `AliasArgumentError` is raised if the aliased parameter is not declared in the function signature.
    '''
    with pytest.raises(ReflexsiveArgumentError, match='Cannot alias parameter \'x\''):
        class AliasTest22(Reflexsive):
            @Reflexsive.alias('bad_alias', x='a')  # 'x' is not explicitly defined
            def run(self, **kwargs):
                return kwargs.get('x')