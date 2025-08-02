import inspect
import os
from pathlib import Path
from unittest.mock import mock_open, patch
from typing import Callable, Dict, ForwardRef, Iterable, List, Optional, Set, Union
import tempfile

from reflexsive.stubgen import (
    stub_generate_signature,
    stub_render_imports,
    stub_read_existing,
    stub_update_class,
    stub_write_file
)

# ===========================
# | stub_generate_signature |
# ===========================

class ForwardType: pass
def test_signature_with_forward_reference():
    '''
    Validates that `stub_generate_signature` handles forward-referenced type annotations 
    (i.e., type hints as strings) without breaking or adding invalid imports.
    '''
    def func(x: 'ForwardType') -> 'ForwardType': 
        '''Uses a forward reference.'''
        return x

    collected = {}
    result = stub_generate_signature(func, collected_types=collected)

    assert "def func(x: 'ForwardType') -> 'ForwardType':" in result
    assert "Uses a forward reference." in result
    # Forward references are strings and should not be tracked
    assert collected == {}
    
def test_signature_with_nested_types():
    '''
    Verifies that `stub_generate_signature` handles nested type annotations like
    Dict[str, List[Set[int]]] and tracks all relevant typing imports.
    '''
    def complex() -> Dict[str, List[Set[int]]]:
        '''Returns a nested container type.'''
        return {}

    collected = {}
    result = stub_generate_signature(complex, collected_types=collected)

    assert "def complex() -> Dict[str, List[Set[int]]]" in result
    assert "Returns a nested container type." in result

    # Should track all three typing types
    assert collected == {
        'typing': {'Dict', 'List', 'Set'}
    }
    
def test_signature_with_complex_nested_types():
    '''
    Verifies that `stub_generate_signature` can handle functions with multiple parameters 
    and a complex nested return type, tracking all appropriate typing imports.
    '''
    def process(data: Dict[str, List[Set[int]]], flags: Iterable[bool]) -> Union[List[int], None]:
        '''Processes structured data with flags.'''
        return 42

    collected = {}
    result = stub_generate_signature(process, collected_types=collected)

    expected_signature = "def process(data: Dict[str, List[Set[int]]], flags: Iterable[bool]) -> Optional[List[int]]:"
    
    assert expected_signature in result
    assert 'Processes structured data with flags.' in result

    # We expect Optional[int] to be used instead of Union[int, None]
    assert collected == {'typing': {'Dict', 'List', 'Set', 'Optional'}, 'collections.abc': {'Iterable'}}
    
def test_signature_with_union_of_multiple_types():
    '''
    Ensures that `stub_generate_signature` handles a Union of more than two types,
    including None, and does not collapse it into Optional[...] unnecessarily.
    '''
    from typing import Union

    def func(x: int) -> Union[int, str, float, None]:
        '''Return one of several types.'''
        return x

    collected = {}
    result = stub_generate_signature(func, collected_types=collected)
    
    print(result)

    assert "def func(x: int) -> Union[int, str, float, None]:" in result
    assert "Return one of several types." in result

    # Only Union should be collected — not Optional
    assert collected == {'typing': {'Union'}}
    
def test_track_type_calls_add_directly_for_non_generic():
    '''
    Confirms that `track_type()` reaches the `else: add(tp)` path when the annotation
    is a non-generic, non-builtin, non-Union class like `datetime.datetime`.
    '''
    import datetime

    def fn(ts: datetime.datetime) -> None:
        '''Uses a non-generic class type.'''
        return

    collected = {}
    result = stub_generate_signature(fn, collected_types=collected)

    assert "def fn(ts: datetime) -> None:" in result
    assert collected == {'datetime': {'datetime'}}
    
def test_signature_with_typing_forwardref():
    '''
    Ensures that `stub_generate_signature` handles `typing.ForwardRef` objects gracefully,
    outputting a valid stub line and skipping import collection.
    '''
    # Create a dummy function with a ForwardRef manually injected
    def func(x): pass
    sig = inspect.signature(func)
    new_param = sig.parameters['x'].replace(annotation=ForwardRef('SomeType'))
    func.__signature__ = sig.replace(parameters=[new_param])

    # Patch __annotations__ as well to prevent empty annotations from overriding
    func.__annotations__ = {'x': ForwardRef('SomeType')}

    collected = {}
    result = stub_generate_signature(func, collected_types=collected)

    assert "def func(x: 'SomeType') -> None:" in result
    assert collected == {}  # ForwardRef should not contribute to imports
    
