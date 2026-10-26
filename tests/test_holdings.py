from datetime import UTC, datetime
from decimal import Decimal

from tests.helpers import make_trade
from trademind.core.holdings import Ledger
from trademind.core.models import Side


def test_buy_adds_shares_and_cost_including_fee() -> None:
    ledger = Ledger.from_trades([make_trade(1, quantity="10", price="2.00", fee="1")])

    position = ledger.position("ASX", "AAA")

    assert position.quantity == Decimal("10")
    assert position.cost == Decimal("21")
    assert position.avg_cost == Decimal("2.1")


def test_second_buy_averages_the_cost() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, "2024-01-01T00:00:00", quantity="10", price="2.00"),
            make_trade(2, "2024-01-02T00:00:00", quantity="10", price="4.00"),
        ]
    )

    assert ledger.position("ASX", "AAA").avg_cost == Decimal("3")


def test_sell_removes_shares_at_average_cost() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, "2024-01-01T00:00:00", quantity="10", price="2.00"),
            make_trade(2, "2024-01-02T00:00:00", quantity="10", price="4.00"),
            make_trade(3, "2024-01-03T00:00:00", side=Side.SELL, quantity="5", price="9.00"),
        ]
    )

    position = ledger.position("ASX", "AAA")

    assert position.quantity == Decimal("15")
    assert position.avg_cost == Decimal("3")


def test_transfer_out_removes_shares_without_a_sale() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, "2024-01-01T00:00:00", quantity="10", price="2.00"),
            make_trade(2, "2024-01-02T00:00:00", side=Side.TRANSFER_OUT, quantity="4"),
        ]
    )

    position = ledger.position("ASX", "AAA")

    assert position.quantity == Decimal("6")
    assert position.avg_cost == Decimal("2")


def test_selling_everything_closes_the_position() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, "2024-01-01T00:00:00", quantity="10"),
            make_trade(2, "2024-01-02T00:00:00", side=Side.SELL, quantity="10"),
        ]
    )

    assert ledger.positions() == {}
    assert ledger.position("ASX", "AAA").avg_cost == Decimal(0)
    assert ledger.warnings == []


def test_same_symbol_on_two_markets_is_two_positions() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, market="ASX", quantity="3"),
            make_trade(2, market="NZX", quantity="5"),
        ]
    )

    assert ledger.position("ASX", "AAA").quantity == Decimal("3")
    assert ledger.position("NZX", "AAA").quantity == Decimal("5")


def test_selling_more_than_held_clamps_to_zero_and_warns() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, "2024-01-01T00:00:00", quantity="5"),
            make_trade(2, "2024-01-02T00:00:00", side=Side.SELL, quantity="8"),
        ]
    )

    assert ledger.position("ASX", "AAA").quantity == Decimal(0)
    assert len(ledger.warnings) == 1
    assert "ASX:AAA" in ledger.warnings[0]


def test_tiny_rounding_difference_does_not_warn() -> None:
    ledger = Ledger.from_trades(
        [
            make_trade(1, "2024-01-01T00:00:00", quantity="1.0000000"),
            make_trade(2, "2024-01-02T00:00:00", side=Side.SELL, quantity="1.0000001"),
        ]
    )

    assert ledger.warnings == []


def test_as_of_stops_at_the_given_time() -> None:
    trades = [
        make_trade(1, "2024-01-01T00:00:00", quantity="10"),
        make_trade(2, "2024-02-01T00:00:00", quantity="10"),
    ]

    ledger = Ledger.from_trades(trades, as_of=datetime(2024, 1, 15, tzinfo=UTC))

    assert ledger.position("ASX", "AAA").quantity == Decimal("10")


def test_unsorted_input_is_applied_in_time_order() -> None:
    trades = [
        make_trade(2, "2024-01-02T00:00:00", side=Side.SELL, quantity="5"),
        make_trade(1, "2024-01-01T00:00:00", quantity="10"),
    ]

    ledger = Ledger.from_trades(trades)

    assert ledger.position("ASX", "AAA").quantity == Decimal("5")
    assert ledger.warnings == []
