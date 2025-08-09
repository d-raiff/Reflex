from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from types import EllipsisType
from typing import (
    Dict, List, Set, Tuple, 
    Any, Callable, Iterable, 
    Optional, Type, Union, 
    TypeVar, cast
)
import ast
import click
import functools
import json
import re
import time
import yaml

try:
    # Python 3.10 and anove
    from typing import ParamSpec
except ImportError:
    # Python 3.9 and below
    from typing_extensions import ParamSpec

from ..errors import (
    ReflexsiveNameConflictError,
    ReflexsiveArgumentError
)
from .info import (
    Info,
    AliasInfo, FunctionInfo, ClassInfo
)
from .statics import (
    VALID_REFLEXSIVE_MODULE_PATHS,
    VALID_REFLEXSIVEMETA_MODULE_PATHS,
)
from ._split_qual_name import split_qual_name

T = TypeVar('T')
P = ParamSpec('P')
ConstantValue = str | bytes | bool | int | float | complex | EllipsisType | None

class WarningLevel(Enum):
    INFO    = auto()
    WARNING = auto()
    ERROR   = auto()
    
    def __str__(self) -> str:
        if self == WarningLevel.INFO:
            return click.style('[Info]:', fg='black', underline=True)
        
        elif self == WarningLevel.WARNING: 
            return click.style('[Warning]:', fg='yellow', underline=True)
        
        elif self == WarningLevel.ERROR: 
            return click.style('[Error]:', fg='red', bold=True, underline=True)

        raise NotImplementedError('Unreachable.')

@dataclass(frozen=True)
class Warning:
    info_objs   : Tuple[Info, ...]
    level       : WarningLevel
    exec_typ    : Optional[Type[Exception]]
    _message    : str
    
    @property
    def message(self) -> str:
        def replacer(match: re.Match) -> str:
            expr = match.group(1)
            split = expr.split('::')
            
            if len(split) > 2:
                raise ValueError(f'Unknown dynamic field components {split[2:]}.')
            
            index = 0
            if len(split) == 2:
                index = int(split[0]) - 1
            
            if index >= len(self.info_objs):
                raise ValueError(f'Invalid dynamic field index {index}.')
            
            field = split[-1]
            
            if not hasattr(self.info_objs[index], field):
                raise ValueError(f'Invalid dynamic field \'{expr}\'.')

            return str(getattr(self.info_objs[index], field))
        
        level_str = str(self.level)
        raises_str = 'raises {}: '.format(click.style(self.exec_typ.__name__, fg='red')) if self.exec_typ else ''
        message_str = re.sub(r'\$\((.*?)\)', replacer, self._message) # Dynamic fields from self.info_objs
            
        return f'{level_str} {raises_str}{message_str}'

def timed(fn: Callable[P, T]) -> Callable[P, Tuple[float, T]]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Tuple[float, T]:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        end = time.perf_counter()
        elapsed = end - start
        return elapsed, result
    return wrapper

def writeln(content: str, *, output: Optional[Path]) -> None:
    if output:
        content = f'{strip_ansi(content)}\n'
        output.parent.mkdir(parents=True, exist_ok=True
                            )
        if not output.exists():
            output.write_text(content, encoding='utf-8')
        else:
            with open(output, 'a') as file:
                file.write(content)
            
    else:
        click.echo(content)
        
def format_elapsed(elapsed: float) -> str:
    if elapsed < 60:
        # Show seconds with 4 significant figures
        return f'{elapsed:.4g}s'
    elif elapsed < 3600:
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        return f'{minutes}m {seconds:.4g}s'
    else:
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = elapsed % 60
        return f'{hours}h {minutes}m {seconds:.4g}s'
    
def validate_path_input(path: Path) -> bool:
    if not path.exists():
        click.echo('{}: Provided scan path does not exist: {}'.format(
            click.style('[Error]', bold=True, fg='red'), str(path)
        ))
        return False
    
    elif not path.is_dir():
        click.echo('{}: Provided scan path is not a directory: {}'.format(
            click.style('[Error]', bold=True, fg='red'), str(path)
        ))
        return False
    
    return True

def resolve_name(expr: ast.expr) -> Optional[str]:
    if isinstance(expr, ast.Name):
        return expr.id
    elif isinstance(expr, ast.Attribute):
        parts: list[str] = []
        while isinstance(expr, ast.Attribute):
            parts.insert(0, expr.attr)
            expr = expr.value
        if isinstance(expr, ast.Name):
            parts.insert(0, expr.id)
        return '.'.join(parts)
    elif isinstance(expr, ast.Call):
        return resolve_name(expr.func)
    return '<unknown>'

