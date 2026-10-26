from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import make_trade
from trademind.api.jobs import JobError, JobStore, StoreFullError
from trademind.core.models import ImportResult


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _imported() -> ImportResult:
    return ImportResult(broker="sharesies", trades=[make_trade()], skipped_rows=[])


def test_a_new_job_is_queued_and_holds_the_upload() -> None:
    store = JobStore()

    job = store.create(_imported())

    assert job.status == "queued"
    assert job.imported is not None
    assert store.get(job.id) is job


def test_ids_are_long_and_never_repeat() -> None:
    store = JobStore(max_jobs=100)

    ids = {store.create(_imported()).id for _ in range(50)}

    assert len(ids) == 50
    assert all(len(job_id) >= 20 for job_id in ids)


def test_start_hands_over_the_upload_and_the_store_forgets_it() -> None:
    store = JobStore()
    job = store.create(_imported())

    imported = store.start(job.id)

    assert imported is not None
    assert job.imported is None
    assert (job.status, job.step) == ("running", "getting_prices")


def test_start_on_a_deleted_job_does_nothing() -> None:
    store = JobStore()
    job = store.create(_imported())
    store.delete(job.id)

    assert store.start(job.id) is None


def test_a_failed_job_drops_the_upload_and_keeps_the_error() -> None:
    store = JobStore()
    job = store.create(_imported())

    store.fail(job.id, JobError("price_source_error", "Try later"))

    assert job.status == "failed"
    assert job.imported is None
    assert job.error == JobError("price_source_error", "Try later")


def test_delete_removes_the_job() -> None:
    store = JobStore()
    job = store.create(_imported())

    assert store.delete(job.id) is True
    assert store.get(job.id) is None
    assert store.delete(job.id) is False


def test_finished_jobs_expire_one_hour_after_they_finish() -> None:
    clock = Clock()
    store = JobStore(ttl=timedelta(hours=1), now=clock)
    job = store.create(_imported())
    clock.now += timedelta(minutes=30)
    store.fail(job.id, JobError("x", "y"))  # finishes at +30 minutes

    clock.now += timedelta(minutes=59)
    assert store.get(job.id) is not None

    clock.now += timedelta(minutes=2)
    assert store.get(job.id) is None


def test_unfinished_jobs_expire_too() -> None:
    clock = Clock()
    store = JobStore(ttl=timedelta(hours=1), now=clock)
    job = store.create(_imported())

    clock.now += timedelta(hours=1, minutes=1)

    assert store.get(job.id) is None
    assert store.count() == 0


def test_the_store_has_a_size_limit_that_frees_up_as_jobs_expire() -> None:
    clock = Clock()
    store = JobStore(max_jobs=2, ttl=timedelta(hours=1), now=clock)
    store.create(_imported())
    store.create(_imported())

    with pytest.raises(StoreFullError):
        store.create(_imported())

    clock.now += timedelta(hours=2)
    store.create(_imported())  # the old ones have expired