def test_stub_format_type_returns_base_without_args():
    '''
    Ensures that `stub_generate_signature` returns just the base name when a generic
    typing type (like `Callable`) has no type arguments, triggering the `return base` case.
    '''
    def fn(cb: Callable) -> None:
        '''Accepts a generic Callable with no args.'''
        return

    collected: Dict[str, Set[str]] = {}
    result = stub_generate_signature(fn, collected_types=collected)

    assert "def fn(cb: Callable) -> None:" in result
    assert "Accepts a generic Callable with no args." in result
    assert collected == {'collections.abc': {'Callable'}}
    
def test_no_annotations():
    '''
    Ensures that `stub_generate_signature` handles functions with no parameter annotations.
    '''
    def fn(a, b): return a + b

    collected: Dict[str, Set[str]] = {}
    result = stub_generate_signature(fn, collected_types=collected)
    
    assert "def fn(a, b) -> None:" in result
    assert collected == {}

def test_varargs_annotation():
    '''
    Ensures that `stub_generate_signature` handles *args with and without annotations.
    '''
    def fn(*args: int): pass

    collected: Dict[str, Set[str]] = {}
    result = stub_generate_signature(fn, collected_types=collected)

    assert "def fn(*args: int) -> None:" in result
    assert collected == {}

def test_varkwargs_annotation():
    '''
    Ensures that `stub_generate_signature` handles **kwargs with and without annotations.
    '''
    def fn(**kwargs: str): pass

    collected: Dict[str, Set[str]] = {}
    result = stub_generate_signature(fn, collected_types=collected)

    assert "def fn(**kwargs: str) -> None:" in result
    assert collected == {}
    
def test_default_values_are_replaced_with_ellipsis():
    '''
    Ensures that parameters with default values are rendered with `= ...` in the stub output,
    and that the types are tracked correctly.
    '''
    def fn(x: int = 42, y: str = "hello") -> None:
        '''Function with defaults.'''
        pass

    collected = {}
    result = stub_generate_signature(fn, collected_types=collected)

    assert "def fn(x: int = ..., y: str = ...) -> None:" in result
    assert 'Function with defaults.' in result
    assert collected == {}
    
def test_instance_method_signature():
    '''
    Verifies that `stub_generate_signature` handles instance methods correctly,
    preserving `self`, formatting parameters, and indenting the result for class stubs.
    '''
    class MyClass:
        def method(self, x: int, y: str) -> bool:
            '''Performs a check.'''
            return True

    collected = {}
    result = stub_generate_signature(MyClass.method, collected_types=collected)

    assert 'def method(self, x: int, y: str) -> bool:' in result
    assert 'Performs a check.' in result
    assert collected == {}
    
# ===========================
# |   stub_render_imports   |
# ===========================

def test_render_imports_sorted():
    '''
    Ensures modules and types are alphabetically sorted in generated import statements.
    '''
    imports = stub_render_imports({'collections': {'deque'}, 'typing': {'Optional', 'Union'}})
    assert imports == "from collections import deque\nfrom typing import Optional, Union"


def test_render_empty_imports():
    '''
    Checks that an empty type map returns an empty string.
    '''
    assert stub_render_imports({}) == ''


def test_render_single_module_multiple_types():
    '''
    Verifies correct rendering when a single module includes multiple types.
    '''
    result = stub_render_imports({'typing': {'List', 'Dict'}})
    assert result == 'from typing import Dict, List'

# ===========================
# |   stub_read_existing    |
# ===========================
    
def test_existing_stub_file():
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.pyi') as tmp:
        tmp.write('def foo() -> None: ...')
        tmp_path = tmp.name
    
    content = stub_read_existing(tmp_path)
    assert content == 'def foo() -> None: ...'
    
    os.remove(tmp_path)
    
def test_nonexistent_file():
    '''
    Test that stub_read_existing returns an empty string for a nonexistent file path.

    This test provides a path that does not exist and asserts that the function returns an empty string.
    '''
    fake_path = 'some/fake/path/nonexistent.pyi'
    content = stub_read_existing(fake_path)
    assert content == ''
    
# ===========================
# |    stub_update_class    |
# ===========================

def test_append_new_class_to_empty_stub():
    '''
    Verifies that `_update_class_stub` appends a new class definition to an empty 
    stub text when the target class does not exist. Ensures new class and methods 
    are added correctly.
    '''
    full_stub_text = ''
    class_name = 'MyClass'
    method_stubs = ['def foo(self) -> None: ...']

    result = stub_update_class(full_stub_text, class_name, method_stubs)

    assert f"class {class_name}" in result
    assert 'def foo(self) -> None: ...' in result