def get_module_name(file_path: Path, root_dir: Path) -> str:
    rel = file_path.relative_to(root_dir).with_suffix('')
    return '.'.join(rel.parts)

def get_decorator_name(expr: ast.expr) -> str:
    '''
    Extracts just the last function name from a decorator expression.

    Examples:
    - @alias                 → 'alias'
    - @Reflexsive.alias      → 'alias'
    - @pkg.module.alias(...) → 'alias'
    - @some.wrapper(...)     → 'wrapper'
    '''
    if isinstance(expr, ast.Name):
        return expr.id
    elif isinstance(expr, ast.Attribute):
        return expr.attr
    elif isinstance(expr, ast.Call):
        return get_decorator_name(expr.func)
    return '<unknown>'

def get_decorator_qual_name(expr: ast.expr, imports: dict[str, str]) -> str:
    '''
    Resolve the fully qualified name of a decorator expression using the provided import map.

    Examples:
    - @alias → 'alias'
    - @Reflexsive.alias → 'reflexsive.Reflexsive.alias' (if Reflexsive is imported from reflexsive)
    - @pkg.module.Decorator(...) → 'pkg.module.Decorator'
    '''
    if isinstance(expr, ast.Name):
        return imports.get(expr.id, expr.id)

    elif isinstance(expr, ast.Attribute):
        parts: list[str] = []
        while isinstance(expr, ast.Attribute):
            parts.insert(0, expr.attr)
            expr = expr.value

        if isinstance(expr, ast.Name):
            root = expr.id
            qualified_root = imports.get(root, root)
            parts.insert(0, qualified_root)
        else:
            parts.insert(0, '<unknown>')

        return '.'.join(parts)

    elif isinstance(expr, ast.Call):
        return get_decorator_qual_name(expr.func, imports)

    return '<unknown>'

