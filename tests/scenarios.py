"""Hand-made trading histories for testing the patterns. All names and numbers are made up.

Everything trades on the NZX in NZD, so no exchange rates are needed. Prices come from flat or
spiky series built by hand, so the expected result of each pattern can be worked out on paper.
"""

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import Decimal

from tests.helpers import make_trade
from trademind.core.decisions import group_into_decisions
from trademind.core.models import EnrichedHistory, InitiatedBy, PriceSeries, Side, Trade

START = date(2022, 1, 1)


def nzx_trade(
    n: int,
    day: date,
    symbol: str = "AAA",
    side: Side = Side.BUY,
    quantity: str = "1",
    price: str = "10",
    initiated_by: InitiatedBy = InitiatedBy.USER,
) -> Trade:
    return make_trade(
        n,
        f"{day.isoformat()}T02:00:00",
        market="NZX",
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        initiated_by=initiated_by,
        currency="NZD",
    )


def flat(price: str = "10", days: int = 1200) -> dict[date, Decimal]:
    """The same close every calendar day, from START."""
    return {START + timedelta(days=n): Decimal(price) for n in range(days)}


def spiky(days: int = 1000, every: int = 30, offset: int = 10) -> dict[date, Decimal]:
    """Flat at 10, with a one-day jump to 13 every `every` days."""
    return {
        START + timedelta(days=n): Decimal("13")
        if n >= offset and (n - offset) % every == 0
        else Decimal("10")
        for n in range(days)
    }


def history_of(
    trades: Iterable[Trade],
    closes: Mapping[str, dict[date, Decimal]],
    *,
    unpriced: Iterable[str] = (),
) -> EnrichedHistory:
    """A history with market prices for `closes`, and own-trade prices for `unpriced` keys."""
    trade_list = list(trades)
    prices = {
        key: PriceSeries(currency="NZD", closes=series, source="market")
        for key, series in closes.items()
    }
    missing = sorted(unpriced)
    for key in missing:
        prices[key] = PriceSeries(currency="NZD", closes={START: Decimal(10)}, source="own_trades")
    return EnrichedHistory(
        broker="test",
        trades=trade_list,
        decisions=group_into_decisions(trade_list),
        prices=prices,
        splits={},
        fx_to_nzd={},
        missing_prices=missing,
        data_notes=[],
    )
