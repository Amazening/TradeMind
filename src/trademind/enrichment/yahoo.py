"""Yahoo Finance price source.

This uses Yahoo's unofficial chart endpoint. It needs no key and covers ASX, NZX and US shares
with split events, which made it the best free option in the provider test (spec section 4.2).

It is NOT licensed for use in a public app and can change without notice. Use it for building and
for personal runs. A licensed provider replaces it before a public launch.
"""

import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from trademind.core.errors import PriceSourceError, UnknownMarketError
from trademind.core.models import Split
from trademind.enrichment.source import PriceHistory

_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
_SUFFIXES = {"ASX": ".AX", "NZX": ".NZ"}
_US_MARKETS = {"NYSE", "NASDAQ"}


def yahoo_symbol(market: str, symbol: str) -> str:
    if market in _SUFFIXES:
        return symbol + _SUFFIXES[market]
    if market in _US_MARKETS:
        return symbol.replace(".", "-")  # Yahoo writes BRK.B as BRK-B
    raise UnknownMarketError(f"Unknown market: {market}")


class YahooPriceSource:
    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        retries: int = 2,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._client = client or httpx.Client(
            timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True
        )
        self._retries = retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._today = today

    def fetch_prices(self, market: str, symbol: str, start: date, end: date) -> PriceHistory | None:
        chart = self._chart(yahoo_symbol(market, symbol), start)
        if chart is None:
            return None
        closes, splits = _parse_chart(chart)
        closes = {day: price for day, price in closes.items() if day <= end}
        if not closes:
            return None
        return PriceHistory(
            currency=str(chart["meta"]["currency"]).upper(), closes=closes, splits=splits
        )

    def fetch_fx_to_nzd(self, currency: str, start: date, end: date) -> dict[date, Decimal] | None:
        chart = self._chart(f"{currency.upper()}NZD=X", start)
        if chart is None:
            return None
        closes, _ = _parse_chart(chart)
        closes = {day: rate for day, rate in closes.items() if day <= end}
        return closes or None

    def _chart(self, yahoo_name: str, start: date) -> dict[str, Any] | None:
        """The `result` of Yahoo's chart reply, or None if Yahoo does not know the symbol.

        Always asks up to today, so split events after the last trade are included.
        """
        params: dict[str, str | int] = {
            "period1": _epoch(start),
            "period2": _epoch(self._today() + timedelta(days=1)),
            "interval": "1d",
            "events": "split",
        }
        last_problem = "no reply"
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(self._backoff_seconds * attempt)
            try:
                response = self._client.get(_BASE_URL + yahoo_name, params=params)
            except httpx.HTTPError as error:
                last_problem = type(error).__name__
                continue
            if response.status_code == 404:
                return None
            if response.status_code == 429 or response.status_code >= 500:
                last_problem = f"HTTP {response.status_code}"
                continue
            if response.status_code != 200:
                raise PriceSourceError(f"Market data service replied HTTP {response.status_code}")
            return _result_of(response)
        raise PriceSourceError(f"Could not reach the market data service ({last_problem})")


def _result_of(response: httpx.Response) -> dict[str, Any] | None:
    try:
        chart = response.json()["chart"]
    except (ValueError, KeyError, TypeError):
        raise PriceSourceError("Market data service sent a reply we could not read") from None
    error = chart.get("error")
    if error:
        if str(error.get("code", "")).lower() == "not found":
            return None
        raise PriceSourceError(f"Market data service error: {error.get('code', 'unknown')}")
    results = chart.get("result")
    if not results:
        return None
    result: dict[str, Any] = results[0]
    return result


def _parse_chart(result: dict[str, Any]) -> tuple[dict[date, Decimal], list[Split]]:
    zone = _zone(result.get("meta", {}).get("exchangeTimezoneName"))
    timestamps: list[int] = result.get("timestamp") or []
    closes_raw: list[float | None] = (
        result.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    )

    closes: dict[date, Decimal] = {}
    for stamp, close in zip(timestamps, closes_raw, strict=False):
        if close is None:
            continue
        try:
            closes[_local_date(stamp, zone)] = Decimal(repr(round(float(close), 6)))
        except (InvalidOperation, ValueError, TypeError):
            continue

    splits: list[Split] = []
    for event in (result.get("events") or {}).get("splits", {}).values():
        try:
            splits.append(
                Split(
                    date=_local_date(int(event["date"]), zone),
                    numerator=Decimal(str(event["numerator"])),
                    denominator=Decimal(str(event["denominator"])),
                )
            )
        except (KeyError, InvalidOperation, ValueError, TypeError):
            continue
    splits.sort(key=lambda split: split.date)
    return closes, splits


def _zone(name: object) -> ZoneInfo:
    try:
        return ZoneInfo(str(name))
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def _local_date(stamp: int, zone: ZoneInfo) -> date:
    return datetime.fromtimestamp(stamp, tz=zone).date()


def _epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())
