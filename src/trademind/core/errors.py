"""Errors that the user can see. Each one has a short code for the API (spec section 8)."""


class TradeMindError(Exception):
    code = "error"


class UnrecognisedBrokerError(TradeMindError):
    code = "unrecognised_broker"


class NoTradesError(TradeMindError):
    code = "no_trades_found"


class UnknownMarketError(TradeMindError):
    code = "unknown_market"


class PriceSourceError(TradeMindError):
    """The market data service failed (network down, rate limited, bad reply)."""

    code = "price_source_error"
