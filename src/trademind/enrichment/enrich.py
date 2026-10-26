"""Enrichment: add market context to imported trades (spec section 4).

For each instrument: daily prices, and any splits that happened after the first trade. Trades are
rescaled to match the prices. Shares with no price data get a series built from the investor's own
trade prices, and a note, so later steps know the data is thin.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from trademind.core.decisions import group_into_decisions
from trademind.core.markets import instrument_key, market_date
from trademind.core.models import (
    DataNote,
    EnrichedHistory,
    ImportResult,
    PriceSeries,
    Split,
    Trade,
)
from trademind.core.prices import PriceLookup
from trademind.core.splits import adjust_for_splits, count_adjusted, split_label
from trademind.enrichment.source import PriceSource

# The run-up pattern compares a buy with the share's previous year of prices.
HISTORY_DAYS_BEFORE_FIRST_TRADE = 366

# A share's median trade price should be close to the market close on the same day. Outside this
# range the market prices are probably on a different basis, so they are not used.
CONSISTENT_RATIO_RANGE = (Decimal("0.8"), Decimal("1.25"))


def enrich(result: ImportResult, source: PriceSource) -> EnrichedHistory:
    trades = result.trades
    first_day = min(trade.executed_at for trade in trades).date()
    last_day = max(trade.executed_at for trade in trades).date()
    start = first_day - timedelta(days=HISTORY_DAYS_BEFORE_FIRST_TRADE)

    notes = [
        DataNote(level="warning", message=f"Row {row.row} was skipped: {row.reason}")
        for row in result.skipped_rows
    ]

    by_instrument: dict[str, list[Trade]] = defaultdict(list)
    for trade in trades:
        by_instrument[instrument_key(trade.market, trade.symbol)].append(trade)

    prices: dict[str, PriceSeries] = {}
    splits: dict[str, list[Split]] = {}
    missing: list[str] = []

    for key in sorted(by_instrument):
        own = by_instrument[key]
        market, symbol, currency = own[0].market, own[0].symbol, own[0].currency
        history = source.fetch_prices(market, symbol, start, last_day)

        if history is not None and history.currency.upper() != currency.upper():
            notes.append(
                DataNote(
                    level="warning",
                    message=(
                        f"{key}: prices are in {history.currency} but trades are in {currency}. "
                        "The market prices were not used."
                    ),
                )
            )
            history = None

        if history is None:
            missing.append(key)
            prices[key] = _own_trade_series(own, currency)
            notes.append(
                DataNote(
                    level="warning",
                    message=(
                        f"No market prices for {key}. Only your own trade prices are used for "
                        "it, so patterns that need market prices skip it."
                    ),
                )
            )
            continue

        prices[key] = PriceSeries(currency=currency, closes=history.closes, source="market")
        first_trade_day = market_date(own[0].executed_at, market)
        relevant = [split for split in history.splits if split.date > first_trade_day]
        if relevant:
            splits[key] = relevant

    adjusted = adjust_for_splits(trades, splits)
    for key, key_splits in splits.items():
        for split in key_splits:
            count = count_adjusted(trades, key, split)
            if count:
                notes.append(
                    DataNote(
                        level="info",
                        message=(
                            f"{key}: {count} trades before {split.date} were adjusted for a "
                            f"{split_label(split)} share split or consolidation."
                        ),
                    )
                )

    # A provider can be wrong in ways its own data does not show, such as a price adjustment for a
    # capital raising that is not listed as a split. If the market prices do not agree with the
    # investor's own trade prices, they are not used.
    low, high = CONSISTENT_RATIO_RANGE
    for key, ratio in sorted(_median_ratios(adjusted, prices).items()):
        if low <= ratio <= high:
            continue
        own_adjusted = [t for t in adjusted if instrument_key(t.market, t.symbol) == key]
        prices[key] = _own_trade_series(own_adjusted, prices[key].currency)
        missing.append(key)
        notes.append(
            DataNote(
                level="warning",
                message=(
                    f"{key}: your trade prices are on average {ratio:.2f} times the market close "
                    "on the same day, so the market prices look to be on a different basis. They "
                    "were not used. Only your own trade prices are used for it, so patterns that "
                    "need market prices skip it."
                ),
            )
        )

    fx = _fetch_fx({trade.currency for trade in trades}, source, start, last_day, notes)

    return EnrichedHistory(
        broker=result.broker,
        trades=adjusted,
        decisions=group_into_decisions(adjusted),
        prices=prices,
        splits=splits,
        fx_to_nzd=fx,
        missing_prices=sorted(missing),
        data_notes=notes,
    )


def price_consistency(history: EnrichedHistory) -> dict[str, Decimal]:
    """Median of (trade price / market close on that day), per instrument with market prices.

    Close to 1 means the trades and the price series agree. Instruments whose market prices were
    rejected are not included.
    """
    return _median_ratios(history.trades, history.prices)


def _median_ratios(trades: list[Trade], prices: dict[str, PriceSeries]) -> dict[str, Decimal]:
    lookups = {
        key: PriceLookup(series.closes)
        for key, series in prices.items()
        if series.source == "market"
    }
    ratios: dict[str, list[Decimal]] = defaultdict(list)
    for trade in trades:
        key = instrument_key(trade.market, trade.symbol)
        lookup = lookups.get(key)
        if lookup is None:
            continue
        close = lookup.on_or_before(market_date(trade.executed_at, trade.market))
        if close:
            ratios[key].append(trade.price / close)
    return {key: median(values) for key, values in ratios.items() if values}


def _own_trade_series(trades: list[Trade], currency: str) -> PriceSeries:
    """One price per market date: the quantity-weighted average of the investor's own trades."""
    quantity: dict[date, Decimal] = defaultdict(Decimal)
    value: dict[date, Decimal] = defaultdict(Decimal)
    for trade in trades:
        day = market_date(trade.executed_at, trade.market)
        quantity[day] += trade.quantity
        value[day] += trade.quantity * trade.price
    closes = {day: value[day] / quantity[day] for day in quantity}
    return PriceSeries(currency=currency, closes=closes, source="own_trades")


def _fetch_fx(
    currencies: set[str],
    source: PriceSource,
    start: date,
    end: date,
    notes: list[DataNote],
) -> dict[str, dict[date, Decimal]]:
    fx: dict[str, dict[date, Decimal]] = {}
    for currency in sorted(currencies):
        if currency.upper() == "NZD":
            continue
        rates = source.fetch_fx_to_nzd(currency, start, end)
        if rates is None:
            notes.append(
                DataNote(
                    level="warning",
                    message=(
                        f"No exchange rates from {currency} to NZD. Anything that needs a total "
                        f"in NZD leaves out {currency} trades."
                    ),
                )
            )
            continue
        fx[currency.upper()] = rates
    return fx
