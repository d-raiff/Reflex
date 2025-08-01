import pytest

from reflexsive.stubgen import stub_update_class

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