def get_func_arg_names(func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> list[str]:
    args = func_node.args
    param_names: list[str] = []

    # Positional and keyword arguments
    param_names.extend(arg.arg for arg in args.args)

    # Positional-only arguments (Python 3.8+)
    if hasattr(args, 'posonlyargs'):
        param_names.extend(arg.arg for arg in args.posonlyargs)

    # Vararg (*args)
    if args.vararg:
        param_names.append(args.vararg.arg)

    # Keyword-only arguments
    param_names.extend(arg.arg for arg in args.kwonlyargs)

    # Kwarg (**kwargs)
    if args.kwarg:
        param_names.append(args.kwarg.arg)

    return param_names

def collect_classes(root: Path) -> Set[ClassInfo]:
    info: Set[ClassInfo] = set()

    for path in root.rglob('*.py'):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                contents = f.read()
                source_lines = contents.splitlines()
                tree = ast.parse(contents, filename=str(path))
        except SyntaxError:
            continue

        module_name = get_module_name(path, root)
        
        local_class_names   : Dict[str, str] = {}
        imports             : Dict[str, str] = {}

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                level = node.level
                if level == 0:
                    base_module = module
                else:
                    parent_parts = module_name.split('.')[:-level]
                    base_module = '.'.join(parent_parts + ([module] if module else []))

                for alias in node.names:
                    full_name = f'{base_module}.{alias.name}' if base_module else alias.name
                    imports[alias.asname or alias.name] = full_name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name] = alias.name
                    
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                qual_name = f'{module_name}.{node.name}'
                local_class_names[node.name] = qual_name
                
                bases: set[str] = set()
                functions: set[FunctionInfo] = set()
                
                # Handle inheritance
                for base in node.bases:
                    name = resolve_name(base)
                    if not name:
                        continue
                    
                    # Handle imported base: module.Base
                    parts = name.split('.')
                    if parts[0] in imports:
                        name = '.'.join([imports[parts[0]], *parts[1:]])
                    # Handle local class reference like just 'A'
                    elif name in local_class_names:
                        name = local_class_names[name]

                    bases.add(name)
                    
                # Handle metaclass
                metaclass = 'type'
                for kw in node.keywords:
                    if kw.arg != 'metaclass':
                        continue
                    
                    resolved = resolve_name(kw.value)
                    if resolved:
                        metaclass = resolved
                        
                    if metaclass and metaclass in imports:
                        metaclass = imports[metaclass]
                            
                # Handle function declarations
                for func in (_node for _node in node.body
                            if isinstance(_node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ):
                    func_qual_name = f'{module_name}.{node.name}.{func.name}'
                    func_decl_line = source_lines[func.lineno - 1] if 0 < func.lineno <= len(source_lines) else ''
                    func_full_impl = '\n'.join(source_lines[func.lineno:func.end_lineno])
                    func_parameters = set(get_func_arg_names(func))
                    aliases: List[AliasInfo] = []
                    
                    for deco in func.decorator_list:                        
                        deco_qual_name = get_decorator_qual_name(deco, imports=imports)
                        deco_decl_line = source_lines[node.lineno - 1] if 0 < node.lineno <= len(source_lines) else ''
                        
                        # Only add decorators that have the name 'alias' - this does not filter aliases from other 
                        # classes/modules though
                        if get_decorator_name(deco) != 'alias':
                            continue
                        
                        has_paren = isinstance(deco, ast.Call)
                        if isinstance(deco, ast.Call):
                            args = deco.args
                            kwargs = {kw.arg: kw.value for kw in deco.keywords if kw.arg is not None}
                            
                            # TODO: Handle this better for non constants and in general
                            args_validated: List[ast.Constant] = [arg for arg in args if isinstance(arg, ast.Constant)]
                            kwargs_validated: Dict[str, ast.Constant] = {k: v for k, v in kwargs.items() if isinstance(v, ast.Constant)}
                            
                            # No alias name defined
                            if args_validated:
                                alias_name = args_validated[0].value
                            else:
                                alias_name = None
                                
                            args_mapping = {k: v.value for k, v in kwargs_validated.items()}
                            
                            # END TODO ^^
                            
                        else:
                            alias_name = None
                            args_mapping = None
                        
                        aliases.append(AliasInfo(
                            deco_qual_name, alias_name, args_mapping, has_paren, path, deco.lineno, deco.col_offset, deco_decl_line
                        ))
                    
                    functions.add(FunctionInfo(
                        func_qual_name, path, func.lineno, func.col_offset, func_parameters, aliases, func_decl_line, func_full_impl
                    ))
                    
                decl_line = source_lines[node.lineno - 1] if 0 < node.lineno <= len(source_lines) else ''
                full_impl = '\n'.join(source_lines[node.lineno:node.end_lineno])
                
                info.add(ClassInfo(
                    qual_name, path, node.lineno, node.col_offset, metaclass, 
                    bases, functions, decl_line, full_impl
                ))

    return info

def get_subclass_qual_names(
        targets: Union[str, List[str]],
        classes: Set['ClassInfo']
    ) -> List[str]:
    '''
    Recursively find all qualified class names that inherit from the given target(s).
    
    Parameters
    ----------
    targets : str | List[str]
        One or more fully qualified base class names to search for subclasses of.
    class_info_map : Optional[Set[ClassInfo]]
        The full set of ClassInfo objects to search through.
    
    Returns
    -------
    List[str]
        Fully qualified names of all matching subclasses.
    '''
    target_set = {targets} if isinstance(targets, str) else set(targets)
    result: Set[str] = set()
    queue = deque(target_set)

    # Build a reverse map of base → [class]
    base_to_classes: Dict[str, List[ClassInfo]] = {}
    for cls in classes:
        for base in cls.bases:
            base_to_classes.setdefault(base, []).append(cls)

    # BFS traversal to find subclasses
    while queue:
        current = queue.popleft()
        for subclass in base_to_classes.get(current, []):
            if subclass.qual_name not in result:
                result.add(subclass.qual_name)
                queue.append(subclass.qual_name)

    return sorted(result)

def get_valid_reflexsive_classes(
        classes: Set[ClassInfo], 
        *, 
        exclude_inherited: bool = False,
        exclude_metaclass: bool = False,
    ) -> Set[str]:
    valid_classes = set(VALID_REFLEXSIVE_MODULE_PATHS)
    
    if not exclude_inherited:
        valid_classes.update(get_subclass_qual_names(VALID_REFLEXSIVE_MODULE_PATHS, classes))
    
    if not exclude_metaclass:
        valid_classes.update(
            cls.qual_name for cls in classes
            if cls.metaclass in VALID_REFLEXSIVEMETA_MODULE_PATHS
        )
        
    return valid_classes

def prune_invalid_aliases(classes: Set[ClassInfo]) -> None:
    '''
    Removes decorators with the name 'alias' but are not valid qual_names (Reflexsive & subclasses & metaclass=Reflexsive).
    '''
    # TODO: other classes subclasses that implement ReflexsiveMeta, this prolly applies to other parts too
    valid_classes_for_alias = get_valid_reflexsive_classes(classes)
    valid_top_level_classes_for_alias = set(split_qual_name(cls)[1] for cls in valid_classes_for_alias)
    
    for cls in classes:
        for func in cls.functions:
            for alias in list(func.aliases):
                alias_class_name, _ = split_qual_name(alias.qual_name)

                if (alias_class_name not in valid_classes_for_alias and
                    alias_class_name not in valid_top_level_classes_for_alias):
                    func.aliases.remove(alias)

def prune_aliasless_functions(classes: Set[ClassInfo]) -> None:
    '''
    Removes functions that do not have any aliases. This cant be done in the ast.wakl because we have to validate
    alias classes after we compile a heirarchy graph.
    '''
    for cls in classes:
        for func in list(cls.functions):
            if not len(func.aliases):
                cls.functions.remove(func)
                
def prune_aliasless_classes(
        classes: Set[ClassInfo],
        *, 
        exclude_inherited: bool,
        exclude_metaclass: bool,
    ) -> Set[ClassInfo]:
    '''
    Removes classes that have either no functions with aliases, but only if they are not a Reflexsive class.
    Also sets .valid_reflexsive = True on valid classes. We do this so we can know later if a class is a valid
    reflexsive class or if it just has a @alias function in it. This is used in ClassInfo.render()
    '''
    valid_reflexsive_classes = get_valid_reflexsive_classes(
        classes, 
        exclude_inherited=exclude_inherited, 
        exclude_metaclass=exclude_metaclass,
    )
    pruned_classes = set()
    
    for cls in classes:
        is_valid_class = cls.qual_name in valid_reflexsive_classes
        
        if is_valid_class:
            cls.set_is_valid_reflexsive(True)
        
        if len(cls.functions) > 0 or is_valid_class:
            pruned_classes.add(cls)
            
    return pruned_classes

def get_class_set_in_path(
        path: Path, 
        *, 
        mode: str,
        exclude_inherited: bool,
        exclude_metaclass: bool,
    ) -> Set[ClassInfo]:
    all_classes = collect_classes(path)
    prune_invalid_aliases(all_classes)
    prune_aliasless_functions(all_classes)
    
    return prune_aliasless_classes(
        all_classes, 
        exclude_inherited=exclude_inherited,
        exclude_metaclass=exclude_metaclass,
    )

def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

def render_output(
        classes : Iterable[ClassInfo], 
        *,
        output  : Optional[Path], 
        mode    : str,
        format  : str,
    ) -> None:
    '''
    Write class/function info to file or stdout in the specified format and mode.

    Parameters
    ----------
    classes : list[ClassInfo]
        The class definitions to output.
    output : Optional[Path]
        The file to write to, or None to print to stdout.
    mode : str
        One of 'classes', 'functions', or 'both'.
    format : str
        One of 'txt', 'json', or 'yaml'.
    '''
    # Sort classes as list for reliable output
    classes = sorted(classes, key=lambda cls: (cls.path, cls.qual_name))
    
    if format == 'json':
        payload = [cls.to_dict() for cls in classes]
        content = json.dumps(payload, indent=4, default=str)

    elif format == 'yaml':
        payload = [cls.to_dict() for cls in classes]
        content = yaml.dump(payload, sort_keys=False)

    elif format == 'txt':
        rendered = [render for cls in classes if (render := cls.render(mode))]
        content = '\n\n'.join(rendered)

    else:
        raise ValueError(f'Unsupported format: {format}')
    
    writeln(content, output=output)
    
    # Write extra newline for stat
    if format == 'txt':
        writeln('', output=output)

def render_statistic(
        elapsed: float, 
        results: Iterable[ClassInfo],
        *,
        output  : Optional[Path], 
        mode    : str,
        format  : str,
    ) -> None:
    n_classes   = len([result for result in results if result.is_valid_reflexsive])
    n_functions = sum(len(result.functions) for result in results)
    
    classes_word_str = 'class' if n_classes == 1 else 'classes'
    functions_word_str = 'function' if n_functions == 1 else 'functions'
    
    classes_string   = click.style(f'{n_classes} {classes_word_str}', fg='red' if not results else 'green', bold=True)
    functions_string = click.style(f'{n_functions} {functions_word_str}', fg='red' if not results else 'green', bold=True)
    
    if mode == 'both':
        results_string = f'{classes_string} and {functions_string}'
        content = f'Found {results_string} in {format_elapsed(elapsed)}'
    
    elif mode == 'classes':
        content = f'Found {classes_string} in {format_elapsed(elapsed)}'
    
    elif mode == 'functions':
        content = f'Found {functions_string} in {format_elapsed(elapsed)}'
        
    else:
        raise ValueError(f'Unsupported mode: {mode}')
    
    if output and format != 'txt':
        return
    
    writeln(content, output=output)
    
def get_validation_warnings(
        path                    : Path,
        *,
        exit                    : bool,
        strict                  : bool,
        minimum_warning_level   : WarningLevel,
    ) -> List[Warning]:
    '''
    Generates a list of warnings from the class set. If exit is true, the program will exit 
    after reporting the first error. If strict is true, all warnings will be considered errors.
    '''
    warnings: List[Warning] = []
    
    classes = get_class_set_in_path(
        path, 
        mode='both',
        exclude_inherited=False, 
        exclude_metaclass=False
    )
    
    def add_warning(
            info_objs: Union[Info, Tuple[Info, ...]], 
            level: WarningLevel, 
            exec_typ: Optional[Type[Exception]],
            message: str
        ) -> bool:
        if int(level.value) < int(minimum_warning_level.value):
            return False
            
        info_objs_tuple: Tuple[Info, ...]
        if not isinstance(info_objs, tuple):
            info_objs_tuple = cast(Tuple[Info, ...], (info_objs, ))
        else:
            info_objs_tuple = cast(Tuple[Info, ...], info_objs)
        
        if strict and level != WarningLevel.INFO:
            level = WarningLevel.ERROR
            
        warnings.append(Warning(info_objs_tuple, level, exec_typ, message))
        return level == WarningLevel.ERROR and exit
    
    for cls in sorted(classes, key=lambda cls: (cls.path, cls.qual_name)):
        alias_map: Dict[AliasInfo, List[str]] = {}
        
        if not cls.functions:
            if add_warning(cls, WarningLevel.INFO, None, 
                '$(colored_location): Class \'$(colored_name)\' has no functions defined.'): 
                return warnings
            
        for func in cls.functions:
            seen_alias_names = set()
            for alias in func.aliases:
                # This also catches the warning for self.arg_mapping is None
                if not alias.has_paren and add_warning((cls, func), WarningLevel.ERROR, ReflexsiveNameConflictError,
                    f'$(2::colored_location): Function \'$(1::colored_name).$(2::colored_name)\' has an alias decorator that is not called.'):
                    return warnings 
                
                if not isinstance(alias.alias_name, str) and add_warning((cls, func, alias), WarningLevel.ERROR, ReflexsiveNameConflictError,
                    f'$(3::colored_location): Alias \'$(3::colored_name)\' of \'$(1::colored_name).$(2::colored_name)\' must have a str name, not \'{type(alias.alias_name).__name__}\'.'):
                    return warnings
                
                if alias.alias_name in seen_alias_names and add_warning((cls, func), WarningLevel.ERROR, ReflexsiveNameConflictError,
                    f'$(2::colored_location): Function \'$(1::colored_name).$(2::colored_name)\' has duplicate alias name \'{alias.colored_name}\'.'):
                    return warnings
                
                if alias.arg_mapping:
                    assert alias.has_paren, 'Should always be true.'
                    for param, remapping in alias.arg_mapping.items():
                        if not isinstance(remapping, str):
                            if add_warning((alias), WarningLevel.ERROR, TypeError, f'$(colored_location): Must provide \'$(colored_name)\' '
                                           f'a string remapping value, not \'{type(remapping).__name__}\'.'):
                                return warnings
                            
                        else:
                            if remapping in ('args', 'kwargs', 'self', 'cls') and add_warning((alias), WarningLevel.ERROR, ReflexsiveArgumentError, 
                                f'$(colored_location): Alias \'$(colored_name)\' cannot use reserved name \'{remapping}\'.'):
                                return warnings 
                            
                            if param not in func.parameters and add_warning((cls, func), WarningLevel.ERROR, ReflexsiveArgumentError,
                                f'$(2::colored_location): Alias \'$(2::colored_name)\' remaps non-existent parameter \'{param}\' in function \'$(1::colored_name)\'.'):
                                return warnings
                
                if alias.alias_name:
                    alias_map.setdefault(alias, []).append(f'{cls.colored_name}.{func.colored_name}')
                    seen_alias_names.add(alias.alias_name)
                    
                    
        for alias, funcs_list in alias_map.items():
            funcs = set(funcs_list)
            if len(funcs) == 1:
                continue
            
            funcs_str = ', '.join(funcs)
            if len(funcs) > 1 and add_warning((cls, alias), WarningLevel.ERROR, ReflexsiveNameConflictError,
                f'$(1::colored_location): Alias name $(2::colored_name) is used by multiple functions in $(1::colored_name): {funcs_str}.'):
                return warnings
            
    return sorted(warnings, key=lambda w: int(w.level.value), reverse=True)
