"""Data shapes passed between layers (spec section 6).

Money and quantities are `Decimal`, never `float`. In JSON they are strings, so no precision
is lost.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

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
