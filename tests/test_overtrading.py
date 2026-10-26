"""Overtrading scenarios. The portfolio is 100 shares at 10, worth 1,000, with flat prices."""

from datetime import date

from tests.scenarios import flat, history_of, nzx_trade
from trademind.analysis import overtrading
from trademind.core.models import InitiatedBy, Side, Trade


def _start_position(quantity: str = "100") -> list[Trade]:
    return [nzx_trade(1, date(2023, 1, 2), quantity=quantity)]


def _monthly(
    first: int,
    months: int,
    *,
    sell_and_buy: str = "20",
    initiated_by: InitiatedBy = InitiatedBy.USER,
) -> list[Trade]:
    """From February 2023: sell on the 15th and buy back on the 16th, `months` times."""
    trades: list[Trade] = []
    n = first
    for month in range(2, 2 + months):
        year = 2023 + (month - 1) // 12
        month_in_year = (month - 1) % 12 + 1
        trades.append(
            nzx_trade(
                n,
                date(year, month_in_year, 15),
                side=Side.SELL,
                quantity=sell_and_buy,
                initiated_by=initiated_by,
            )
        )
        trades.append(
            nzx_trade(
                n + 1,
                date(year, month_in_year, 16),
                quantity=sell_and_buy,
                initiated_by=initiated_by,
            )
        )
        n += 2
    return trades


def test_heavy_trading_is_detected() -> None:
    # Each month sells 200 and buys 200 against a 1,000 portfolio: 20% turnover.
    trades = _start_position() + _monthly(2, 8)

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    assert finding.result == "detected"
    assert finding.metrics["avg_monthly_turnover_pct"] == 20.0
    assert finding.metrics["annualised_turnover_pct"] == 240.0
    assert finding.metrics["months"] == 8
    assert finding.sample.cases == 8
    assert finding.sample.decisions == 16
    assert finding.confidence == "low"  # 8 months is under twice the minimum of 6


def test_light_trading_is_not_detected() -> None:
    # One 10-value buy a month against 1,000: about 0.5% turnover.
    trades = _start_position() + [
        nzx_trade(n, date(2023 + (m - 1) // 12, (m - 1) % 12 + 1, 15))
        for n, m in enumerate(range(2, 14), start=2)
    ]

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    assert finding.result == "not_detected"
    assert finding.metrics["avg_monthly_turnover_pct"] < 1
    assert finding.confidence is not None


def test_too_few_months_is_not_enough_data() -> None:
    trades = _start_position() + _monthly(2, 3)

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    assert finding.result == "insufficient_data"
    assert finding.confidence is None
    assert finding.metrics == {}
    assert finding.sample.cases == 3


def test_no_decisions_is_not_enough_data() -> None:
    finding = overtrading.detect(history_of([], {}))

    assert finding.result == "insufficient_data"


def test_small_portfolios_are_left_out_with_a_note() -> None:
    # 10 shares at 10 is worth 100, under the NZ$500 minimum.
    trades = _start_position("10") + _monthly(2, 8, sell_and_buy="5")

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    assert finding.result == "insufficient_data"
    assert any("NZ$500" in note for note in finding.notes)


def test_platform_trades_are_not_the_investors_decisions() -> None:
    trades = _start_position() + _monthly(2, 8, initiated_by=InitiatedBy.PLATFORM)

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    assert finding.result == "insufficient_data"
    assert finding.sample.decisions == 0


def test_platform_trades_still_count_towards_the_portfolio() -> None:
    # The investor trades heavily. A platform purchase before that makes the portfolio bigger,
    # so the same trades are a smaller share of it.
    investor = _monthly(3, 8)
    small = _start_position("100") + investor
    large = [
        *_start_position("100"),
        nzx_trade(2, date(2023, 1, 3), quantity="100", initiated_by=InitiatedBy.PLATFORM),
        *investor,
    ]

    small_finding = overtrading.detect(history_of(small, {"NZX:AAA": flat()}))
    large_finding = overtrading.detect(history_of(large, {"NZX:AAA": flat()}))

    assert small_finding.metrics["avg_monthly_turnover_pct"] == 20.0
    assert large_finding.metrics["avg_monthly_turnover_pct"] == 10.0


def test_evidence_names_the_busiest_months() -> None:
    trades = _start_position() + _monthly(2, 8)

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    months = [e for e in finding.evidence if e.decision_id is None]
    decisions = [e for e in finding.evidence if e.decision_id is not None]
    assert len(months) == 3
    assert "20.0% of the portfolio traded (1 buys, 1 sells)" in months[0].note
    assert decisions
    assert all(e.note.startswith(("Bought NZX:AAA", "Sold NZX:AAA")) for e in decisions)


def test_shares_without_market_prices_add_a_note_and_use_the_last_trade_price() -> None:
    trades = _start_position() + _monthly(2, 8)

    finding = overtrading.detect(history_of(trades, {}, unpriced=["NZX:AAA"]))

    assert finding.result == "detected"
    assert any("last trade price" in note for note in finding.notes)


def test_twice_the_minimum_is_medium_confidence() -> None:
    trades = _start_position() + _monthly(2, 12)

    finding = overtrading.detect(history_of(trades, {"NZX:AAA": flat()}))

    assert finding.confidence == "medium"
