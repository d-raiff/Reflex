from pathlib import Path
import re
from typing import Callable, Iterable, Optional, Mapping, Dict, Set, Union
import inspect
import textwrap


def stub_generate_signature(
        fn: Callable, 
        alias_name: Optional[str] = None, 
        arg_map: Optional[Mapping[str, str]] = None,
        collected_types: Optional[Dict[str, Set[str]]] = None
    ) -> str:
    '''
    Generate a stub signature line for a function or its alias, for inclusion in a `.pyi` file.

    This utility formats a Python function signature (optionally remapped through aliasing)
    as a stub-compatible method declaration, and tracks type annotations for import rendering.

    Parameters
    ----------
    fn (Callable):
        The original function object to be stubbed.

    alias_name (Optional[str]):
        The name to use in the stub. Defaults to the function’s own name.

    arg_map (Optional[Mapping[str, str]]):
        Optional mapping of original argument names to their alias forms.

    collected_types (Optional[Dict[str, Set[str]]]):
        A collection structure to record type references needed for `from ... import ...` generation.

    Returns
    -------
    str:
        A single string line formatted as a `.pyi` stub method definition.
    '''
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ''
    alias_name = alias_name or fn.__name__

    if collected_types is None:
        collected_types = {}

    def track_type(tp: type) -> None:
        # Handle wrapped types like Optional[int], List[User], etc.
        origin = getattr(tp, '__origin__', None)
        args = getattr(tp, '__args__', []) if origin else []

        def add(t: Union[type, str]) -> None:
            if isinstance(t, str):
                return  # ForwardRef not resolved
            mod = getattr(t, '__module__', None)
            name = getattr(t, '__name__', None)
            if not mod or not name or mod == 'builtins':
                return
            collected_types.setdefault(mod, set()).add(name)

        # Special case for `Union`, as Optional is defined as Union with None
        if origin is Union:
            if len(args) == 2 and type(None) in args:
                collected_types.setdefault('typing', set()).add('Optional')
                for arg in args:
                    if arg is not type(None):
                        track_type(arg)
                return  # ✅ skip adding Union itself
            else:
                collected_types.setdefault('typing', set()).add('Union')
                for arg in args:
                    track_type(arg)
        elif origin:
            add(origin)
            if args:
                for arg in args:
                    track_type(arg)
        else:
            add(tp)

    new_params = []
    for param in sig.parameters.values():
        if param.name == 'self':
            new_params.append(param)
            continue
        new_name = arg_map.get(param.name, param.name) if arg_map else param.name
        if param.annotation is not inspect.Parameter.empty:
            track_type(param.annotation)
        new_params.append(param.replace(name=new_name))

    new_sig = sig.replace(parameters=new_params)
    params_str = ', '.join(str(p) for p in new_sig.parameters.values())
    
    return_annotation = new_sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return_type = 'Any'
        collected_types.setdefault('typing', set()).add('Any')
    elif isinstance(return_annotation, type):
        return_type = return_annotation.__name__
        track_type(return_annotation)
    else:
        return_type = str(return_annotation)
        track_type(return_annotation)

    if not doc:
        return f'    def {alias_name}({params_str}) -> {return_type}: ...'
    else:
        docstring = textwrap.indent(f'\'\'\'\n{doc}\n\'\'\'', ' ' * 8)
        return f'    def {alias_name}({params_str}) -> {return_type}:\n{docstring}\n        ...'
    
def stub_render_imports(
        type_map: Mapping[str, Set[str]]
    ) -> str:
    '''
    Render a list of import statements needed for type annotations in the stub file.

    Parameters
    ----------
    type_map (Mapping[str, Set[str]]):
        A mapping from module names to the set of type names that should be imported from each.

    Returns
    -------
    str:
        A string of newline-separated `from ... import ...` statements.
    '''
    lines = []
    for module, names in sorted(type_map.items()):
        name = ', '.join(sorted(names))
        line = f'from {module} import {name}'
        lines.append(line)
    return '\n'.join(lines)

def stub_read_existing(path: Union[str, Path]) -> str:
    '''
    Read the contents of an existing stub (.pyi) file, if it exists.

    Parameters
    ----------
    path : str
        The file path to the stub file to be read.

    Returns
    -------
    str
        The contents of the stub file as a string, or an empty string if the file does not exist.
    '''
    if not Path(path).exists():
        return ''
    
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
    
def stub_update_class(
        full_stub_text: str,
        class_name: str,
        new_method_stubs: Iterable[str]
    ) -> str:
    '''
    Update or insert a class definition within stub text with the provided method stubs.

    Parameters
    ----------
    full_stub_text : str
        The complete text of the existing stub file.
    class_name : str
        The name of the class to update or insert in the stub file.
    new_method_stubs : Iterable[str]
        A list or iterable of method stub strings to insert into the class definition.

    Returns
    -------
    str
        The updated stub file content, with the specified class updated or appended.
        Existing methods with the same name are replaced; others are preserved.
    '''
    class_pattern = re.compile(
        rf"^(class {class_name}\b[^\n]*?:)([\s\S]*?)(?=^class\s|\Z)", 
        re.MULTILINE
    )

    match = class_pattern.search(full_stub_text)
    if match:
        header, body = match.group(1), match.group(2)
        body_lines = body.splitlines()

        # Map method name to lines in class
        method_pattern = re.compile(r'^\s*def\s+(\w+)\s*\(')
        existing_methods = {}
        for line in body_lines:
            m = method_pattern.match(line)
            if m:
                existing_methods[m.group(1)] = line

        # Replace or add new methods
        updated_body_lines = []
        seen = set()
        for line in new_method_stubs:
            m = method_pattern.match(line)
            if m:
                method_name = m.group(1)
                seen.add(method_name)
                updated_body_lines.append("    " + line.strip())

        # Retain any lines that weren’t replaced
        for line in body_lines:
            m = method_pattern.match(line)
            if m and m.group(1) in seen:
                continue  # Replaced already
            updated_body_lines.append(line)

        updated_body = "\n".join(updated_body_lines)
        return full_stub_text[:match.start()] + header + "\n" + updated_body + "\n" + full_stub_text[match.end():]
    else:
        # No class definition, append a new one
        class_block = f"\n\nclass {class_name}:\n"
        for line in new_method_stubs:
            class_block += "    " + line.strip() + "\n"
        return full_stub_text + class_block

def stub_write_file(
        class_name: str,
        import_block: str,
        stub_lines: Iterable[str],
        source_path: Union[str, Path]
    ) -> None:
    '''
    Write or update a stub (.pyi) file with the provided class definition and optional imports.

    Parameters
    ----------
    class_name : str
        The name of the class for which the stub is being generated or updated.
    import_block : str
        A block of import statements to include at the top of the stub file, if not already present.
    stub_lines : Iterable[str]
        The lines of stub content representing the class signature and methods.
    source_path : str
        The file path of the source Python file used to determine the stub file location.

    Returns
    -------
    None
        This function writes the updated stub content to the corresponding `.pyi` file and does not return a value.
    '''
    full_stub_text = stub_read_existing(source_path)
    updated_stub = stub_update_class(full_stub_text, class_name, stub_lines)

    if import_block:
        # Insert imports at the top only if not present already
        lines = updated_stub.strip().splitlines()
        if not any(line.strip().startswith('import') or line.strip().startswith('from') for line in lines[:5]):
            updated_stub = import_block + "\n\n" + updated_stub

    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(updated_stub)