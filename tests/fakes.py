"""A price source with hand-made prices. Tests never call the internet."""

from datetime import date
from decimal import Decimal

from trademind.enrichment.source import PriceHistory


class FakePriceSource:
    def __init__(
        self,
        prices: dict[str, PriceHistory] | None = None,
        fx: dict[str, dict[date, Decimal]] | None = None,
    ) -> None:
        self.prices = prices or {}
        self.fx = fx or {}
        self.price_calls: list[tuple[str, str, date, date]] = []
        self.fx_calls: list[tuple[str, date, date]] = []

    def fetch_prices(self, market: str, symbol: str, start: date, end: date) -> PriceHistory | None:
        self.price_calls.append((market, symbol, start, end))
        return self.prices.get(f"{market}:{symbol}")

    def fetch_fx_to_nzd(self, currency: str, start: date, end: date) -> dict[date, Decimal] | None:
        self.fx_calls.append((currency, start, end))
        return self.fx.get(currency)


class FakeChatModel:
    """A text model with scripted replies. A reply that is an exception is raised.

    When the script runs out, the last reply is used again.
    """

    name = "fake:model"

    def __init__(self, replies: list[str | Exception]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        reply = self.replies[min(len(self.calls), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply


def daily(start: date, days: int, price: str = "2.00") -> dict[date, Decimal]:
    """`days` consecutive calendar days of the same close, starting at `start`."""
    from datetime import timedelta

    return {start + timedelta(days=n): Decimal(price) for n in range(days)}
