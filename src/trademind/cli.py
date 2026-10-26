"""Command line interface. Uses the same layers as the web app."""

from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from trademind import __version__
from trademind.analysis import analyse as analyse_history
from trademind.core.decisions import group_into_decisions
from trademind.core.errors import TradeMindError
from trademind.core.holdings import Ledger
from trademind.core.markets import instrument_key
from trademind.core.models import EnrichedHistory, InitiatedBy, Side
from trademind.core.settings import get_settings
from trademind.core.splits import split_label
from trademind.enrichment import (
    CachedPriceSource,
    PriceSource,
    YahooPriceSource,
    price_consistency,
)
from trademind.enrichment import enrich as enrich_history
from trademind.ingestion import import_file
from trademind.reporting import (
    ChatModel,
    ExplanationCache,
    GroqModel,
    OllamaModel,
    explain_report,
    render_text,
)

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


class OutputFormat(StrEnum):
    JSON = "json"
    TEXT = "text"


class ExplainWith(StrEnum):
    NONE = "none"
    GROQ = "groq"
    OLLAMA = "ollama"


def _chat_model(choice: ExplainWith) -> ChatModel | None:
    settings = get_settings()
    if choice == ExplainWith.GROQ:
        return GroqModel(settings.groq_api_key, settings.groq_model)
    if choice == ExplainWith.OLLAMA:
        return OllamaModel(settings.ollama_url, settings.ollama_model)
    return None


def _enriched(path: Path, no_cache: bool) -> EnrichedHistory:
    source: PriceSource = YahooPriceSource()
    if not no_cache:
        source = CachedPriceSource(source, get_settings().price_cache_dir)
    try:
        return enrich_history(import_file(path), source)
    except TradeMindError as error:
        typer.echo(f"Error ({error.code}): {error}", err=True)
        raise typer.Exit(code=1) from error


@app.command()
def analyse(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[
        OutputFormat, typer.Option("--format", help="json is the full report.")
    ] = OutputFormat.JSON,
    no_cache: Annotated[bool, typer.Option(help="Ignore the price cache.")] = False,
    explain: Annotated[
        ExplainWith,
        typer.Option(help="Add plain English explanations. groq is hosted, ollama is local."),
    ] = ExplainWith.NONE,
) -> None:
    """Read a broker CSV and find behaviour patterns in it."""
    try:
        model = _chat_model(explain)
    except TradeMindError as error:
        typer.echo(f"Error ({error.code}): {error}", err=True)
        raise typer.Exit(code=1) from error

    report = analyse_history(_enriched(path, no_cache))
    if model is not None:
        cache = ExplanationCache(None if no_cache else get_settings().explanation_cache_dir)
        report = explain_report(report, model, cache)
    if output_format == OutputFormat.TEXT:
        typer.echo(render_text(report))
    else:
        typer.echo(report.model_dump_json(indent=2))


@app.command()
def enrich(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    no_cache: Annotated[bool, typer.Option(help="Ignore the price cache.")] = False,
) -> None:
    """Read a broker CSV, add market prices, and print how well each share is covered."""
    history = _enriched(path, no_cache)

    ratios = price_consistency(history)
    typer.echo(f"Trades: {len(history.trades)}   Decisions: {len(history.decisions)}")
    typer.echo(
        f"Instruments with market prices: {len(history.prices) - len(history.missing_prices)}"
    )
    typer.echo(f"Instruments without: {len(history.missing_prices)}")
    typer.echo(f"Currencies converted to NZD: {', '.join(sorted(history.fx_to_nzd)) or 'none'}")
    typer.echo("")
    typer.echo("Per instrument (trade price / market close, median; 1.00 means they agree):")
    for key in sorted(history.prices):
        series = history.prices[key]
        trade_count = sum(
            1 for trade in history.trades if instrument_key(trade.market, trade.symbol) == key
        )
        days = sorted(series.closes)
        coverage = f"{len(days)} days {days[0]} to {days[-1]}"
        ratio = f"{ratios[key]:.2f}" if key in ratios else "n/a"
        splits = ", ".join(f"{s.date} {split_label(s)}" for s in history.splits.get(key, []))
        typer.echo(
            f"  {key:<12} {trade_count:>4} trades  {series.source:<10}  {coverage}  "
            f"ratio {ratio}" + (f"  splits: {splits}" if splits else "")
        )
    typer.echo("")
    typer.echo(f"Data notes: {len(history.data_notes)}")
    for note in history.data_notes:
        typer.echo(f"  [{note.level}] {note.message}")
