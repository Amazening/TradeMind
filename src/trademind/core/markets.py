"""Markets we know about, and the time zone each one trades in.

A trade's "market date" is its date in the market's own time zone, not in UTC.
A late ASX trade is already the next day in Sydney.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from trademind.core.errors import UnknownMarketError

MARKET_TIMEZONES: dict[str, ZoneInfo] = {
    "ASX": ZoneInfo("Australia/Sydney"),
    "NZX": ZoneInfo("Pacific/Auckland"),
    "NYSE": ZoneInfo("America/New_York"),
    "NASDAQ": ZoneInfo("America/New_York"),
}


def is_known_market(market: str) -> bool:
    return market in MARKET_TIMEZONES


def market_date(executed_at: datetime, market: str) -> date:
    """The calendar date of `executed_at` in the market's own time zone."""
    try:
        zone = MARKET_TIMEZONES[market]
    except KeyError:
        raise UnknownMarketError(f"Unknown market: {market}") from None
    return executed_at.astimezone(zone).date()
