from typing import Set
from pathlib import Path
from typing import Optional
import click

from .helpers import (
    validate_path_input,
    timed, 
    get_class_set_in_path,
    render_output,
    render_statistic,
    WarningLevel,
    get_validation_warnings
)
from .info import ClassInfo 

@click.group()
def scan() -> None:
    '''
    Scan the codebase for Reflexsive classes and aliases for viewing or validation.
    '''
    pass

@scan.command('view')
@click.option(
    '--path', '-p', 
    type=click.Path(writable=False, dir_okay=True, path_type=Path),
    default=Path('.'), 
    help='Path to scan, defaults to ./ if not specified'
)
@click.option(
    '--output', '-o',
    type=click.Path(writable=True, dir_okay=False, path_type=Path),
    help='Write results to a file instead of printing to stdout - extension is infered if not specified'
)
@click.option(
    '--mode', '-m', 
    type=click.Choice(['classes', 'functions', 'both']), 
    default='both', 
    show_default=True, 
    help='Select what to scan for'
)
@click.option(
    '--format', '-f', 
    type=click.Choice(['txt', 'json', 'yaml']), 
    default='txt', 
    show_default=True, 
    help='Select the format of the output'
)
@click.option(
    '--exclude-inherited/--include-inherited',
    is_flag=True, 
    default=False,
    help='Exclude subclasses of Reflexsive'
)
@click.option(
    '--exclude-metaclass/--include-metaclass',
    is_flag=True, 
    default=False,
    help='Exclude metaclass of Reflexsive'
)
def scan_view(
        path                : Path, 
        output              : Optional[Path],
        mode                : str,
        format              : str,
        exclude_inherited   : bool, 
        exclude_metaclass   : bool,
    ) -> None:
    '''Find all ReflexsiveMeta/Reflexsive classes in your codebase.''' 
       
    if not validate_path_input(path):
        return
    
    @timed
    def run() -> Set[ClassInfo]:
        return get_class_set_in_path(
            path, 
            mode=mode,
            exclude_inherited=exclude_inherited, 
            exclude_metaclass=exclude_metaclass
        )

    elapsed, results = run() 
    
    if output and not output.suffix:
        output = output.with_suffix(f'.{format}')
        
    if output and output.exists() and output.is_file():
        output.unlink()
    
    render_output(results, output=output, mode=mode, format=format)
    render_statistic(elapsed, results, output=output, mode=mode, format=format)

@scan.command('validate')
@click.option(
    '--path', '-p', 
    type=click.Path(writable=False, dir_okay=True, path_type=Path),
    default=Path('.'), 
    help='Path to scan'
)
@click.option(
    '--exit/--no-exit', '-x',
    default=False,
    help='Stop validation and exit immediately on the first error encountered.'
)
@click.option(
    '--strict/--no-strict', '-s',
    default=False,
    help='If enabled, fail on any validation error (non-zero exit).'
)
@click.option(
    '--verbose',
    is_flag=True,
    default=False,
    help='If enabled, the program will print all message types.'
)
@click.option(
    '--no-warn',
    is_flag=True,
    default=False,
    help='If enabled, the program suppress printing warning and info types.'
)
def scan_validate(
        path    : Path, 
        exit    : bool,
        strict  : bool,
        verbose : bool,
        no_warn : bool,
    ) -> None:
    ''' 
    Validate all occurances of Reflexsive.alias, or any subclasses or Reflexsive's aliases.
    
    By default, prints error and warning messages. 
    '''
    if not validate_path_input(path):
        return
    
    if no_warn:
        minimum_warning_level = WarningLevel.ERROR
    elif not verbose:
        minimum_warning_level = WarningLevel.WARNING
    else:
        minimum_warning_level = WarningLevel.INFO

    results = get_validation_warnings(path, exit=exit, strict=strict, minimum_warning_level=minimum_warning_level)
    click.echo('\n'.join(res.message for res in results))

@click.group()
def stub() -> None:
    '''
    Tooling for generating and validating .ipy stubs for aliased classes.
    '''
    pass

@stub.command('generate')
@click.argument('target')
@click.option('--output', '-o', default='stubs/', help='Directory to output stub files')
@click.option('--only-aliases', is_flag=True, help='Only include alias stubs')
@click.option('--force', is_flag=True, help='Overwrite existing stub files')
def stubs_generate(target: str, output: str, only_aliases: bool, force: bool) -> None:
    '''Generate .pyi stubs for aliases.'''
    click.echo(f'[NYI] Would generate stubs for {target} -> {output}, only_aliases={only_aliases}, force={force}')


