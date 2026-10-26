"""Buying after a run-up (spec section 5.3): does the investor buy right after a sharp rise?

For each of the investor's own buys, take the share's return over the 20 trading days up to the
day before the buy. Compare it with every 20-day return for that share in the year before. If it
is in the top 10%, the buy is a "run-up buy". By chance alone about 10% of buys would be. A
binomial test checks whether the investor has more than that.

Limits:
- Buys of the same share close together share the same history, so they are not independent.
- Shares without market prices are left out, because they have no price history to compare.
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from trademind.analysis.common import confidence_level, has_market_prices, user_decisions
from trademind.analysis.stats import binomial_upper_tail
from trademind.core.markets import instrument_key
from trademind.core.models import (
    Decision,
    EnrichedHistory,
    Evidence,
    Finding,
    FindingSample,
    Side,
)

PATTERN = "run_up_buying"
TITLE = "Buying after a sharp rise"
WINDOW_TRADING_DAYS = 20
BASELINE_DAYS = 365
MIN_BASELINE_RETURNS = 200  # about 80% of a trading year
TOP_SHARE = 0.10
MIN_BUY_DECISIONS = 15
SIGNIFICANCE = 0.05
EVIDENCE_LIMIT = 10

_THRESHOLD_TEXT = "Share of buys after a top-10% rise above 10%, with p below 0.05"


@dataclass
class _Buy:
    decision: Decision
    rise: Decimal
    is_run_up: bool


def detect(history: EnrichedHistory) -> Finding:
    series = {
        key: (sorted(s.closes), [s.closes[day] for day in sorted(s.closes)])
        for key, s in history.prices.items()
        if s.source == "market"
    }

    buys: list[_Buy] = []
    for decision in user_decisions(history, Side.BUY):
        key = instrument_key(decision.market, decision.symbol)
        if not has_market_prices(history, key):
            continue
        dates, values = series[key]
        buy = _assess(decision, dates, values)
        if buy is not None:
            buys.append(buy)

    notes = _notes(history)
    if len(buys) < MIN_BUY_DECISIONS:
        return Finding(
            pattern=PATTERN,
            title=TITLE,
            result="insufficient_data",
            confidence=None,
            sample=FindingSample(decisions=len(buys), cases=len(buys)),
            metrics={},
            threshold=_THRESHOLD_TEXT,
            evidence=[],
            notes=[
                *notes,
                f"Needs at least {MIN_BUY_DECISIONS} buys with a full year of earlier prices.",
            ],
        )

    run_ups = [b for b in buys if b.is_run_up]
    share = len(run_ups) / len(buys)
    p_value = binomial_upper_tail(len(run_ups), len(buys), TOP_SHARE)
    detected = share > TOP_SHARE and p_value < SIGNIFICANCE

    return Finding(
        pattern=PATTERN,
        title=TITLE,
        result="detected" if detected else "not_detected",
        confidence=confidence_level(len(buys) / MIN_BUY_DECISIONS),
        sample=FindingSample(decisions=len(buys), cases=len(buys)),
        metrics={
            "run_up_share": round(share, 4),
            "expected_share": TOP_SHARE,
            "run_up_buys": float(len(run_ups)),
            "p_value": round(p_value, 8),
        },
        threshold=_THRESHOLD_TEXT,
        evidence=_evidence(run_ups),
        notes=notes,
    )


def _assess(decision: Decision, dates: list[date], values: list[Decimal]) -> _Buy | None:
    """None if there is not a full year of earlier prices to compare with."""
    last_before = bisect_left(dates, decision.market_date) - 1  # last close before the buy day
    if last_before < WINDOW_TRADING_DAYS:
        return None
    rise = values[last_before] / values[last_before - WINDOW_TRADING_DAYS] - 1

    oldest = decision.market_date - timedelta(days=BASELINE_DAYS)
    first_end = max(bisect_left(dates, oldest), WINDOW_TRADING_DAYS)
    baseline = [
        values[end] / values[end - WINDOW_TRADING_DAYS] - 1
        for end in range(first_end, last_before + 1)
    ]
    if len(baseline) < MIN_BASELINE_RETURNS:
        return None

    at_least_as_big = sum(1 for r in baseline if r >= rise)
    return _Buy(decision, rise, at_least_as_big / len(baseline) <= TOP_SHARE)


def _evidence(run_ups: list[_Buy]) -> list[Evidence]:
    biggest = sorted(run_ups, key=lambda b: b.rise, reverse=True)[:EVIDENCE_LIMIT]
    return [
        Evidence(
            decision_id=b.decision.id,
            note=(
                f"Bought {instrument_key(b.decision.market, b.decision.symbol)} on "
                f"{b.decision.market_date}, after it rose {b.rise:.1%} in the 20 trading days "
                "before"
            ),
        )
        for b in biggest
    ]


def _notes(history: EnrichedHistory) -> list[str]:
    if not history.missing_prices:
        return []
    return [
        f"{len(history.missing_prices)} shares without market prices were left out: "
        + ", ".join(history.missing_prices)
        + "."
    ]
