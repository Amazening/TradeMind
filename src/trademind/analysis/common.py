"""Helpers shared by the patterns."""

from datetime import date, timedelta
from decimal import Decimal

from trademind.core.models import Confidence, Decision, EnrichedHistory, InitiatedBy, Side
from trademind.core.prices import PriceLookup

_NO_GAP_LIMIT = 36500  # days. Used for own-trade prices, which only exist on trade days.


def user_decisions(history: EnrichedHistory, side: Side | None = None) -> list[Decision]:
    """The investor's own decisions. Platform trades (auto-invest and so on) are left out."""
    return [
        d
        for d in history.decisions
        if d.initiated_by == InitiatedBy.USER and (side is None or d.side == side)
    ]


def confidence_level(*sample_over_minimum: float) -> Confidence:
    """Spec section 5.4: low just over the minimum, medium at 2x, high at 4x.

    Each argument is a sample size divided by its minimum. The smallest one decides.
    """
    ratio = min(sample_over_minimum)
    if ratio >= 4:
        return "high"
    if ratio >= 2:
        return "medium"
    return "low"


def has_market_prices(history: EnrichedHistory, key: str) -> bool:
    series = history.prices.get(key)
    return series is not None and series.source == "market"


class Valuer:
    """Prices and exchange rates on a date."""

    def __init__(self, history: EnrichedHistory) -> None:
        self._prices = {
            key: PriceLookup(series.closes, 7 if series.source == "market" else _NO_GAP_LIMIT)
            for key, series in history.prices.items()
        }
        self._currencies = {key: series.currency for key, series in history.prices.items()}
        self._fx = {currency: PriceLookup(rates) for currency, rates in history.fx_to_nzd.items()}

    def price(self, key: str, day: date) -> Decimal | None:
        """The close on or before `day`. For shares without market prices, the last own trade."""
        lookup = self._prices.get(key)
        return lookup.on_or_before(day) if lookup else None

    def currency(self, key: str) -> str:
        return self._currencies[key]

    def nzd_rate(self, currency: str, day: date) -> Decimal | None:
        """How many NZD one unit of `currency` was worth, or None if we have no rate."""
        if currency.upper() == "NZD":
            return Decimal(1)
        lookup = self._fx.get(currency.upper())
        return lookup.on_or_before(day) if lookup else None


def month_starts(first: date, last: date) -> list[date]:
    """The first day of every calendar month from `first`'s month to `last`'s month."""
    months: list[date] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(date(year, month, 1))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def day_before(day: date) -> date:
    return day - timedelta(days=1)
