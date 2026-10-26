"""Data shapes passed between layers (spec section 6).

Money and quantities are `Decimal`, never `float`. In JSON they are strings, so no precision
is lost.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"
    TRANSFER_OUT = "transfer_out"


class InitiatedBy(StrEnum):
    USER = "user"
    PLATFORM = "platform"


class Trade(BaseModel):
    """One row of a broker file, after cleaning."""

    model_config = ConfigDict(frozen=True)

    id: str
    source_id: str
    executed_at: AwareDatetime
    market: str
    symbol: str
    name: str
    side: Side
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    currency: str
    fee: Decimal = Field(ge=0)
    initiated_by: InitiatedBy


class SkippedRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    row: int
    reason: str


class ImportResult(BaseModel):
    """What ingestion hands to enrichment."""

    broker: str
    trades: list[Trade]
    skipped_rows: list[SkippedRow]


class Decision(BaseModel):
    """One choice by the investor. Split fills of one order count as one decision."""

    model_config = ConfigDict(frozen=True)

    id: str
    trade_ids: list[str]
    market_date: date
    market: str
    symbol: str
    side: Side
    quantity: Decimal
    avg_price: Decimal
    initiated_by: InitiatedBy


class Split(BaseModel):
    """A share split or consolidation.

    `numerator` new shares for every `denominator` old shares. A 2-for-1 split is 2:1. A
    1-for-25 consolidation is 1:25. `date` is the first trading day on the new basis.
    """

    model_config = ConfigDict(frozen=True)

    date: date
    numerator: Decimal = Field(gt=0)
    denominator: Decimal = Field(gt=0)


class PriceSeries(BaseModel):
    """Daily closing prices for one instrument, in its trade currency.

    `source` is "market" for prices from a data provider. It is "own_trades" when none were
    available and the series is built from the investor's own trade prices.
    """

    currency: str
    closes: dict[date, Decimal]
    source: Literal["market", "own_trades"]


class DataNote(BaseModel):
    """Something the user should know about the data, such as a share we could not price."""

    model_config = ConfigDict(frozen=True)

    level: Literal["info", "warning"]
    message: str


class EnrichedHistory(BaseModel):
    """What enrichment hands to analysis (spec section 6.2).

    `trades` are adjusted for splits, so they match the prices. Keys of `prices`, `splits` and
    `missing_prices` look like "ASX:ABC".
    """

    broker: str
    trades: list[Trade]
    decisions: list[Decision]
    prices: dict[str, PriceSeries]
    splits: dict[str, list[Split]]
    fx_to_nzd: dict[str, dict[date, Decimal]]
    missing_prices: list[str]
    data_notes: list[DataNote]
