"""Holdings and average cost, worked out from trades.

Every pattern uses this one helper so they all agree on the numbers (spec section 6.2).

- Buys add shares at cost: quantity x price + fee.
- Sells and transfers out remove shares at the average cost, so the average does not change.
- Positions are per market and symbol, in the trade currency.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trademind.core.models import Side, Trade

_ROUNDING_TOLERANCE = Decimal("0.000001")

PositionKey = tuple[str, str]


@dataclass(frozen=True)
class Position:
    quantity: Decimal
    cost: Decimal

    @property
    def avg_cost(self) -> Decimal:
        return self.cost / self.quantity if self.quantity > 0 else Decimal(0)


_EMPTY = Position(Decimal(0), Decimal(0))


class Ledger:
    def __init__(self) -> None:
        self._positions: dict[PositionKey, Position] = {}
        self.warnings: list[str] = []

    @classmethod
    def from_trades(cls, trades: Iterable[Trade], as_of: datetime | None = None) -> "Ledger":
        """Apply trades in time order, up to and including `as_of` if given."""
        ledger = cls()
        for trade in sorted(trades, key=lambda t: (t.executed_at, t.id)):
            if as_of is not None and trade.executed_at > as_of:
                break
            ledger.apply(trade)
        return ledger

    def position(self, market: str, symbol: str) -> Position:
        return self._positions.get((market, symbol), _EMPTY)

    def positions(self) -> dict[PositionKey, Position]:
        """Open positions only."""
        return {key: pos for key, pos in self._positions.items() if pos.quantity > 0}

    def apply(self, trade: Trade) -> None:
        key = (trade.market, trade.symbol)
        current = self._positions.get(key, _EMPTY)

        if trade.side == Side.BUY:
            self._positions[key] = Position(
                current.quantity + trade.quantity,
                current.cost + trade.quantity * trade.price + trade.fee,
            )
            return

        quantity = trade.quantity
        if quantity > current.quantity + _ROUNDING_TOLERANCE:
            self.warnings.append(
                f"{trade.market}:{trade.symbol} {trade.side.value} on "
                f"{trade.executed_at.date()} is larger than the {current.quantity} held. "
                "The history may be missing earlier buys or transfers in."
            )
        if quantity >= current.quantity:
            self._positions[key] = _EMPTY
            return
        remaining = current.quantity - quantity
        self._positions[key] = Position(remaining, current.cost * remaining / current.quantity)
