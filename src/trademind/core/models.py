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


class FileDiagnostics(BaseModel):
    """Counts about how a file was read. They hold no share names, dates or amounts.

    A tester can send these to the developer to show what their file looked like (spec section
    6.3). `initiated_by` uses "you" for the investor's own name, so the name is never shown.
    Labels from the file other than the investor's own name are kept as written.
    """

    model_config = ConfigDict(frozen=True)

    rows_read: int
    rows_skipped: int
    skipped_reasons: dict[str, int]
    transaction_methods: dict[str, int]
    initiated_by: dict[str, int]
    small_buys: dict[str, int]  # buys worth under 1 in their own currency, by who started them
    shares_without_market_prices: int = 0
    shares_adjusted_for_splits: int = 0


class ImportResult(BaseModel):
    """What ingestion hands to enrichment."""

    broker: str
    trades: list[Trade]
    skipped_rows: list[SkippedRow]
    diagnostics: FileDiagnostics | None = None


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
    diagnostics: FileDiagnostics | None = None


PatternResult = Literal["detected", "not_detected", "insufficient_data"]
Confidence = Literal["low", "medium", "high"]


class Evidence(BaseModel):
    """One piece of support for a finding. `decision_id` is None for a summary line."""

    model_config = ConfigDict(frozen=True)

    decision_id: str | None
    note: str


class FindingSample(BaseModel):
    """How much data a finding rests on. `cases` counts what the pattern compares."""

    model_config = ConfigDict(frozen=True)

    decisions: int
    cases: int


class Finding(BaseModel):
    """The result of one pattern check (spec section 6.3).

    `explanation` is filled in later by the reporting step. Analysis never sets it.
    `explained_by` says who wrote it: "ai" for a model's rewording of the facts, or "tool" for
    text written by code (used when a model is not available or its reply is rejected).
    """

    pattern: str
    title: str
    result: PatternResult
    confidence: Confidence | None
    sample: FindingSample
    metrics: dict[str, float]
    threshold: str
    evidence: list[Evidence]
    notes: list[str]
    explanation: str | None = None
    explained_by: Literal["ai", "tool"] | None = None


class ReportPeriod(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: date
    end: date


class ReportSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    trades_read: int
    decisions: int
    user_decisions: int
    platform_decisions: int
    markets: list[str]
    instruments: int


class Report(BaseModel):
    """The main output of TradeMind (spec section 6.3). Everything else is built from this."""

    schema_version: str
    tool_version: str
    generated_at: AwareDatetime
    broker: str
    period: ReportPeriod
    summary: ReportSummary
    findings: list[Finding]
    data_notes: list[DataNote]
    diagnostics: FileDiagnostics | None = None
    disclaimer: str
