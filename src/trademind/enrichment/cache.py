"""Disk cache for market data.

Only prices are cached: public data, keyed by market and symbol, never linked to a user.
Entries expire after a week, because a later split changes the basis of older prices.
"""

import os
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pydantic import AwareDatetime, BaseModel

from trademind.enrichment.source import PriceHistory, PriceSource


class _PricesEntry(BaseModel):
    fetched_at: AwareDatetime
    start: date
    end: date
    history: PriceHistory | None


class _FxEntry(BaseModel):
    fetched_at: AwareDatetime
    start: date
    end: date
    rates: dict[date, Decimal] | None


class CachedPriceSource:
    def __init__(
        self,
        inner: PriceSource,
        cache_dir: Path,
        *,
        ttl: timedelta = timedelta(days=7),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._inner = inner
        self._dir = cache_dir
        self._ttl = ttl
        self._now = now

    def fetch_prices(self, market: str, symbol: str, start: date, end: date) -> PriceHistory | None:
        path = self._path(f"prices-{market}-{symbol}")
        cached = self._load(path, _PricesEntry)
        if cached and self._covers(cached, start, end):
            return cached.history
        history = self._inner.fetch_prices(market, symbol, start, end)
        self._save(
            path, _PricesEntry(fetched_at=self._now(), start=start, end=end, history=history)
        )
        return history

    def fetch_fx_to_nzd(self, currency: str, start: date, end: date) -> dict[date, Decimal] | None:
        path = self._path(f"fx-{currency}")
        cached = self._load(path, _FxEntry)
        if cached and self._covers(cached, start, end):
            return cached.rates
        rates = self._inner.fetch_fx_to_nzd(currency, start, end)
        self._save(path, _FxEntry(fetched_at=self._now(), start=start, end=end, rates=rates))
        return rates

    def _covers(self, entry: _PricesEntry | _FxEntry, start: date, end: date) -> bool:
        fresh = self._now() - entry.fetched_at < self._ttl
        return fresh and entry.start <= start and entry.end >= end

    def _path(self, name: str) -> Path:
        return self._dir / (re.sub(r"[^A-Za-z0-9._-]", "_", name) + ".json")

    def _load[T: (_PricesEntry, _FxEntry)](self, path: Path, model: type[T]) -> T | None:
        try:
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # missing or damaged: treat as a miss

    def _save(self, path: Path, entry: _PricesEntry | _FxEntry) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(entry.model_dump_json(), encoding="utf-8")
        os.replace(temp, path)  # a half-written file is never read
