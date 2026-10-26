"""Errors that the user can see. Each one has a short code for the API (spec section 8)."""


class TradeMindError(Exception):
    code = "error"


class UnrecognisedBrokerError(TradeMindError):
    code = "unrecognised_broker"


class NoTradesError(TradeMindError):
    code = "no_trades_found"


class UnknownMarketError(TradeMindError):
    code = "unknown_market"


class ExplainerError(TradeMindError):
    """The AI service failed, or is not set up. Reports still work without explanations."""

    code = "explainer_error"


class PriceSourceError(TradeMindError):
    """The market data service failed (network down, rate limited, bad reply)."""

    code = "price_source_error"
