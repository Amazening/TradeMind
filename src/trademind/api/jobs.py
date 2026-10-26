"""In-memory store of analysis jobs.

Nothing here is written to disk. A job and its report are deleted when the user deletes them, or
one hour after they finish, whichever comes first. The uploaded file is dropped as soon as the
job starts, and only the finished report is kept.
"""

import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from trademind.core.models import ImportResult, Report

Status = Literal["queued", "running", "done", "failed"]

STEP_GETTING_PRICES = "getting_prices"
STEP_FINDING_PATTERNS = "finding_patterns"
STEP_WRITING_EXPLANATIONS = "writing_explanations"


@dataclass(frozen=True)
class JobError:
    code: str
    message: str


@dataclass
class Job:
    id: str
    status: Status
    created_at: datetime
    step: str | None = None
    finished_at: datetime | None = None
    imported: ImportResult | None = field(default=None, repr=False)
    report: Report | None = field(default=None, repr=False)
    error: JobError | None = None


class StoreFullError(Exception):
    """Too many jobs are held at once."""


class JobStore:
    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(hours=1),
        max_jobs: int = 50,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._ttl = ttl
        self._max_jobs = max_jobs
        self._now = now
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, imported: ImportResult) -> Job:
        with self._lock:
            self._purge()
            if len(self._jobs) >= self._max_jobs:
                raise StoreFullError
            # 128 random bits. The id is all that protects a report, so it must not be guessable.
            job = Job(
                id=secrets.token_urlsafe(16),
                status="queued",
                created_at=self._now(),
                imported=imported,
            )
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            self._purge()
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            self._purge()
            return self._jobs.pop(job_id, None) is not None

    def start(self, job_id: str) -> ImportResult | None:
        """Mark the job running and hand over the upload, dropping the store's copy."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # deleted before it started
                return None
            imported, job.imported = job.imported, None
            job.status = "running"
            job.step = STEP_GETTING_PRICES
            return imported

    def set_step(self, job_id: str, step: str) -> None:
        with self._lock:
            if (job := self._jobs.get(job_id)) is not None:
                job.step = step

    def finish(self, job_id: str, report: Report) -> None:
        with self._lock:
            if (job := self._jobs.get(job_id)) is not None:
                job.status, job.step, job.report = "done", None, report
                job.finished_at = self._now()

    def fail(self, job_id: str, error: JobError) -> None:
        with self._lock:
            if (job := self._jobs.get(job_id)) is not None:
                job.status, job.step, job.error = "failed", None, error
                job.imported = None
                job.finished_at = self._now()

    def count(self) -> int:
        with self._lock:
            self._purge()
            return len(self._jobs)

    def _purge(self) -> None:
        """Drop jobs past their lifetime. Call with the lock held."""
        now = self._now()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if now - (job.finished_at or job.created_at) >= self._ttl
        ]
        for job_id in expired:
            del self._jobs[job_id]
