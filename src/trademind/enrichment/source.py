"""The interface the rest of the system uses to get market data (spec section 4.3).

Nothing outside `enrichment/` knows which provider is behind it. Swapping providers means writing
one new class.
"""

from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from trademind.core.models import Split


class PriceHistory(BaseModel):
    """What a provider returns for one instrument.

    `closes` are on today's basis, already adjusted for splits.
    """

    currency: str
    closes: dict[date, Decimal]
    splits: list[Split]


class PriceSource(Protocol):
    def fetch_prices(self, market: str, symbol: str, start: date, end: date) -> PriceHistory | None:
        """Daily closes from `start` to `end`, and every split up to today.

        Returns None if the provider has no data for this instrument, for example a delisted
        share. Raises PriceSourceError if the service itself fails.
        """
        ...

    def fetch_fx_to_nzd(self, currency: str, start: date, end: date) -> dict[date, Decimal] | None:
        """Daily exchange rate from `currency` to NZD, or None if not available."""
        ...
