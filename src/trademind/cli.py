"""Command line interface. Uses the same layers as the web app."""

import typer

from trademind import __version__

app = typer.Typer(help="Find behaviour patterns in a share trading history.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """TradeMind command line tool."""


@app.command()
def version() -> None:
    """Show the TradeMind version."""
    typer.echo(__version__)
