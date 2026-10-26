"""Builders for hand-made test data. All names, tickers and numbers here are made up."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from trademind.core.models import InitiatedBy, Side, Trade

SHARESIES_HEADER = (
    "Trade ID,Trade date,Instrument code,Instrument name,Market code,Quantity,Price,"
    "Transaction type,Currency,Amount,Transaction fee,Transaction method,Portfolio,Initiated by"
)


def sharesies_row(
    trade_id: str = "T1",
    date: str = "2024-03-04 02:15:30.123456 (UTC)",
    code: str = "AAA",
    name: str = "Example Corp",
    market: str = "ASX",
    quantity: str = "10",
    price: str = "2.50",
    kind: str = "BUY",
    currency: str = "aud",
    fee: str = "0.12",
    method: str | None = None,
    actor: str = "Sam",
) -> str:
    try:
        amount = Decimal(quantity) * Decimal(price)
    except InvalidOperation:  # tests can pass bad values on purpose
        amount = Decimal(0)
    return (
        f"{trade_id},{date},{code},{name},{market},{quantity},{price},{kind},{currency},"
        f"{amount},{fee},{method or kind},Investments,{actor}"
    )


def sharesies_csv(*rows: str) -> str:
    return "\n".join([SHARESIES_HEADER, *rows]) + "\n"


def make_trade(
    n: int = 1,
    when: str = "2024-03-04T02:00:00",
    market: str = "ASX",
    symbol: str = "AAA",
    side: Side = Side.BUY,
    quantity: str = "10",
    price: str = "2.00",
    fee: str = "0",
    initiated_by: InitiatedBy = InitiatedBy.USER,
    currency: str = "AUD",
) -> Trade:
    return Trade(
        id=f"row-{n}",
        source_id=f"T{n}",
        executed_at=datetime.fromisoformat(when).replace(tzinfo=UTC),
        market=market,
        symbol=symbol,
        name="Example Corp",
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        currency=currency,
        fee=Decimal(fee),
        initiated_by=initiated_by,
    )
