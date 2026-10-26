"""Disposition effect (spec section 5.2): selling winners sooner than losers.

Method from Odean (1998). On every day the investor sells something, look at each share they
held at the start of that day:
- sold at a price above the average cost: a realised gain
- sold below the average cost: a realised loss
- not sold, with the day's close above the average cost: a paper gain
- not sold, close below the average cost: a paper loss

Proportion of gains realised (PGR) = realised gains / (realised gains + paper gains).
Proportion of losses realised (PLR) = realised losses / (realised losses + paper losses).
The effect shows as PGR > PLR.

Limits:
- A paper gain or loss is counted again on every sell day, so observations are not independent
  and the p-value is more optimistic than it looks. Odean's test has the same limit.
- Shares without market prices are left out completely. Counting their sales but not their
  paper gains would bias the result.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from trademind.analysis.common import Valuer, confidence_level, has_market_prices, user_decisions
from trademind.analysis.stats import two_proportion_p_value
from trademind.core.holdings import Ledger
from trademind.core.markets import instrument_key, market_date
from trademind.core.models import (
    Decision,
    EnrichedHistory,
    Evidence,
    Finding,
    FindingSample,
    Side,
    Trade,
)

PATTERN = "disposition_effect"
TITLE = "Selling winners sooner than losers"
MIN_SELL_DECISIONS = 10
MIN_CASES_EACH_SIDE = 5
SIGNIFICANCE = 0.05
EVIDENCE_EACH_SIDE = 5

_THRESHOLD_TEXT = "Share of gains sold above share of losses sold, with p below 0.05"


@dataclass
class _Sale:
    decision: Decision
    change: Decimal  # price / average cost - 1


def detect(history: EnrichedHistory) -> Finding:
    valuer = Valuer(history)
    sells = [
        d
        for d in user_decisions(history, Side.SELL)
        if has_market_prices(history, instrument_key(d.market, d.symbol))
    ]
    by_day: dict[date, dict[str, Decision]] = {}
    for decision in sells:
        by_day.setdefault(decision.market_date, {})[
            instrument_key(decision.market, decision.symbol)
        ] = decision

    dated = sorted(
        ((market_date(t.executed_at, t.market), t) for t in history.trades),
        key=lambda item: (item[0], item[1].executed_at, item[1].id),
    )
    ledger = Ledger()
    applied = 0

    realised_gains: list[_Sale] = []
    realised_losses: list[_Sale] = []
    paper_gains = paper_losses = 0

    for day in sorted(by_day):
        applied = _apply_before(ledger, dated, applied, day)
        sold_today = by_day[day]
        for (market, symbol), position in ledger.positions().items():
            key = instrument_key(market, symbol)
            if not has_market_prices(history, key) or position.avg_cost <= 0:
                continue
            sold = sold_today.get(key)
            price = sold.avg_price if sold else valuer.price(key, day)
            if price is None:
                continue
            change = price / position.avg_cost - 1
            if sold is not None:
                if change > 0:
                    realised_gains.append(_Sale(sold, change))
                elif change < 0:
                    realised_losses.append(_Sale(sold, change))
            elif change > 0:
                paper_gains += 1
            elif change < 0:
                paper_losses += 1

    gain_cases = len(realised_gains) + paper_gains
    loss_cases = len(realised_losses) + paper_losses
    sale_count = len(realised_gains) + len(realised_losses)
    notes = _notes(history)
    sample = FindingSample(decisions=sale_count, cases=gain_cases + loss_cases)

    if (
        sale_count < MIN_SELL_DECISIONS
        or gain_cases < MIN_CASES_EACH_SIDE
        or loss_cases < MIN_CASES_EACH_SIDE
    ):
        return Finding(
            pattern=PATTERN,
            title=TITLE,
            result="insufficient_data",
            confidence=None,
            sample=sample,
            metrics={},
            threshold=_THRESHOLD_TEXT,
            evidence=[],
            notes=[
                *notes,
                f"Needs at least {MIN_SELL_DECISIONS} sales, and {MIN_CASES_EACH_SIDE} gains "
                f"and {MIN_CASES_EACH_SIDE} losses to compare.",
            ],
        )

    pgr = len(realised_gains) / gain_cases
    plr = len(realised_losses) / loss_cases
    p_value = two_proportion_p_value(
        len(realised_gains), gain_cases, len(realised_losses), loss_cases
    )
    detected = pgr > plr and p_value is not None and p_value < SIGNIFICANCE

    metrics = {
        "pgr": round(pgr, 4),
        "plr": round(plr, 4),
        "score": round(pgr - plr, 4),
        "realised_gains": float(len(realised_gains)),
        "paper_gains": float(paper_gains),
        "realised_losses": float(len(realised_losses)),
        "paper_losses": float(paper_losses),
    }
    if p_value is not None:
        metrics["p_value"] = round(p_value, 8)

    return Finding(
        pattern=PATTERN,
        title=TITLE,
        result="detected" if detected else "not_detected",
        confidence=confidence_level(
            sale_count / MIN_SELL_DECISIONS,
            gain_cases / MIN_CASES_EACH_SIDE,
            loss_cases / MIN_CASES_EACH_SIDE,
        ),
        sample=sample,
        metrics=metrics,
        threshold=_THRESHOLD_TEXT,
        evidence=_evidence(realised_gains, realised_losses),
        notes=notes,
    )


def _apply_before(ledger: Ledger, dated: list[tuple[date, Trade]], applied: int, day: date) -> int:
    """Apply every trade made on an earlier market date. Returns how many are applied so far."""
    while applied < len(dated) and dated[applied][0] < day:
        ledger.apply(dated[applied][1])
        applied += 1
    return applied


def _evidence(gains: list[_Sale], losses: list[_Sale]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for sales, word in ((gains, "above"), (losses, "below")):
        biggest = sorted(sales, key=lambda s: abs(s.change), reverse=True)[:EVIDENCE_EACH_SIDE]
        for sale in biggest:
            d = sale.decision
            evidence.append(
                Evidence(
                    decision_id=d.id,
                    note=(
                        f"Sold {instrument_key(d.market, d.symbol)} on {d.market_date}, "
                        f"{abs(sale.change):.1%} {word} your average cost"
                    ),
                )
            )
    return evidence


def _notes(history: EnrichedHistory) -> list[str]:
    if not history.missing_prices:
        return []
    return [
        f"{len(history.missing_prices)} shares without market prices were left out: "
        + ", ".join(history.missing_prices)
        + "."
    ]