def test_replace_existing_method_and_preserve_others():
    '''
    Ensures that `_update_class_stub` replaces existing method stubs with matching names
    while preserving non-conflicting ones in the class body.
    '''
    full_stub_text = '''
class MyClass:
    def foo(self) -> None: ...
    def bar(self) -> int: ...
    '''

    class_name = 'MyClass'
    method_stubs = ['def foo(self) -> str: ...']

    result = stub_update_class(full_stub_text, class_name, method_stubs)

    assert 'def foo(self) -> str: ...' in result
    assert 'def bar(self) -> int: ...' in result
    assert 'def foo(self) -> None: ...' not in result


def test_insert_import_block_if_absent():
    '''
    Confirms that import statements are not handled directly by `_update_class_stub` 
    but that formatting remains stable if imports are present in the stub content.
    (Note: actual import handling occurs elsewhere, in `_write_stub_file`.)
    '''
    full_stub_text = '''
class AnotherClass:
    def alpha(self): ...
    '''

    class_name = 'NewClass'
    method_stubs = ['def beta(self): ...']

    result = stub_update_class(full_stub_text, class_name, method_stubs)

    assert 'class NewClass:' in result
    assert 'def beta(self): ...' in result
    assert 'class AnotherClass:' in result


def test_preserves_non_method_lines_in_class_body():
    '''
    Verifies that `_update_class_stub` preserves non-method lines within the 
    class body, such as comments or docstrings, while still replacing method stubs.
    '''
    full_stub_text = '''
class Sample:
    """This is a class docstring."""
    def old_method(self): ...
    '''
    class_name = 'Sample'
    method_stubs = ['def old_method(self): ...', 'def new_method(self): ...']

    result = stub_update_class(full_stub_text, class_name, method_stubs)

    assert '"""This is a class docstring."""' in result
    assert 'def old_method(self): ...' in result
    assert 'def new_method(self): ...' in result
    
def test_update_class_adds_new_class():
    '''
    Verifies that a new class block is added if it does not exist in the stub text.
    '''
    stub = ''
    class_name = 'NewClass'
    methods = ['def foo(self): ...']
    result = stub_update_class(stub, class_name, methods)
    assert 'class NewClass:' in result
    assert 'def foo(self): ...' in result


def test_update_class_replaces_matching_methods():
    '''
    Checks that existing methods with matching names are replaced by new ones.
    '''
    stub = 'class MyClass:\n    def foo(self): ...\n    def bar(self): ...'
    result = stub_update_class(stub, 'MyClass', ['def foo(self, x): ...'])
    assert 'def foo(self, x): ...' in result
    assert 'def bar(self): ...' in result
    assert 'def foo(self): ...' not in result


def test_update_class_preserves_docstrings():
    '''
    Ensures that non-method lines like comments and docstrings are preserved during update.
    '''
    stub = 'class X:\n    """docstring"""\n    def old(self): ...'
    result = stub_update_class(stub, 'X', ['def old(self): ...', 'def new(self): ...'])
    assert '"""docstring"""' in result
    assert 'def old(self): ...' in result
    assert 'def new(self): ...' in result

# ===========================
# |     stub_write_file     |
# ===========================

def test_write_file_adds_imports_and_class():
    '''
    Checks that a stub file is created with both import block and class stub.
    '''
    m = mock_open(read_data='')
    with patch('reflexsive.stubgen.open', m), patch('reflexsive.stubgen.stub_read_existing', return_value=''):
        stub_write_file('Z', 'from typing import Any', ['def f(self) -> Any: ...'], 'file.pyi')
    written = m().write.call_args[0][0]
    assert 'from typing import Any' in written
    assert 'class Z:' in written
    assert 'def f(self)' in written

def test_write_file_skips_redundant_imports():
    '''
    Ensures import block is not inserted again if one is already present.
    '''
    stub_with_import = 'from typing import Any\n\nclass Z:\n    def f(self) -> Any: ...'
    m = mock_open()
    with patch('reflexsive.stubgen.open', m), patch('reflexsive.stubgen.stub_read_existing', return_value=stub_with_import):
        stub_write_file('Z', 'from typing import Any', ['def f(self) -> Any: ...'], 'file.pyi')
    written = m().write.call_args[0][0]
    assert written.startswith('from typing import Any')

def test_write_file_updates_existing_stub():
    '''
    Validates that the function updates the existing `.pyi` file instead of overwriting unrelated content.
    '''
    existing_stub = 'class A:\n    def old(self): ...'
    m = mock_open()
    with patch('reflexsive.stubgen.open', m), patch('reflexsive.stubgen.stub_read_existing', return_value=existing_stub):
        stub_write_file('A', '', ['def old(self): ...', 'def new(self): ...'], 'file.pyi')
    written = m().write.call_args[0][0]
    assert 'def new(self): ...' in written
    assert 'class A:' in written