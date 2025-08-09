# reflexsive/cli/__init__.py

import click
from .commands import scan, stub

@click.group()
def cli() -> None:
    pass

@cli.command()
def version() -> None:
    '''Show Reflexsive version.'''
    from reflexsive import __name__, __version_short__, __version__
    click.echo('{} {} ({})'.format(
        click.style(__name__.title(), fg='bright_green', bold=True), __version_short__, __version__
    ))

# Add all command groups    
cli.add_command(scan)
cli.add_command(stub)
    
if __name__ == '__main__':
    cli()
