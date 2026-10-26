"""Turning trades into decisions (spec section 3).

Rows for the same share, same side and same market date, started by the same party, are one
decision. Transfers are not decisions.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from trademind.core.markets import market_date
from trademind.core.models import Decision, InitiatedBy, Side, Trade

_GroupKey = tuple[str, str, Side, date, InitiatedBy]


def group_into_decisions(trades: Iterable[Trade]) -> list[Decision]:
    groups: dict[_GroupKey, list[Trade]] = {}
    for trade in sorted(trades, key=lambda t: (t.executed_at, t.id)):
        if trade.side == Side.TRANSFER_OUT:
            continue
        group_key: _GroupKey = (
            trade.market,
            trade.symbol,
            trade.side,
            market_date(trade.executed_at, trade.market),
            trade.initiated_by,
        )
        groups.setdefault(group_key, []).append(trade)

    decisions: list[Decision] = []
    for number, (key, members) in enumerate(groups.items(), start=1):
        market, symbol, side, day, initiated_by = key
        quantity = sum((t.quantity for t in members), Decimal(0))
        value = sum((t.quantity * t.price for t in members), Decimal(0))
        decisions.append(
            Decision(
                id=f"d-{number}",
                trade_ids=[t.id for t in members],
                market_date=day,
                market=market,
                symbol=symbol,
                side=side,
                quantity=quantity,
                avg_price=value / quantity,
                initiated_by=initiated_by,
            )
        )
    return decisions
