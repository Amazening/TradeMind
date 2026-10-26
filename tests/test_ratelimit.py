from datetime import UTC, datetime, timedelta

import pytest

import trademind.api.ratelimit as ratelimit_module
from trademind.api.ratelimit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def test_allows_up_to_the_limit_then_refuses() -> None:
    limiter = RateLimiter(3, timedelta(hours=1), Clock())

    assert [limiter.allow("a") for _ in range(5)] == [True, True, True, False, False]


def test_each_address_has_its_own_allowance() -> None:
    limiter = RateLimiter(1, timedelta(hours=1), Clock())

    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False


def test_the_window_slides() -> None:
    clock = Clock()
    limiter = RateLimiter(2, timedelta(hours=1), clock)
    limiter.allow("a")
    clock.now += timedelta(minutes=40)
    limiter.allow("a")

    clock.now += timedelta(minutes=21)  # the first attempt is now over an hour old

    assert limiter.allow("a") is True
    assert limiter.allow("a") is False


def test_retry_after_says_when_the_oldest_attempt_expires() -> None:
    clock = Clock()
    limiter = RateLimiter(1, timedelta(hours=1), clock)
    limiter.allow("a")
    clock.now += timedelta(minutes=45)

    assert 899 <= limiter.retry_after_seconds("a") <= 902
    assert limiter.retry_after_seconds("never-seen") == 0


def test_retry_after_is_zero_when_allowed() -> None:
    limiter = RateLimiter(2, timedelta(hours=1), Clock())
    limiter.allow("a")

    assert limiter.retry_after_seconds("a") == 0


def test_addresses_are_forgotten_once_their_window_passes() -> None:
    clock = Clock()
    limiter = RateLimiter(1, timedelta(hours=1), clock)
    limiter.allow("a")
    clock.now += timedelta(hours=2)

    limiter.allow("b")

    assert "a" not in limiter._hits


def test_a_flood_of_addresses_cannot_fill_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit_module, "_MAX_TRACKED_ADDRESSES", 50)
    limiter = RateLimiter(1, timedelta(hours=1), Clock())

    for n in range(500):
        limiter.allow(f"10.0.0.{n}")

    assert len(limiter._hits) <= 51
