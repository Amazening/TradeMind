"""The web API (spec section 8).

    POST   /api/analyses        upload a CSV, get an id (202)
    GET    /api/analyses/{id}   status, and the report when done
    DELETE /api/analyses/{id}   delete the upload and report now
    GET    /api/health
    GET    /api/config          whether the site is invite-only, and whether an AI service is used

The file is checked and read as soon as it is uploaded, so a bad file gets an answer straight away.
Getting prices and finding patterns take longer, so they run in the background.

Privacy: everything is held in memory (see jobs.py). Logs hold counts and timings, never trades.
An error reply never repeats anything from the file.
"""

import hmac
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from trademind import __version__
from trademind.analysis import analyse
from trademind.api.jobs import (
    STEP_FINDING_PATTERNS,
    STEP_WRITING_EXPLANATIONS,
    Job,
    JobError,
    JobStore,
    StoreFullError,
)
from trademind.api.ratelimit import RateLimiter
from trademind.core.errors import PriceSourceError, TradeMindError
from trademind.enrichment import PriceSource, enrich
from trademind.ingestion import import_csv
from trademind.reporting import ChatModel, ExplanationCache, explain_report, explain_with_facts

logger = logging.getLogger("trademind.api")

ACCESS_CODE_HEADER = "X-Access-Code"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_BODY_SLACK_BYTES = 64 * 1024  # multipart framing around the file


