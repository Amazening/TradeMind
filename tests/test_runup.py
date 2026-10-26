"""Run-up scenarios.

The price is 10 every day except for a one-day jump to 13 every 30 days. So 20-day returns are 0
almost always, +30% on each jump day, and -23% 20 days after. A jump is in the top 10% of 20-day
returns for the year, because only about 1 window in 30 has it.
"""

from datetime import date, timedelta

from tests.scenarios import START, flat, history_of, nzx_trade
from trademind.analysis import runup
from trademind.core.models import InitiatedBy, Trade

EVERY = 30
OFFSET = 10


def _jump_days() -> list[date]:
    return [START + timedelta(days=OFFSET + EVERY * k) for k in range(33)]


def _buys(
    days_after_jump: int, count: int, initiated_by: InitiatedBy = InitiatedBy.USER
) -> list[Trade]:
    """Buys `days_after_jump` days after a jump, only for jumps in 2023 and later, so each buy
    has a full year of earlier prices."""
    jumps = [d for d in _jump_days() if d >= date(2023, 2, 1)][:count]
    return [
        nzx_trade(n, jump + timedelta(days=days_after_jump), initiated_by=initiated_by)
        for n, jump in enumerate(jumps, start=1)
    ]


def test_buying_the_day_after_each_jump_is_detected() -> None:
    from tests.scenarios import spiky

    finding = runup.detect(history_of(_buys(1, 20), {"NZX:AAA": spiky()}))

    assert finding.result == "detected"
    assert finding.metrics["run_up_buys"] == 20
    assert finding.metrics["run_up_share"] == 1.0
    assert finding.metrics["expected_share"] == 0.1
    assert finding.metrics["p_value"] < 0.05
    assert finding.sample.decisions == 20
    assert finding.confidence == "low"  # 20 buys is under twice the minimum of 15


def test_buying_on_quiet_days_is_not_detected() -> None:
    from tests.scenarios import spiky

    finding = runup.detect(history_of(_buys(10, 20), {"NZX:AAA": spiky()}))

    assert finding.result == "not_detected"
    assert finding.metrics["run_up_buys"] == 0
    assert finding.evidence == []


def test_few_buys_is_not_enough_data() -> None:
    from tests.scenarios import spiky

    finding = runup.detect(history_of(_buys(1, 5), {"NZX:AAA": spiky()}))

    assert finding.result == "insufficient_data"
    assert finding.confidence is None
    assert finding.sample.decisions == 5


def test_buys_without_a_full_year_of_prices_are_not_counted() -> None:
    from tests.scenarios import spiky

    # The first jumps are in the first months of the price history, so there is no year before.
    early = [nzx_trade(n, d + timedelta(days=1)) for n, d in enumerate(_jump_days()[:6], start=1)]

    finding = runup.detect(history_of(early, {"NZX:AAA": spiky()}))

    assert finding.sample.decisions == 0


def test_platform_buys_are_not_the_investors_decisions() -> None:
    from tests.scenarios import spiky

    finding = runup.detect(history_of(_buys(1, 20, InitiatedBy.PLATFORM), {"NZX:AAA": spiky()}))

    assert finding.result == "insufficient_data"
    assert finding.sample.decisions == 0


def test_shares_without_market_prices_are_left_out_with_a_note() -> None:
    finding = runup.detect(history_of(_buys(1, 20), {}, unpriced=["NZX:AAA"]))

    assert finding.result == "insufficient_data"
    assert any("NZX:AAA" in note for note in finding.notes)


def test_a_flat_price_never_counts_as_a_run_up() -> None:
    # Every 20-day return is 0, so a return of 0 is not in the top 10%.
    buys = [nzx_trade(n, date(2023, 2, 1) + timedelta(days=n * 5)) for n in range(1, 21)]

    finding = runup.detect(history_of(buys, {"NZX:AAA": flat()}))

    assert finding.metrics["run_up_buys"] == 0


def test_evidence_describes_the_rise_before_each_run_up_buy() -> None:
    from tests.scenarios import spiky

    finding = runup.detect(history_of(_buys(1, 20), {"NZX:AAA": spiky()}))

    assert len(finding.evidence) == 10
    assert all("rose 30.0% in the 20 trading days before" in e.note for e in finding.evidence)
    assert all(e.decision_id for e in finding.evidence)
