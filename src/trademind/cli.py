"""Command line interface. Uses the same layers as the web app."""

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from trademind import __version__
from trademind.core.decisions import group_into_decisions
from trademind.core.errors import TradeMindError
from trademind.core.holdings import Ledger
from trademind.core.models import InitiatedBy, Side
from trademind.ingestion import import_file

app = typer.Typer(help="Find behaviour patterns in a share trading history.", no_args_is_help=True)

_MAX_SKIPPED_SHOWN = 20


@app.callback()
def main() -> None:
    """TradeMind command line tool."""


@app.command()
def version() -> None:
    """Show the TradeMind version."""
    typer.echo(__version__)


@app.command(name="import")
def import_(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    holdings: Annotated[bool, typer.Option(help="Also list open positions.")] = False,
) -> None:
    """Read a broker CSV and print a summary of what was found."""
    try:
        result = import_file(path)
    except TradeMindError as error:
        typer.echo(f"Error ({error.code}): {error}", err=True)
        raise typer.Exit(code=1) from error

    trades = result.trades
    sides = Counter(trade.side for trade in trades)
    decisions = group_into_decisions(trades)
    by_actor = Counter(decision.initiated_by for decision in decisions)
    ledger = Ledger.from_trades(trades)

    typer.echo(f"Broker: {result.broker}")
    typer.echo(
        f"Trades read: {len(trades)} "
        f"(buys {sides[Side.BUY]}, sells {sides[Side.SELL]}, "
        f"transfers out {sides[Side.TRANSFER_OUT]})"
    )
    typer.echo(
        f"Decisions: {len(decisions)} "
        f"(yours {by_actor[InitiatedBy.USER]}, platform {by_actor[InitiatedBy.PLATFORM]})"
    )
    typer.echo(f"Period: {trades[0].executed_at.date()} to {trades[-1].executed_at.date()}")
    typer.echo(f"Markets: {', '.join(sorted({trade.market for trade in trades}))}")
    typer.echo(f"Instruments: {len({(trade.market, trade.symbol) for trade in trades})}")
    typer.echo(f"Skipped rows: {len(result.skipped_rows)}")
    for skipped in result.skipped_rows[:_MAX_SKIPPED_SHOWN]:
        typer.echo(f"  row {skipped.row}: {skipped.reason}")
    if len(result.skipped_rows) > _MAX_SKIPPED_SHOWN:
        typer.echo(f"  and {len(result.skipped_rows) - _MAX_SKIPPED_SHOWN} more")
    for warning in ledger.warnings:
        typer.echo(f"Warning: {warning}")

    if holdings:
        typer.echo("")
        typer.echo("Open positions (average cost includes buy fees, in the trade currency):")
        for (market, symbol), position in sorted(ledger.positions().items()):
            typer.echo(
                f"  {market}:{symbol}  {position.quantity.normalize():f} shares  "
                f"avg cost {position.avg_cost:.4f}"
            )
