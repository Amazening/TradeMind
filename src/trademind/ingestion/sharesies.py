"""Reader for the Sharesies Transaction Report CSV (spec section 2).

Rules (spec section 3):
- Times are UTC.
- The "Transaction method" column decides the side. A transfer out is not a sale.
- "Initiated by" of System or Operator means the platform acted, not the user.
- Amount does not include the fee, so it is not used. Quantity x price is.
"""

import csv
import io
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from trademind.core.markets import is_known_market
from trademind.core.models import (
    FileDiagnostics,
    ImportResult,
    InitiatedBy,
    Side,
    SkippedRow,
    Trade,
)

NAME = "sharesies"

REQUIRED_COLUMNS = (
    "Trade ID",
    "Trade date",
    "Instrument code",
    "Instrument name",
    "Market code",
    "Quantity",
    "Price",
    "Currency",
    "Transaction fee",
    "Transaction method",
    "Initiated by",
)

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S.%f (UTC)", "%Y-%m-%d %H:%M:%S (UTC)")

_SIDES = {
    "BUY": Side.BUY,
    "SELL": Side.SELL,
    "TRANSFER OUT": Side.TRANSFER_OUT,
}

_PLATFORM_ACTORS = {"system", "operator"}

# A buy worth less than this in its own currency counts as "small" in the diagnostics.
_SMALL_BUY = Decimal(1)


class _RowError(Exception):
    """A row that cannot be used. The message is shown to the user."""


def matches(header: Sequence[str]) -> bool:
    columns = {name.strip() for name in header}
    return all(column in columns for column in REQUIRED_COLUMNS)


def parse(text: str) -> ImportResult:
    reader = csv.reader(io.StringIO(text))
    header = [name.strip() for name in next(reader, [])]
    trades: list[Trade] = []
    skipped: list[SkippedRow] = []
    seen_ids: set[str] = set()
    methods: Counter[str] = Counter()
    actors: list[str] = []
    small_buy_actors: list[str] = []

    for values in reader:
        row = reader.line_num
        if not any(value.strip() for value in values):
            continue
        record = dict(zip(header, values, strict=False))
        methods[record.get("Transaction method", "").strip().upper() or "(blank)"] += 1
        actor = record.get("Initiated by", "").strip()
        actors.append(actor)
        try:
            trade = _parse_row(row, record)
            if trade.source_id in seen_ids:
                raise _RowError(f"Duplicate Trade ID: {trade.source_id}")
        except _RowError as error:
            skipped.append(SkippedRow(row=row, reason=str(error)))
            continue
        seen_ids.add(trade.source_id)
        trades.append(trade)
        if trade.side == Side.BUY and trade.quantity * trade.price < _SMALL_BUY:
            small_buy_actors.append(actor)

    trades.sort(key=lambda t: (t.executed_at, t.id))
    diagnostics = FileDiagnostics(
        rows_read=len(actors),
        rows_skipped=len(skipped),
        skipped_reasons=_sorted_counts(Counter(_reason_group(s.reason) for s in skipped)),
        transaction_methods=_sorted_counts(methods),
        initiated_by=_sorted_counts(Counter(_actor_labels(actors))),
        small_buys=_sorted_counts(Counter(_actor_labels(actors, small_buy_actors))),
    )
    return ImportResult(broker=NAME, trades=trades, skipped_rows=skipped, diagnostics=diagnostics)


def _actor_labels(all_actors: list[str], chosen: list[str] | None = None) -> list[str]:
    """Label each actor for the diagnostics. The investor's own name becomes "you".

    The investor's name is the most common label that is not System or Operator.
    """
    own = Counter(a for a in all_actors if a and a.lower() not in _PLATFORM_ACTORS)
    own_name = own.most_common(1)[0][0] if own else None
    return [
        "you" if actor == own_name else (actor or "(blank)")
        for actor in (all_actors if chosen is None else chosen)
    ]


def _reason_group(reason: str) -> str:
    """A skipped row's reason without the value from the file, except labels that help."""
    if reason.startswith(("Unknown transaction method", "Unknown market")):
        return reason
    return reason.split(":", 1)[0]


def _sorted_counts(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items()))


def _parse_row(row: int, record: dict[str, str]) -> Trade:
    method = record["Transaction method"].strip().upper()
    side = _SIDES.get(method)
    if side is None:
        raise _RowError(f"Unknown transaction method: {record['Transaction method'].strip()}")

    market = record["Market code"].strip().upper()
    if not is_known_market(market):
        raise _RowError(f"Unknown market: {record['Market code'].strip()}")

    quantity = _decimal(record["Quantity"], "Quantity")
    if quantity <= 0:
        raise _RowError("Quantity must be greater than zero")
    price = _decimal(record["Price"], "Price")
    if price <= 0:
        raise _RowError("Price must be greater than zero")
    fee_text = record["Transaction fee"].strip()
    fee = _decimal(fee_text, "Transaction fee") if fee_text else Decimal(0)
    if fee < 0:
        raise _RowError("Transaction fee cannot be negative")

    symbol = record["Instrument code"].strip().upper()
    if not symbol:
        raise _RowError("Instrument code is empty")
    source_id = record["Trade ID"].strip()
    if not source_id:
        raise _RowError("Trade ID is empty")

    actor = record["Initiated by"].strip().lower()
    return Trade(
        id=f"row-{row}",
        source_id=source_id,
        executed_at=_date(record["Trade date"]),
        market=market,
        symbol=symbol,
        name=record["Instrument name"].strip(),
        side=side,
        quantity=quantity,
        price=price,
        currency=record["Currency"].strip().upper(),
        fee=fee,
        initiated_by=InitiatedBy.PLATFORM if actor in _PLATFORM_ACTORS else InitiatedBy.USER,
    )


def _decimal(text: str, label: str) -> Decimal:
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise _RowError(f"{label} is not a number: {text.strip()!r}") from None
    if not value.is_finite():
        raise _RowError(f"{label} is not a number: {text.strip()!r}")
    return value


def _date(text: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise _RowError(f"Trade date is not in the expected format: {text.strip()!r}")
