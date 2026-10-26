from datetime import date
from decimal import Decimal

from tests.helpers import make_trade
from trademind.core.models import Split
from trademind.core.prices import PriceLookup
from trademind.core.splits import adjust_for_splits, count_adjusted, split_label

CONSOLIDATION = Split(date=date(2024, 6, 1), numerator=Decimal(1), denominator=Decimal(25))
FORWARD = Split(date=date(2024, 6, 1), numerator=Decimal(2), denominator=Decimal(1))


def test_consolidation_shrinks_quantity_and_raises_price() -> None:
    trade = make_trade(1, "2024-05-01T02:00:00", quantity="1000", price="0.40")

    [adjusted] = adjust_for_splits([trade], {"ASX:AAA": [CONSOLIDATION]})

    assert adjusted.quantity == Decimal("40")
    assert adjusted.price == Decimal("10")


def test_forward_split_raises_quantity_and_lowers_price() -> None:
    trade = make_trade(1, "2024-05-01T02:00:00", quantity="10", price="8.00")

    [adjusted] = adjust_for_splits([trade], {"ASX:AAA": [FORWARD]})

    assert adjusted.quantity == Decimal("20")
    assert adjusted.price == Decimal("4")


def test_value_of_the_trade_does_not_change() -> None:
    trade = make_trade(1, "2024-05-01T02:00:00", quantity="7", price="3.00")
    seven_to_one = Split(date=date(2024, 6, 1), numerator=Decimal(1), denominator=Decimal(7))

    [adjusted] = adjust_for_splits([trade], {"ASX:AAA": [seven_to_one]})

    assert adjusted.quantity == Decimal("1")
    assert adjusted.quantity * adjusted.price == trade.quantity * trade.price


def test_trade_on_or_after_the_split_date_is_unchanged() -> None:
    on_day = make_trade(1, "2024-06-01T02:00:00")
    after = make_trade(2, "2024-07-01T02:00:00")

    assert adjust_for_splits([on_day, after], {"ASX:AAA": [CONSOLIDATION]}) == [on_day, after]


def test_only_the_split_instrument_is_adjusted() -> None:
    other = make_trade(1, "2024-05-01T02:00:00", symbol="BBB")

    assert adjust_for_splits([other], {"ASX:AAA": [CONSOLIDATION]}) == [other]


def test_two_splits_stack() -> None:
    later = Split(date=date(2024, 9, 1), numerator=Decimal(2), denominator=Decimal(1))
    trade = make_trade(1, "2024-05-01T02:00:00", quantity="100", price="1.00")

    [adjusted] = adjust_for_splits([trade], {"ASX:AAA": [CONSOLIDATION, later]})

    assert adjusted.quantity == Decimal("8")
    assert adjusted.price == Decimal("12.5")


def test_fee_is_not_rescaled() -> None:
    trade = make_trade(1, "2024-05-01T02:00:00", fee="3")

    [adjusted] = adjust_for_splits([trade], {"ASX:AAA": [CONSOLIDATION]})

    assert adjusted.fee == Decimal(3)


def test_split_label_and_count() -> None:
    trades = [make_trade(1, "2024-05-01T02:00:00"), make_trade(2, "2024-07-01T02:00:00")]

    assert split_label(CONSOLIDATION) == "1:25"
    assert split_label(FORWARD) == "2:1"
    assert count_adjusted(trades, "ASX:AAA", CONSOLIDATION) == 1


def test_lookup_returns_exact_day() -> None:
    lookup = PriceLookup({date(2024, 3, 4): Decimal("5")})

    assert lookup.on_or_before(date(2024, 3, 4)) == Decimal("5")


def test_lookup_falls_back_over_a_weekend() -> None:
    lookup = PriceLookup({date(2024, 3, 1): Decimal("5")})  # a Friday

    assert lookup.on_or_before(date(2024, 3, 3)) == Decimal("5")


def test_lookup_gives_up_after_the_gap_limit() -> None:
    lookup = PriceLookup({date(2024, 3, 1): Decimal("5")}, max_gap_days=7)

    assert lookup.on_or_before(date(2024, 3, 8)) == Decimal("5")
    assert lookup.on_or_before(date(2024, 3, 9)) is None


def test_lookup_before_the_first_price_is_none() -> None:
    lookup = PriceLookup({date(2024, 3, 4): Decimal("5")})

    assert lookup.on_or_before(date(2024, 3, 1)) is None


def test_lookup_picks_the_latest_close_not_after_the_day() -> None:
    lookup = PriceLookup({date(2024, 3, 1): Decimal("1"), date(2024, 3, 4): Decimal("2")})

    assert lookup.on_or_before(date(2024, 3, 5)) == Decimal("2")
