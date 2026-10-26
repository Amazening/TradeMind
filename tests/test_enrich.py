from datetime import date
from decimal import Decimal
from typing import Any

from tests.fakes import FakePriceSource, daily
from tests.helpers import make_trade
from trademind.core.models import ImportResult, SkippedRow, Split
from trademind.enrichment import PriceHistory, enrich, price_consistency


def _result(*trades_args: dict[str, Any]) -> ImportResult:
    trades = [make_trade(n, **args) for n, args in enumerate(trades_args, start=1)]
    return ImportResult(broker="sharesies", trades=trades, skipped_rows=[])


def _history(price: str = "2.00", splits: list[Split] | None = None) -> PriceHistory:
    return PriceHistory(
        currency="AUD", closes=daily(date(2023, 1, 1), 800, price), splits=splits or []
    )


def test_adds_market_prices_and_decisions() -> None:
    result = _result({"when": "2024-03-04T02:00:00", "price": "2.00"})
    source = FakePriceSource(
        {"ASX:AAA": _history()}, fx={"AUD": {date(2024, 3, 4): Decimal("1.1")}}
    )

    history = enrich(result, source)

    assert history.prices["ASX:AAA"].source == "market"
    assert history.prices["ASX:AAA"].currency == "AUD"
    assert history.missing_prices == []
    assert len(history.decisions) == 1
    assert history.fx_to_nzd == {"AUD": {date(2024, 3, 4): Decimal("1.1")}}
    assert history.data_notes == []


def test_asks_for_a_year_of_prices_before_the_first_trade() -> None:
    result = _result(
        {"when": "2024-03-04T02:00:00"},
        {"when": "2024-06-10T02:00:00"},
    )
    source = FakePriceSource({"ASX:AAA": _history()})

    enrich(result, source)

    market, symbol, start, end = source.price_calls[0]
    assert (market, symbol) == ("ASX", "AAA")
    assert start == date(2023, 3, 4)  # 366 days before 2024-03-04
    assert end == date(2024, 6, 10)  # the last trade


def test_each_instrument_and_currency_is_asked_for_once() -> None:
    result = _result(
        {"when": "2024-03-04T02:00:00"},
        {"when": "2024-03-05T02:00:00"},
        {"when": "2024-03-06T02:00:00", "symbol": "BBB"},
    )
    source = FakePriceSource()

    enrich(result, source)

    assert sorted(call[1] for call in source.price_calls) == ["AAA", "BBB"]
    assert [call[0] for call in source.fx_calls] == ["AUD"]


def test_nzd_trades_need_no_exchange_rate() -> None:
    result = _result({"when": "2024-03-04T02:00:00", "market": "NZX"})
    result.trades[0] = result.trades[0].model_copy(update={"currency": "NZD"})
    source = FakePriceSource(
        {"NZX:AAA": PriceHistory(currency="NZD", closes=daily(date(2023, 1, 1), 800), splits=[])}
    )

    history = enrich(result, source)

    assert source.fx_calls == []
    assert history.fx_to_nzd == {}


def test_unpriced_share_falls_back_to_own_trade_prices_with_a_note() -> None:
    result = _result(
        {"when": "2024-03-04T02:00:00", "quantity": "10", "price": "2.00"},
        {"when": "2024-03-04T02:00:05", "quantity": "30", "price": "3.00"},
    )

    history = enrich(result, FakePriceSource())

    assert history.missing_prices == ["ASX:AAA"]
    series = history.prices["ASX:AAA"]
    assert series.source == "own_trades"
    assert series.closes == {date(2024, 3, 4): Decimal("2.75")}  # (10x2 + 30x3) / 40
    assert any("No market prices for ASX:AAA" in n.message for n in history.data_notes)


def test_price_currency_mismatch_is_ignored_with_a_note() -> None:
    result = _result({"when": "2024-03-04T02:00:00"})
    wrong = PriceHistory(currency="GBP", closes=daily(date(2023, 1, 1), 800), splits=[])

    history = enrich(result, FakePriceSource({"ASX:AAA": wrong}))

    assert history.missing_prices == ["ASX:AAA"]
    assert any("GBP" in n.message for n in history.data_notes)


def test_missing_exchange_rate_adds_a_note() -> None:
    result = _result({"when": "2024-03-04T02:00:00"})

    history = enrich(result, FakePriceSource({"ASX:AAA": _history()}))

    assert history.fx_to_nzd == {}
    assert any("No exchange rates from AUD" in n.message for n in history.data_notes)


def test_consolidation_adjusts_earlier_trades_and_adds_a_note() -> None:
    split = Split(date=date(2024, 6, 1), numerator=Decimal(1), denominator=Decimal(25))
    result = _result(
        {"when": "2024-03-04T02:00:00", "quantity": "1000", "price": "0.08"},
        {"when": "2024-07-01T02:00:00", "quantity": "10", "price": "2.00"},
    )
    source = FakePriceSource({"ASX:AAA": _history("2.00", [split])})

    history = enrich(result, source)

    before, after = history.trades
    assert (before.quantity, before.price) == (Decimal("40"), Decimal("2"))
    assert (after.quantity, after.price) == (Decimal("10"), Decimal("2.00"))
    assert history.splits == {"ASX:AAA": [split]}
    assert any(
        "1 trades before 2024-06-01 were adjusted for a 1:25" in n.message
        for n in history.data_notes
    )
    # With the adjustment the trade prices agree with the market closes.
    assert price_consistency(history)["ASX:AAA"] == Decimal(1)


def test_split_before_the_first_trade_is_ignored() -> None:
    split = Split(date=date(2023, 6, 1), numerator=Decimal(2), denominator=Decimal(1))
    result = _result({"when": "2024-03-04T02:00:00"})

    history = enrich(result, FakePriceSource({"ASX:AAA": _history("2.00", [split])}))

    assert history.splits == {}


def test_market_prices_that_disagree_with_trade_prices_are_not_used() -> None:
    # The provider shows prices 25 times the trade prices, and reports no split.
    result = _result({"when": "2024-03-04T02:00:00", "price": "0.08"})

    history = enrich(result, FakePriceSource({"ASX:AAA": _history("2.00")}))

    assert history.missing_prices == ["ASX:AAA"]
    assert history.prices["ASX:AAA"].source == "own_trades"
    assert price_consistency(history) == {}
    [note] = [n for n in history.data_notes if "market close" in n.message]
    assert "0.04 times the market close" in note.message
    assert "were not used" in note.message


def test_slightly_different_prices_are_accepted() -> None:
    # Trades happen at different prices from the close, but not by a large factor.
    result = _result({"when": "2024-03-04T02:00:00", "price": "2.20"})

    history = enrich(result, FakePriceSource({"ASX:AAA": _history("2.00")}))

    assert history.missing_prices == []
    assert history.prices["ASX:AAA"].source == "market"
    assert price_consistency(history)["ASX:AAA"] == Decimal("1.1")


def test_skipped_import_rows_become_data_notes() -> None:
    result = _result({"when": "2024-03-04T02:00:00"})
    result = result.model_copy(
        update={"skipped_rows": [SkippedRow(row=7, reason="Unknown market: LSE")]}
    )

    history = enrich(result, FakePriceSource({"ASX:AAA": _history()}))

    assert history.data_notes[0].message == "Row 7 was skipped: Unknown market: LSE"


def test_result_can_be_written_as_json_and_read_back() -> None:
    result = _result({"when": "2024-03-04T02:00:00"})
    history = enrich(result, FakePriceSource({"ASX:AAA": _history()}))

    data = history.model_dump(mode="json")

    assert type(history).model_validate(data) == history
