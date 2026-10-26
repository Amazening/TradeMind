"""Yahoo reader tests use made-up replies through a mock transport. No internet."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from trademind.core.errors import PriceSourceError, UnknownMarketError
from trademind.enrichment.yahoo import YahooPriceSource, yahoo_symbol


def _stamp(year: int, month: int, day: int, hour: int = 0) -> int:
    return int(datetime(year, month, day, hour, tzinfo=UTC).timestamp())


def _chart(
    closes: list[float | None],
    *,
    currency: str = "AUD",
    zone: str = "Australia/Sydney",
    splits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # 23:00 UTC is 10:00 the next day in Sydney (daylight saving).
    stamps = [_stamp(2024, 3, 3 + n, 23) for n in range(len(closes))]
    result: dict[str, Any] = {
        "meta": {"currency": currency, "exchangeTimezoneName": zone},
        "timestamp": stamps,
        "indicators": {"quote": [{"close": closes}]},
    }
    if splits:
        result["events"] = {"splits": splits}
    return {"chart": {"result": [result], "error": None}}


def _source(handler: httpx.MockTransport, **kwargs: Any) -> YahooPriceSource:
    return YahooPriceSource(
        httpx.Client(transport=handler),
        sleep=lambda _: None,
        today=lambda: date(2024, 6, 1),
        **kwargs,
    )


def test_symbols_for_each_market() -> None:
    assert yahoo_symbol("ASX", "AAA") == "AAA.AX"
    assert yahoo_symbol("NZX", "AAA") == "AAA.NZ"
    assert yahoo_symbol("NYSE", "BRK.B") == "BRK-B"
    assert yahoo_symbol("NASDAQ", "AAA") == "AAA"
    with pytest.raises(UnknownMarketError):
        yahoo_symbol("LSE", "AAA")


def test_reads_closes_in_the_markets_own_dates() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=_chart([2.5, 2.6])))

    history = _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31))

    assert history is not None
    assert history.currency == "AUD"
    assert history.closes == {date(2024, 3, 4): Decimal("2.5"), date(2024, 3, 5): Decimal("2.6")}


def test_floats_become_clean_decimals() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=_chart([0.1 + 0.2]))  # 0.30000000000000004
    )

    history = _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31))

    assert history is not None
    assert history.closes[date(2024, 3, 4)] == Decimal("0.3")


def test_skips_missing_closes_and_trims_to_end() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=_chart([2.5, None, 2.7]))
    )

    history = _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 3, 5))

    assert history is not None
    assert list(history.closes) == [date(2024, 3, 4)]


def test_reads_split_events() -> None:
    splits = {
        "1717200000": {
            "date": _stamp(2024, 5, 31, 23),
            "numerator": 1,
            "denominator": 25,
            "splitRatio": "1:25",
        }
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=_chart([2.5], splits=splits))
    )

    history = _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31))

    assert history is not None
    [split] = history.splits
    assert split.date == date(2024, 6, 1)
    assert (split.numerator, split.denominator) == (Decimal(1), Decimal(25))


def test_asks_for_a_range_that_reaches_today_so_late_splits_are_found() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_chart([2.5]))

    _source(httpx.MockTransport(handler)).fetch_prices(
        "ASX", "AAA", date(2024, 1, 1), date(2024, 3, 31)
    )

    params = seen[0].url.params
    assert seen[0].url.path.endswith("/AAA.AX")
    assert params["period1"] == str(_stamp(2024, 1, 1))
    assert params["period2"] == str(_stamp(2024, 6, 2))  # the day after "today"
    assert params["events"] == "split"


def test_unknown_symbol_gives_none() -> None:
    body = {"chart": {"result": None, "error": {"code": "Not Found", "description": "x"}}}
    transport = httpx.MockTransport(lambda request: httpx.Response(404, json=body))

    assert (
        _source(transport).fetch_prices("ASX", "ZZZ", date(2024, 1, 1), date(2024, 12, 31)) is None
    )


def test_not_found_inside_a_200_reply_gives_none() -> None:
    body = {"chart": {"result": None, "error": {"code": "Not Found", "description": "x"}}}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))

    assert (
        _source(transport).fetch_prices("ASX", "ZZZ", date(2024, 1, 1), date(2024, 12, 31)) is None
    )


def test_symbol_with_no_bars_gives_none() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=_chart([])))

    assert (
        _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31)) is None
    )


def test_retries_after_rate_limiting() -> None:
    replies = iter([httpx.Response(429), httpx.Response(200, json=_chart([2.5]))])
    transport = httpx.MockTransport(lambda request: next(replies))

    history = _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31))

    assert history is not None


def test_gives_up_with_a_price_source_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503))

    with pytest.raises(PriceSourceError):
        _source(transport, retries=2).fetch_prices(
            "ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31)
        )


def test_network_failure_is_a_price_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with pytest.raises(PriceSourceError):
        _source(httpx.MockTransport(handler)).fetch_prices(
            "ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31)
        )


def test_garbled_reply_is_a_price_source_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="not json"))

    with pytest.raises(PriceSourceError):
        _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31))


def test_other_error_codes_are_price_source_errors() -> None:
    body = {"chart": {"result": None, "error": {"code": "Server Error", "description": "x"}}}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))

    with pytest.raises(PriceSourceError):
        _source(transport).fetch_prices("ASX", "AAA", date(2024, 1, 1), date(2024, 12, 31))


def test_fx_uses_the_pair_symbol() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_chart([1.08], currency="NZD", zone="UTC"))

    rates = _source(httpx.MockTransport(handler)).fetch_fx_to_nzd(
        "aud", date(2024, 1, 1), date(2024, 12, 31)
    )

    assert seen[0].url.path.endswith("/AUDNZD=X")
    assert rates == {date(2024, 3, 3): Decimal("1.08")}
