"""Disposition scenarios.

Every share is bought at 10 on 2 January 2023. "Winners" trade at 15 (up 50%) and "losers" at 6
(down 40%), with flat prices, so every paper and realised result can be counted by hand.
"""

from datetime import date, timedelta
from decimal import Decimal

from tests.scenarios import flat, history_of, nzx_trade
from trademind.analysis import disposition
from trademind.core.models import EnrichedHistory, InitiatedBy, Side, Trade

BOUGHT = date(2023, 1, 2)
FIRST_SALE = date(2023, 3, 1)


def _history(
    winners_sold: int,
    losers_unsold: int,
    losers_sold: int = 0,
    winners_unsold: int = 0,
    unpriced: tuple[str, ...] = (),
    seller: InitiatedBy = InitiatedBy.USER,
) -> EnrichedHistory:
    """Winners W1.. are each sold on their own day. Losers L1.. are sold on the same days
    (for the first `losers_sold` of them) or never. Extra winners X1.. are never sold."""
    trades: list[Trade] = []
    closes: dict[str, dict[date, Decimal]] = {}
    n = 1

    def add(symbol: str, price: str, sale_day: date | None) -> None:
        nonlocal n
        trades.append(nzx_trade(n, BOUGHT, symbol=symbol, quantity="10", price="10"))
        n += 1
        if sale_day is not None:
            trades.append(
                nzx_trade(
                    n,
                    sale_day,
                    symbol=symbol,
                    side=Side.SELL,
                    quantity="10",
                    price=price,
                    initiated_by=seller,
                )
            )
            n += 1
        closes[f"NZX:{symbol}"] = flat(price)

    for i in range(1, winners_sold + 1):
        add(f"W{i}", "15", FIRST_SALE + timedelta(days=i))
    for k in range(1, winners_unsold + 1):
        add(f"X{k}", "15", None)
    for j in range(1, losers_sold + losers_unsold + 1):
        sold_on = FIRST_SALE + timedelta(days=j) if j <= losers_sold else None
        add(f"L{j}", "6", sold_on)

    skipped = [key for key in closes if key.split(":")[1] in unpriced]
    for key in skipped:
        del closes[key]
    return history_of(trades, closes, unpriced=skipped)


def test_selling_winners_and_holding_losers_is_detected() -> None:
    # 12 winners sold one a day, 5 losers never sold.
    # Realised gains 12, paper gains 66 (12+... counted daily), paper losses 60.
    finding = disposition.detect(_history(winners_sold=12, losers_unsold=5))

    assert finding.result == "detected"
    assert finding.metrics["realised_gains"] == 12
    assert finding.metrics["paper_gains"] == 66
    assert finding.metrics["realised_losses"] == 0
    assert finding.metrics["paper_losses"] == 60
    assert finding.metrics["pgr"] == round(12 / 78, 4)
    assert finding.metrics["plr"] == 0
    assert finding.metrics["p_value"] < 0.05
    assert finding.sample.decisions == 12
    assert finding.sample.cases == 138


def test_selling_both_equally_is_not_detected() -> None:
    # Each day one winner and one loser are sold, so the two proportions are the same.
    finding = disposition.detect(_history(winners_sold=12, losers_unsold=0, losers_sold=12))

    assert finding.result == "not_detected"
    assert finding.metrics["pgr"] == finding.metrics["plr"]
    assert finding.metrics["score"] == 0
    assert finding.metrics["p_value"] == 0.5


def test_selling_losers_sooner_than_winners_is_not_detected() -> None:
    # 12 losers are sold, but only 5 of the 25 winners. PLR is above PGR.
    finding = disposition.detect(
        _history(winners_sold=5, winners_unsold=20, losers_unsold=0, losers_sold=12)
    )

    assert finding.result == "not_detected"
    assert finding.metrics["score"] < 0
    assert finding.metrics["plr"] > finding.metrics["pgr"]


def test_few_sales_is_not_enough_data() -> None:
    finding = disposition.detect(_history(winners_sold=3, losers_unsold=5))

    assert finding.result == "insufficient_data"
    assert finding.confidence is None
    assert finding.sample.decisions == 3


def test_needs_losses_to_compare() -> None:
    finding = disposition.detect(_history(winners_sold=12, losers_unsold=0))

    assert finding.result == "insufficient_data"


def test_platform_sales_are_not_the_investors_decisions() -> None:
    finding = disposition.detect(
        _history(winners_sold=12, losers_unsold=5, seller=InitiatedBy.PLATFORM)
    )

    assert finding.result == "insufficient_data"
    assert finding.sample.decisions == 0


def test_shares_without_market_prices_are_left_out_completely() -> None:
    # Three of the 14 sold winners have no market prices. Their sales are not counted, and the
    # note names them.
    finding = disposition.detect(
        _history(winners_sold=14, losers_unsold=5, unpriced=("W1", "W2", "W3"))
    )

    assert finding.metrics["realised_gains"] == 11
    assert any("NZX:W1" in note and "NZX:W3" in note for note in finding.notes)


def test_a_share_bought_the_same_day_it_is_sold_is_not_counted() -> None:
    trades = [
        nzx_trade(1, date(2023, 3, 1), symbol="X", quantity="10", price="10"),
        nzx_trade(2, date(2023, 3, 1), symbol="X", side=Side.SELL, quantity="10", price="15"),
    ]

    finding = disposition.detect(history_of(trades, {"NZX:X": flat("15")}))

    assert finding.sample.decisions == 0


def test_a_sale_at_the_average_cost_is_neither_a_gain_nor_a_loss() -> None:
    trades = [
        nzx_trade(1, BOUGHT, symbol="X", quantity="10", price="10"),
        nzx_trade(2, FIRST_SALE, symbol="X", side=Side.SELL, quantity="10", price="10"),
    ]

    finding = disposition.detect(history_of(trades, {"NZX:X": flat("10")}))

    assert finding.sample.decisions == 0
    assert finding.sample.cases == 0


def test_average_cost_includes_every_earlier_buy() -> None:
    # Bought at 10 then at 20: average cost 15. Selling at 16 is a gain, not a loss.
    trades = [
        nzx_trade(1, BOUGHT, symbol="X", quantity="10", price="10"),
        nzx_trade(2, BOUGHT + timedelta(days=1), symbol="X", quantity="10", price="20"),
        nzx_trade(3, FIRST_SALE, symbol="X", side=Side.SELL, quantity="20", price="16"),
    ]

    finding = disposition.detect(history_of(trades, {"NZX:X": flat("16")}))

    assert finding.sample.decisions == 1
    assert finding.metrics == {}  # too few to compare, but counted
    assert finding.sample.cases == 1


def test_evidence_lists_gains_above_and_losses_below_the_average_cost() -> None:
    finding = disposition.detect(_history(winners_sold=12, losers_unsold=0, losers_sold=12))

    notes = [e.note for e in finding.evidence]
    assert any("50.0% above your average cost" in note for note in notes)
    assert any("40.0% below your average cost" in note for note in notes)
    assert len(notes) <= 10
