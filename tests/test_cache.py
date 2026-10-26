from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tests.fakes import FakePriceSource
from trademind.core.models import Split
from trademind.enrichment import CachedPriceSource, PriceHistory

START = date(2023, 1, 1)
END = date(2024, 1, 1)
HISTORY = PriceHistory(
    currency="AUD",
    closes={date(2023, 6, 1): Decimal("2.5")},
    splits=[Split(date=date(2023, 9, 1), numerator=Decimal(1), denominator=Decimal(25))],
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2024, 1, 10, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def test_second_request_comes_from_disk(tmp_path: Path) -> None:
    inner = FakePriceSource({"ASX:AAA": HISTORY})
    cached = CachedPriceSource(inner, tmp_path)

    first = cached.fetch_prices("ASX", "AAA", START, END)
    second = cached.fetch_prices("ASX", "AAA", START, END)

    assert first == second == HISTORY
    assert len(inner.price_calls) == 1


def test_a_new_cache_object_reads_the_same_files(tmp_path: Path) -> None:
    inner = FakePriceSource({"ASX:AAA": HISTORY})
    CachedPriceSource(inner, tmp_path).fetch_prices("ASX", "AAA", START, END)

    again = CachedPriceSource(inner, tmp_path).fetch_prices("ASX", "AAA", START, END)

    assert again == HISTORY
    assert len(inner.price_calls) == 1


def test_a_smaller_range_is_covered_by_a_bigger_cached_one(tmp_path: Path) -> None:
    inner = FakePriceSource({"ASX:AAA": HISTORY})
    cached = CachedPriceSource(inner, tmp_path)
    cached.fetch_prices("ASX", "AAA", START, END)

    cached.fetch_prices("ASX", "AAA", date(2023, 3, 1), date(2023, 12, 1))

    assert len(inner.price_calls) == 1


def test_a_wider_range_fetches_again(tmp_path: Path) -> None:
    inner = FakePriceSource({"ASX:AAA": HISTORY})
    cached = CachedPriceSource(inner, tmp_path)
    cached.fetch_prices("ASX", "AAA", START, END)

    cached.fetch_prices("ASX", "AAA", date(2022, 1, 1), END)

    assert len(inner.price_calls) == 2


def test_not_found_is_cached_too(tmp_path: Path) -> None:
    inner = FakePriceSource()
    cached = CachedPriceSource(inner, tmp_path)

    assert cached.fetch_prices("ASX", "GONE", START, END) is None
    assert cached.fetch_prices("ASX", "GONE", START, END) is None
    assert len(inner.price_calls) == 1


def test_entries_expire(tmp_path: Path) -> None:
    clock = Clock()
    inner = FakePriceSource({"ASX:AAA": HISTORY})
    cached = CachedPriceSource(inner, tmp_path, ttl=timedelta(days=7), now=clock)
    cached.fetch_prices("ASX", "AAA", START, END)

    clock.now += timedelta(days=8)
    cached.fetch_prices("ASX", "AAA", START, END)

    assert len(inner.price_calls) == 2


def test_different_instruments_have_different_entries(tmp_path: Path) -> None:
    inner = FakePriceSource({"ASX:AAA": HISTORY, "NZX:AAA": HISTORY})
    cached = CachedPriceSource(inner, tmp_path)

    cached.fetch_prices("ASX", "AAA", START, END)
    cached.fetch_prices("NZX", "AAA", START, END)

    assert len(inner.price_calls) == 2


def test_damaged_cache_file_is_ignored(tmp_path: Path) -> None:
    inner = FakePriceSource({"ASX:AAA": HISTORY})
    cached = CachedPriceSource(inner, tmp_path)
    cached.fetch_prices("ASX", "AAA", START, END)
    for file in tmp_path.glob("*.json"):
        file.write_text("{not json", encoding="utf-8")

    result = cached.fetch_prices("ASX", "AAA", START, END)

    assert result == HISTORY
    assert len(inner.price_calls) == 2


def test_odd_symbols_cannot_escape_the_cache_folder(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    inner = FakePriceSource()
    cached = CachedPriceSource(inner, cache_dir)

    cached.fetch_prices("ASX", "../../evil", START, END)

    files = list(tmp_path.rglob("*.json"))
    assert files
    assert all(file.parent == cache_dir for file in files)


def test_fx_rates_are_cached(tmp_path: Path) -> None:
    rates = {date(2023, 6, 1): Decimal("1.08")}
    inner = FakePriceSource(fx={"AUD": rates})
    cached = CachedPriceSource(inner, tmp_path)

    first = cached.fetch_fx_to_nzd("AUD", START, END)
    second = cached.fetch_fx_to_nzd("AUD", START, END)

    assert first == second == rates
    assert len(inner.fx_calls) == 1
