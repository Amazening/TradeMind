"""Looking up a price on a date."""

from bisect import bisect_right
from collections.abc import Mapping
from datetime import date
from decimal import Decimal


class PriceLookup:
    """Closing prices by date. Markets are closed at weekends, so lookups fall back to the
    last close on or before the date, up to `max_gap_days` back."""

    def __init__(self, closes: Mapping[date, Decimal], max_gap_days: int = 7) -> None:
        self._dates = sorted(closes)
        self._values = [closes[day] for day in self._dates]
        self._max_gap_days = max_gap_days

    def on_or_before(self, day: date) -> Decimal | None:
        index = bisect_right(self._dates, day)
        if index == 0:
            return None
        found = self._dates[index - 1]
        if (day - found).days > self._max_gap_days:
            return None
        return self._values[index - 1]
