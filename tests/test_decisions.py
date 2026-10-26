from datetime import date
from decimal import Decimal

import pytest

from tests.helpers import make_trade
from trademind.core.decisions import group_into_decisions
from trademind.core.errors import UnknownMarketError
from trademind.core.markets import market_date
from trademind.core.models import InitiatedBy, Side


def test_split_fills_of_one_order_are_one_decision() -> None:
    trades = [
        make_trade(1, "2024-03-04T02:00:00", quantity="4", price="2.00"),
        make_trade(2, "2024-03-04T02:00:05", quantity="6", price="2.50"),
    ]

    [decision] = group_into_decisions(trades)

    assert decision.trade_ids == ["row-1", "row-2"]
    assert decision.quantity == Decimal("10")
    # (4 x 2.00 + 6 x 2.50) / 10
    assert decision.avg_price == Decimal("2.3")
    assert decision.side == Side.BUY
    assert decision.market_date == date(2024, 3, 4)


def test_different_days_are_different_decisions() -> None:
    trades = [
        make_trade(1, "2024-03-04T02:00:00"),
        make_trade(2, "2024-03-05T02:00:00"),
    ]

    assert len(group_into_decisions(trades)) == 2


def test_different_side_share_or_market_are_different_decisions() -> None:
    trades = [
        make_trade(1, side=Side.BUY),
        make_trade(2, side=Side.SELL),
        make_trade(3, symbol="BBB"),
        make_trade(4, market="NZX"),
    ]

    assert len(group_into_decisions(trades)) == 4


def test_platform_and_user_trades_are_never_merged() -> None:
    trades = [
        make_trade(1, initiated_by=InitiatedBy.USER),
        make_trade(2, initiated_by=InitiatedBy.PLATFORM),
    ]

    decisions = group_into_decisions(trades)

    assert {d.initiated_by for d in decisions} == {InitiatedBy.USER, InitiatedBy.PLATFORM}
    assert len(decisions) == 2


def test_transfers_out_are_not_decisions() -> None:
    trades = [make_trade(1), make_trade(2, side=Side.TRANSFER_OUT)]

    [decision] = group_into_decisions(trades)

    assert decision.trade_ids == ["row-1"]


def test_ids_are_numbered_in_time_order() -> None:
    trades = [
        make_trade(1, "2024-03-06T02:00:00"),
        make_trade(2, "2024-03-04T02:00:00"),
    ]

    decisions = group_into_decisions(trades)

    assert [(d.id, d.trade_ids) for d in decisions] == [("d-1", ["row-2"]), ("d-2", ["row-1"])]


def test_late_utc_trade_is_the_next_day_in_sydney() -> None:
    # 23:30 UTC on 4 March is 10:30 on 5 March in Sydney (daylight saving).
    trades = [make_trade(1, "2024-03-04T23:30:00", market="ASX")]

    [decision] = group_into_decisions(trades)

    assert decision.market_date == date(2024, 3, 5)


def test_early_utc_trade_is_the_previous_day_in_new_york() -> None:
    trades = [make_trade(1, "2024-03-05T01:00:00", market="NYSE")]

    [decision] = group_into_decisions(trades)

    assert decision.market_date == date(2024, 3, 4)


def test_fills_either_side_of_a_local_midnight_are_separate_decisions() -> None:
    # Same UTC date, but Sydney midnight falls between them.
    trades = [
        make_trade(1, "2024-03-04T12:00:00", market="ASX"),
        make_trade(2, "2024-03-04T14:00:00", market="ASX"),
    ]

    assert len(group_into_decisions(trades)) == 2


def test_unknown_market_raises() -> None:
    with pytest.raises(UnknownMarketError):
        market_date(make_trade().executed_at, "LSE")
