from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from types import EllipsisType
from typing import Any, Optional, Dict, List, Set
import re
import click
import textwrap

from ._split_qual_name import split_qual_name
from .statics import (
    VALID_REFLEXSIVE_CLASS_NAME,
    VALID_REFLEXSIVE_MODULE_PATHS,
    VALID_REFLEXSIVEMETA_CLASS_NAME,
    VALID_REFLEXSIVEMETA_MODULE_PATHS,
)

ConstantValue = str | bytes | bool | int | float | complex | EllipsisType | None

class Info(ABC):
    qual_name   : str
    path        : Path
    row         : int
    column      : int
    
    @property
    def name(self) -> str:
        return split_qual_name(self.qual_name)[1]
    
    @property
    @abstractmethod
    def colored_name(self) -> str:
        pass
    
    @property
    def location(self) -> str:
        column_str = f':{self.column}' if self.column else ''
        return f'{self.path}:{self.row}{column_str}'
    
    @property
    def colored_location(self) -> str:
        return click.style(self.location, fg='black', underline=True)

@dataclass(frozen=True)
class AliasInfo(Info):
    qual_name   : str
    alias_name  : Optional[ConstantValue]            # These can be any constant - we do not raise any errors during AST parsing
    arg_mapping : Optional[Dict[str, ConstantValue]] # These can be any constant - we do not raise any errors during AST parsing
    has_paren   : bool
    path        : Path
    row         : int
    column      : int
    decl_line   : str
    
    @property
    def colored_name(self) -> str:
        return click.style(self.alias_name, fg='red', bold=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'qual-name': self.qual_name,
            'alias-name': self.alias_name,
            'arg-mapping': self.arg_mapping,
            'has-paren': self.has_paren,
            'path': str(self.path),
            'line': self.row,
            'column': self.column,
            'declaration': self.decl_line,
        }
    
    def __hash__(self) -> int:
        # We want the same declared alias in different places to match, leave out path, row, column, and declaration, also
        # arg_mapping to match across different sets of args
        return hash((
            self.qual_name,
            self.alias_name,
            self.has_paren,
        ))
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AliasInfo):
            return NotImplemented
        return (
            self.qual_name == other.qual_name and
            self.alias_name == other.alias_name and
            self.has_paren == other.has_paren
        )

@dataclass(frozen=True)
class FunctionInfo(Info):
    qual_name   : str
    path        : Path
    row         : int
    column      : int
    parameters  : Set[str]
    aliases     : List[AliasInfo]
    decl_line   : str
    full_impl   : str
    
    @property
    def colored_name(self) -> str:
        return click.style(self.name, fg='blue', bold=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.qual_name,
            'path': str(self.path),
            'line': self.row,
            'column': self.column,
            'parameters': self.parameters,
            'aliases': list(alias.to_dict() for alias in self.aliases),
            'implementaion': f'{self.decl_line}\n{self.full_impl}',
        }
    
    def __hash__(self) -> int:
        return hash((
            self.qual_name,
            self.path.resolve(),
            self.row,
            self.column,
            frozenset(sorted(self.parameters)),
            self.decl_line.strip(),
            self.full_impl.strip(),
        ))
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FunctionInfo):
            return NotImplemented
        return (
            self.qual_name == other.qual_name and
            self.path.resolve() == other.path.resolve() and
            self.row == other.row and
            self.column == other.column and
            self.parameters == other.parameters and
            self.decl_line == other.decl_line and
            self.full_impl == other.full_impl
        )

