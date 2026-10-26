from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.helpers import SHARESIES_HEADER, sharesies_csv, sharesies_row
from trademind.core.errors import NoTradesError, UnrecognisedBrokerError
from trademind.core.models import ImportResult, InitiatedBy, Side
from trademind.ingestion import import_csv


def test_reads_a_buy() -> None:
    result = import_csv(sharesies_csv(sharesies_row()))

    assert result.broker == "sharesies"
    assert result.skipped_rows == []
    [trade] = result.trades
    assert trade.id == "row-2"
    assert trade.source_id == "T1"
    assert trade.executed_at == datetime(2024, 3, 4, 2, 15, 30, 123456, tzinfo=UTC)
    assert trade.market == "ASX"
    assert trade.symbol == "AAA"
    assert trade.name == "Example Corp"
    assert trade.side == Side.BUY
    assert trade.quantity == Decimal("10")
    assert trade.price == Decimal("2.50")
    assert trade.currency == "AUD"
    assert trade.fee == Decimal("0.12")
    assert trade.initiated_by == InitiatedBy.USER


def test_quantity_and_price_keep_full_precision() -> None:
    row = sharesies_row(quantity="0.25000000", price="12.340")

    [trade] = import_csv(sharesies_csv(row)).trades

    assert trade.quantity == Decimal("0.25000000")
    assert trade.price == Decimal("12.340")


def test_reads_dates_without_fractional_seconds() -> None:
    row = sharesies_row(date="2024-03-04 02:15:30 (UTC)")

    [trade] = import_csv(sharesies_csv(row)).trades

    assert trade.executed_at == datetime(2024, 3, 4, 2, 15, 30, tzinfo=UTC)


def test_sell_has_sell_side() -> None:
    [trade] = import_csv(sharesies_csv(sharesies_row(kind="SELL"))).trades

    assert trade.side == Side.SELL


def test_transfer_out_is_not_a_sale() -> None:
    # Sharesies labels a transfer out as a SELL in "Transaction type". The method decides.
    row = sharesies_row(trade_id="T9", kind="SELL", method="TRANSFER OUT", actor="Operator")
    buy = sharesies_row(trade_id="T1")

    result = import_csv(sharesies_csv(buy, row))

    assert [t.side for t in result.trades] == [Side.BUY, Side.TRANSFER_OUT]


@pytest.mark.parametrize("actor", ["System", "Operator", "system"])
def test_platform_actors_are_not_the_user(actor: str) -> None:
    [trade] = import_csv(sharesies_csv(sharesies_row(actor=actor))).trades

    assert trade.initiated_by == InitiatedBy.PLATFORM


def test_user_name_means_user_initiated() -> None:
    [trade] = import_csv(sharesies_csv(sharesies_row(actor="Sam"))).trades

    assert trade.initiated_by == InitiatedBy.USER


def test_trades_are_sorted_by_time() -> None:
    later = sharesies_row(trade_id="T1", date="2024-05-01 00:00:00 (UTC)")
    earlier = sharesies_row(trade_id="T2", date="2024-03-01 00:00:00 (UTC)")

    result = import_csv(sharesies_csv(later, earlier))

    assert [t.source_id for t in result.trades] == ["T2", "T1"]


def test_missing_fee_is_zero() -> None:
    [trade] = import_csv(sharesies_csv(sharesies_row(fee=""))).trades

    assert trade.fee == Decimal(0)


def test_handles_byte_order_mark_and_bytes_input() -> None:
    data = ("﻿" + sharesies_csv(sharesies_row())).encode("utf-8")

    result = import_csv(data)

    assert len(result.trades) == 1


def test_bad_rows_are_skipped_with_row_numbers_and_reasons() -> None:
    rows = [
        sharesies_row(trade_id="T1"),
        sharesies_row(trade_id="T2", kind="DIVIDEND"),
        sharesies_row(trade_id="T3", quantity="abc"),
        sharesies_row(trade_id="T4", quantity="0"),
        sharesies_row(trade_id="T5", date="04/03/2024"),
        sharesies_row(trade_id="T6", market="LSE"),
        sharesies_row(trade_id="T1"),
        sharesies_row(trade_id="T7", price="-1"),
        sharesies_row(trade_id="T8", fee="x"),
    ]

    result = import_csv(sharesies_csv(*rows))

    assert [t.source_id for t in result.trades] == ["T1"]
    reasons = {s.row: s.reason for s in result.skipped_rows}
    assert reasons == {
        3: "Unknown transaction method: DIVIDEND",
        4: "Quantity is not a number: 'abc'",
        5: "Quantity must be greater than zero",
        6: "Trade date is not in the expected format: '04/03/2024'",
        7: "Unknown market: LSE",
        8: "Duplicate Trade ID: T1",
        9: "Price must be greater than zero",
        10: "Transaction fee is not a number: 'x'",
    }


def test_blank_lines_are_ignored() -> None:
    text = sharesies_csv(sharesies_row()) + "\n\n,,,,,,,,,,,,,\n"

    result = import_csv(text)

    assert len(result.trades) == 1
    assert result.skipped_rows == []


def test_unrecognised_file_is_rejected() -> None:
    with pytest.raises(UnrecognisedBrokerError) as error:
        import_csv("Date,Ticker,Shares\n2024-01-01,AAA,5\n")

    assert error.value.code == "unrecognised_broker"
    assert "sharesies" in str(error.value)


def test_empty_file_is_rejected() -> None:
    with pytest.raises(UnrecognisedBrokerError):
        import_csv("")


def test_file_with_no_buys_or_sells_is_rejected() -> None:
    with pytest.raises(NoTradesError):
        import_csv(SHARESIES_HEADER + "\n")


def test_file_with_only_bad_rows_is_rejected() -> None:
    with pytest.raises(NoTradesError):
        import_csv(sharesies_csv(sharesies_row(kind="DIVIDEND")))


def test_result_serialises_to_json_with_decimals_as_strings() -> None:
    result = import_csv(sharesies_csv(sharesies_row(quantity="0.5", price="12.340")))

    data = result.model_dump(mode="json")

    trade = data["trades"][0]
    assert trade["quantity"] == "0.5"
    assert trade["price"] == "12.340"
    assert trade["side"] == "buy"
    assert trade["executed_at"].startswith("2024-03-04T02:15:30.123456")
    assert ImportResult.model_validate(data) == result