def create_app(
    *,
    price_source: PriceSource,
    chat_model: ChatModel | None = None,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
    ttl: timedelta = timedelta(hours=1),
    max_jobs: int = 50,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    static_dir: Path | None = None,
    uploads_per_hour: int | None = None,
    access_code: str | None = None,
) -> FastAPI:
    app = FastAPI(
        title="TradeMind",
        version=__version__,
        description="Finds behaviour patterns in a share trading history. Not financial advice.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    store = JobStore(ttl=ttl, max_jobs=max_jobs, now=now)
    limiter = RateLimiter(uploads_per_hour, timedelta(hours=1), now) if uploads_per_hour else None
    explanations = ExplanationCache()  # memory only
    app.state.jobs = store

    def process(job_id: str) -> None:
        imported = store.start(job_id)
        if imported is None:
            return
        started = time.monotonic()
        try:
            history = enrich(imported, price_source)
            store.set_step(job_id, STEP_FINDING_PATTERNS)
            report = analyse(history, now=now())
            store.set_step(job_id, STEP_WRITING_EXPLANATIONS)
            report = (
                explain_report(report, chat_model, explanations)
                if chat_model is not None
                else explain_with_facts(report)
            )
        except TradeMindError as error:
            store.fail(job_id, JobError(error.code, _public_message(error)))
            logger.info("analysis failed: %s", error.code)
            return
        except Exception as error:
            # Only the type is logged: the message could hold values from the file.
            store.fail(
                job_id, JobError("internal_error", "Something went wrong. Please try again.")
            )
            logger.error("analysis crashed: %s", type(error).__name__)
            return
        store.finish(job_id, report)
        logger.info(
            "analysis finished: trades=%d decisions=%d seconds=%.1f",
            report.summary.trades_read,
            report.summary.decisions,
            time.monotonic() - started,
        )

    @app.middleware("http")
    async def limit_body_and_add_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await _guarded(request, call_next, max_upload_bytes, limiter, access_code)
        return _with_headers(response, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> Response:
        # The details are left out: they can repeat what the client sent.
        return _error(422, "invalid_request", "The request was not valid. Send the file as 'file'.")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> Response:
        codes = {404: "not_found", 405: "method_not_allowed"}
        messages = {404: "That was not found.", 405: "That method is not allowed here."}
        return _error(
            error.status_code,
            codes.get(error.status_code, "error"),
            messages.get(error.status_code, "The request could not be completed."),
        )

    @app.post("/api/analyses", status_code=202)
    async def create_analysis(file: UploadFile, background: BackgroundTasks) -> Response:
        name = (file.filename or "").lower()
        if not name.endswith(".csv"):
            return _error(400, "not_a_csv", "Please upload a .csv file.")
        data = await file.read(max_upload_bytes + 1)
        if len(data) > max_upload_bytes:
            return _too_large(max_upload_bytes)

        try:
            imported = import_csv(data)
        except UnicodeDecodeError:
            return _error(400, "not_a_csv", "This file is not a text CSV file.")
        except TradeMindError as error:  # not a supported broker, or no buys and sells
            return _error(422, error.code, str(error))

        try:
            job = store.create(imported)
        except StoreFullError:
            return _error(503, "busy", "TradeMind is busy. Try again in a few minutes.")
        background.add_task(process, job.id)
        return JSONResponse(
            {"id": job.id, "status": job.status},
            status_code=202,
            headers={"Location": f"/api/analyses/{job.id}"},
        )

    @app.get("/api/analyses/{job_id}")
    def get_analysis(job_id: str) -> Response:
        job = store.get(job_id)
        if job is None:
            return _error(404, "not_found", "That analysis was not found. It may have expired.")
        return JSONResponse(_job_json(job))

    @app.delete("/api/analyses/{job_id}")
    def delete_analysis(job_id: str) -> Response:
        if not store.delete(job_id):
            return _error(404, "not_found", "That analysis was not found. It may have expired.")
        return Response(status_code=204)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/config")
    def config() -> dict[str, bool]:
        """What the web page needs to know before it shows the upload form."""
        return {
            "access_code_required": access_code is not None,
            # So the page only says an AI service is used when one is.
            "ai_explanations": chat_model is not None,
        }

    # The built frontend. Mounted last so the API routes above take priority.
    if static_dir is not None and (static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


async def _guarded(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    max_upload_bytes: int,
    limiter: RateLimiter | None,
    access_code: str | None,
) -> Response:
    """Refuses an upload from a visitor who has sent too many, who has no valid access code (when
    the site is invite-only), that is too big, or that does not say its size. This happens before
    the file is read. The rate limit comes first, so wrong guesses at the code are counted."""
    if request.method == "POST":
        if limiter is not None:
            address = request.client.host if request.client else "unknown"
            if not limiter.allow(address):
                response = _error(
                    429, "rate_limited", "Too many uploads. Please try again in a little while."
                )
                response.headers["Retry-After"] = str(limiter.retry_after_seconds(address))
                return response
        if access_code is not None:
            given = request.headers.get(ACCESS_CODE_HEADER)
            if not given:
                return _error(
                    401, "access_code_required", "This site is invite-only. Enter your access code."
                )
            # compare_digest takes the same time however much of the code is right
            if not hmac.compare_digest(given.encode("utf-8"), access_code.encode("utf-8")):
                return _error(
                    401, "access_code_invalid", "That access code is not right. Please check it."
                )
        declared = request.headers.get("content-length")
        if declared is None or not declared.isdigit():
            return _error(411, "length_required", "The upload must say how big it is.")
        if int(declared) > max_upload_bytes + _BODY_SLACK_BYTES:
            return _too_large(max_upload_bytes)
    return await call_next(request)


# Only files from this site. No inline scripts or styles, nothing from other sites, and the page
# cannot be put in a frame.
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


# The page uses none of the browser's device features, so all of them are switched off.
_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


def _with_headers(response: Response, path: str) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
    if not path.startswith("/api/docs"):  # the interactive docs load scripts from a CDN
        response.headers["Content-Security-Policy"] = _CSP
    if path.startswith("/api/analyses"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _job_json(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "step": job.step,
        "report": job.report.model_dump(mode="json") if job.report else None,
        "error": {"code": job.error.code, "message": job.error.message} if job.error else None,
    }


def _public_message(error: TradeMindError) -> str:
    if isinstance(error, PriceSourceError):
        return "We couldn't get market prices. Try again later."
    return str(error)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _too_large(limit: int) -> JSONResponse:
    return _error(
        413, "file_too_large", f"The file is too big. The limit is {limit // 1024 // 1024} MB."
    )
