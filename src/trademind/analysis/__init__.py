"""Analysis: find behaviour patterns in an enriched trading history.

The output is a `Report` (spec section 6.3). It is the main product: the web app, the API and the
command line all start from it.
"""

from datetime import UTC, datetime

from trademind.analysis import disposition, overtrading, runup
from trademind.core.models import (
    EnrichedHistory,
    InitiatedBy,
    Report,
    ReportPeriod,
    ReportSummary,
)

SCHEMA_VERSION = "1.0"
DISCLAIMER = "This report describes past trading behaviour. It is not financial advice."


def analyse(history: EnrichedHistory, now: datetime | None = None) -> Report:
    trades = history.trades
    user = sum(1 for d in history.decisions if d.initiated_by == InitiatedBy.USER)
    return Report(
        schema_version=SCHEMA_VERSION,
        generated_at=now or datetime.now(UTC),
        broker=history.broker,
        period=ReportPeriod(
            start=min(t.executed_at for t in trades).date(),
            end=max(t.executed_at for t in trades).date(),
        ),
        summary=ReportSummary(
            trades_read=len(trades),
            decisions=len(history.decisions),
            user_decisions=user,
            platform_decisions=len(history.decisions) - user,
            markets=sorted({t.market for t in trades}),
            instruments=len({(t.market, t.symbol) for t in trades}),
        ),
        findings=[
            overtrading.detect(history),
            disposition.detect(history),
            runup.detect(history),
        ],
        data_notes=history.data_notes,
        disclaimer=DISCLAIMER,
    )
