"""Overtrading (spec section 5.1): does the investor trade a large share of the portfolio?

Measure, after Barber and Odean (2000): for each month, purchases and sales are each divided by the
portfolio value at the start of the month. Monthly turnover is the average of the two. The
paper's most active fifth of households traded above 8.8% a month.

Differences from the paper:
- Trades are valued at the trade price. The paper values them at the start-of-month price.
- Months that start with a portfolio under NZ$500 are left out. A new investor adding money to a
  tiny portfolio would show huge turnover that says nothing about trading habits.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from trademind.analysis.common import (
    Valuer,
    confidence_level,
    day_before,
    month_starts,
    user_decisions,
)
from trademind.core.holdings import Ledger
from trademind.core.markets import instrument_key
from trademind.core.models import (
    Decision,
    EnrichedHistory,
    Evidence,
    Finding,
    FindingSample,
    Side,
)

PATTERN = "overtrading"
TITLE = "Trading a large share of the portfolio"
THRESHOLD_MONTHLY_TURNOVER = 0.088
MIN_MONTHS = 6
MIN_DECISIONS = 10
MIN_START_VALUE_NZD = Decimal(500)
EVIDENCE_MONTHS = 3
EVIDENCE_DECISIONS_PER_MONTH = 5

_THRESHOLD_TEXT = "Average monthly turnover above 8.8%"


@dataclass
class _Month:
    start: date
    turnover: float
    decisions: list[Decision]
    values: dict[str, Decimal]  # decision id -> NZD value


def detect(history: EnrichedHistory) -> Finding:
    decisions = user_decisions(history)
    if not decisions:
        return _insufficient(0, 0, [])

    valuer = Valuer(history)
    months: list[_Month] = []
    small_months = 0
    unpriced_decisions = 0

    first = min(d.market_date for d in decisions)
    last = max(d.market_date for d in decisions)
    for start in month_starts(first, last):
        start_value = _portfolio_value(history, valuer, start)
        if start_value is None or start_value < MIN_START_VALUE_NZD:
            if start_value is not None and start_value > 0:
                small_months += 1
            continue
        month_decisions = [
            d
            for d in decisions
            if (d.market_date.year, d.market_date.month) == (start.year, start.month)
        ]
        values: dict[str, Decimal] = {}
        for decision in month_decisions:
            value = _value_nzd(valuer, decision)
            if value is None:
                unpriced_decisions += 1
            else:
                values[decision.id] = value
        bought = sum(
            (values.get(d.id, Decimal(0)) for d in month_decisions if d.side == Side.BUY),
            Decimal(0),
        )
        sold = sum(
            (values.get(d.id, Decimal(0)) for d in month_decisions if d.side == Side.SELL),
            Decimal(0),
        )
        turnover = float((bought + sold) / 2 / start_value)
        months.append(_Month(start, turnover, month_decisions, values))

    notes = _notes(history, small_months, unpriced_decisions)
    decision_count = sum(len(m.decisions) for m in months)
    if len(months) < MIN_MONTHS or decision_count < MIN_DECISIONS:
        return _insufficient(decision_count, len(months), notes)

    average = sum(m.turnover for m in months) / len(months)
    detected = average > THRESHOLD_MONTHLY_TURNOVER
    return Finding(
        pattern=PATTERN,
        title=TITLE,
        result="detected" if detected else "not_detected",
        confidence=confidence_level(len(months) / MIN_MONTHS, decision_count / MIN_DECISIONS),
        sample=FindingSample(decisions=decision_count, cases=len(months)),
        metrics={
            "avg_monthly_turnover_pct": round(average * 100, 2),
            "annualised_turnover_pct": round(average * 1200, 2),
            "months": float(len(months)),
        },
        threshold=_THRESHOLD_TEXT,
        evidence=_evidence(months),
        notes=notes,
    )


def _portfolio_value(history: EnrichedHistory, valuer: Valuer, month_start: date) -> Decimal | None:
    """Value of everything held at the start of the month, in NZD. None if there was nothing."""
    ledger = Ledger.from_trades(
        history.trades, as_of=datetime(month_start.year, month_start.month, 1, tzinfo=UTC)
    )
    positions = ledger.positions()
    if not positions:
        return None
    before = day_before(month_start)
    total = Decimal(0)
    for (market, symbol), position in positions.items():
        key = instrument_key(market, symbol)
        price = valuer.price(key, before)
        rate = valuer.nzd_rate(valuer.currency(key), before)
        if price is not None and rate is not None:
            total += position.quantity * price * rate
    return total


def _value_nzd(valuer: Valuer, decision: Decision) -> Decimal | None:
    key = instrument_key(decision.market, decision.symbol)
    rate = valuer.nzd_rate(valuer.currency(key), decision.market_date)
    return None if rate is None else decision.quantity * decision.avg_price * rate


def _evidence(months: list[_Month]) -> list[Evidence]:
    busiest = sorted(months, key=lambda m: m.turnover, reverse=True)[:EVIDENCE_MONTHS]
    evidence: list[Evidence] = []
    for month in busiest:
        buys = sum(1 for d in month.decisions if d.side == Side.BUY)
        sells = len(month.decisions) - buys
        evidence.append(
            Evidence(
                decision_id=None,
                note=(
                    f"{month.start:%B %Y}: {month.turnover:.1%} of the portfolio traded "
                    f"({buys} buys, {sells} sells)"
                ),
            )
        )
        largest = sorted(
            month.decisions, key=lambda d: month.values.get(d.id, Decimal(0)), reverse=True
        )[:EVIDENCE_DECISIONS_PER_MONTH]
        for decision in largest:
            verb = "Bought" if decision.side == Side.BUY else "Sold"
            key = instrument_key(decision.market, decision.symbol)
            evidence.append(
                Evidence(
                    decision_id=decision.id,
                    note=f"{verb} {key} on {decision.market_date}",
                )
            )
    return evidence


def _notes(history: EnrichedHistory, small_months: int, unpriced_decisions: int) -> list[str]:
    notes: list[str] = []
    if small_months:
        notes.append(
            f"{small_months} months were left out because the portfolio was worth under NZ$500 at "
            "the start of the month. Small amounts make the percentages jump."
        )
    if unpriced_decisions:
        notes.append(
            f"{unpriced_decisions} decisions were left out because there was no exchange rate to "
            "NZD."
        )
    if history.missing_prices:
        notes.append(
            "Shares without market prices are valued at your last trade price when working out "
            "the portfolio value."
        )
    return notes


def _insufficient(decisions: int, months: int, notes: list[str]) -> Finding:
    return Finding(
        pattern=PATTERN,
        title=TITLE,
        result="insufficient_data",
        confidence=None,
        sample=FindingSample(decisions=decisions, cases=months),
        metrics={},
        threshold=_THRESHOLD_TEXT,
        evidence=[],
        notes=[
            *notes,
            f"Needs at least {MIN_MONTHS} months with a portfolio and {MIN_DECISIONS} decisions.",
        ],
    )