@dataclass(frozen=True)
class ClassInfo(Info):
    qual_name   : str
    path        : Path
    row         : int
    column      : int
    metaclass   : str
    bases       : Set[str]
    functions   : Set[FunctionInfo]
    decl_line   : str
    full_impl   : str
    
    # Workaround for frozen=True, list of 1 element
    _is_valid_reflexsive: List[bool] = field(default_factory=lambda: [False]) # Set by `prune_aliasless_classes`

    @property
    def colored_name(self) -> str:
        return click.style(self.name, fg='cyan', bold=True)
    
    @property
    def is_valid_reflexsive(self) -> bool:
        assert len(self._is_valid_reflexsive) == 1, 'Stop messing with my implementaion!'
        return self._is_valid_reflexsive[0]
    
    def set_is_valid_reflexsive(self, value: bool) -> None:
        assert len(self._is_valid_reflexsive) == 1, 'Stop messing with my implementaion!'
        self._is_valid_reflexsive[0] = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.qual_name,
            'path': str(self.path),
            'line': self.row,
            'column': self.column,
            'metaclass': self.metaclass,
            'bases': list(self.bases),
            'functions': list(func.to_dict() for func in self.functions),
            'implementaion': f'{self.decl_line}\n{self.full_impl}',
        }
        
    def render(self, mode: str) -> str:
        def highlight_bases(declaration: str) -> str:
            match = re.match(r'(class\s+\w+\s*\((.*?)\))', declaration)
            if not match:
                return declaration
            
            def color_base(base: str) -> str:
                base_like_reflexsive = (
                    base == VALID_REFLEXSIVE_CLASS_NAME or
                    base in VALID_REFLEXSIVE_MODULE_PATHS
                )
                base_like_reflexsive_meta = (
                    (metaclass := base.removeprefix('metaclass=')) == VALID_REFLEXSIVEMETA_CLASS_NAME or
                     metaclass in VALID_REFLEXSIVEMETA_MODULE_PATHS
                )
                                
                if base_like_reflexsive or base_like_reflexsive_meta:
                    if metaclass != base:
                        return '{}={}'.format(click.style('metaclass', fg='bright_yellow', italic=True), 
                                              click.style(metaclass, fg='green'))
                    else:
                        return click.style(base, fg='green')
                
                return click.style(base, fg='yellow')

            base_group = match.group(2)
            bases = [b.strip() for b in base_group.split(',') if b.strip()]
            colored_bases = [color_base(b) for b in bases]
            
            start, end = match.span(2)
            highlighted_decl = (
                declaration[:start] +
                ', '.join(colored_bases) +
                declaration[end:]
            )
            return highlighted_decl
        
        column_str = f':{self.column}' if self.column else ''
        path_str = click.style(f'{self.path}:{self.row}{column_str}', fg='black', underline=True)
        
        lines = []

        if mode in ('classes', 'both') and self.is_valid_reflexsive:
            lines.append(f'{path_str}: {self.colored_name}')
            lines.append(textwrap.indent(highlight_bases(self.decl_line.strip()), ' ' * 4))

        if mode in ('functions', 'both') and self.functions:
            for func in sorted(self.functions, key=lambda f: (f.row, f.qual_name)):
                func_col_str = f':{func.column}' if func.column else ''
                func_path_str = click.style(f'{func.path}:{func.row}{func_col_str}', fg='black', underline=True)
                lines.append(f'{func_path_str}: {func.colored_name}')
                
                aliases = sorted(func.aliases, key=lambda a: a.row)
                for i, alias in enumerate(aliases):        
                    alias_qual_name = click.style(f'@{alias.qual_name}', fg='magenta', bold=True)
                    alias_params = ''
                    
                    if alias.alias_name:
                        alias_params = '\'{}\''.format(click.style(alias.alias_name, fg='yellow'))
                    
                    if alias.arg_mapping:
                        alias_params_no_name = ', '.join('\'{}\'=\'{}\''.format(
                                click.style(param, fg='yellow'), 
                                click.style(param_alias, fg='yellow')
                            ) for param, param_alias in alias.arg_mapping.items())
                        alias_params = ', '.join(s for s in [alias_params, alias_params_no_name] if s)
                    
                    alias_params_parens = f'({alias_params})' if alias.has_paren else alias_params
                    
                    alias_line = f'{alias_qual_name}{alias_params_parens}'
                    lines.append(textwrap.indent(alias_line, ' ' * 4))
                    
                    # Draw elipses to fill in for decorators that we don't care about
                    row_dist = (aliases[i + 1].row if i + 1  < len(aliases) else func.row) - alias.row
                    for _ in range(row_dist - 1):
                        lines.append(textwrap.indent('...', ' ' * 4))

                lines.append(textwrap.indent(textwrap.dedent(func.decl_line), ' ' * 4))
                lines.append(textwrap.indent(textwrap.dedent(func.full_impl), ' ' * 8).rstrip('\n'))
                
        return '\n'.join(lines)
    
    def __hash__(self) -> int:
        return hash((
            self.qual_name,
            self.path.resolve(),
            self.row,
            self.column,
            self.metaclass,
            tuple(self.bases),
            self.decl_line.strip(),
            self.full_impl.strip(),
        ))
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClassInfo):
            return NotImplemented
        return (
            self.qual_name == other.qual_name and
            self.path.resolve() == other.path.resolve() and
            self.row == other.row and
            self.column == other.column and
            self.decl_line == other.decl_line and
            self.full_impl == other.full_impl
        )