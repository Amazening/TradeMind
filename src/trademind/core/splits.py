"""Adjusting trades for share splits and consolidations.

Providers give prices on today's basis. A trade made before a split is on the old basis, so its
quantity and price are rescaled to match. Without this, a 1-for-25 consolidation looks like a
2,400% price jump.
"""

from collections.abc import Iterable, Mapping, Sequence

from trademind.core.markets import instrument_key, market_date
from trademind.core.models import Split, Trade


def split_label(split: Split) -> str:
    return f"{split.numerator.normalize():f}:{split.denominator.normalize():f}"


def adjust_for_splits(
    trades: Iterable[Trade], splits: Mapping[str, Sequence[Split]]
) -> list[Trade]:
    """Rescale trades made before a split. Trades on or after the split date are unchanged."""
    adjusted: list[Trade] = []
    for trade in trades:
        applicable = _splits_after(trade, splits)
        if not applicable:
            adjusted.append(trade)
            continue
        quantity = trade.quantity
        price = trade.price
        for split in applicable:
            quantity = quantity * split.numerator / split.denominator
            price = price * split.denominator / split.numerator
        adjusted.append(trade.model_copy(update={"quantity": quantity, "price": price}))
    return adjusted


def _splits_after(trade: Trade, splits: Mapping[str, Sequence[Split]]) -> list[Split]:
    day = market_date(trade.executed_at, trade.market)
    key = instrument_key(trade.market, trade.symbol)
    return [split for split in splits.get(key, ()) if day < split.date]


def count_adjusted(trades: Iterable[Trade], key: str, split: Split) -> int:
    """How many trades of one instrument happened before `split`."""
    return sum(
        1
        for trade in trades
        if instrument_key(trade.market, trade.symbol) == key
        and market_date(trade.executed_at, trade.market) < split.date
    )
