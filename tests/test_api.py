import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from tests.fakes import FakeChatModel, FakePriceSource, daily
from tests.helpers import SHARESIES_HEADER, sharesies_csv, sharesies_row
from trademind.api import create_app
from trademind.core.errors import PriceSourceError
from trademind.core.models import Report
from trademind.enrichment import PriceHistory

CSV = sharesies_csv(sharesies_row("T1", "2024-03-04 02:00:00 (UTC)", price="2.00"))
PRICES = {"ASX:AAA": PriceHistory(currency="AUD", closes=daily(date(2023, 1, 1), 900), splits=[])}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _client(source: Any = None, **kwargs: Any) -> TestClient:
    app: FastAPI = create_app(price_source=source or FakePriceSource(PRICES), **kwargs)
    return TestClient(app)


def _upload(client: TestClient, content: str | bytes = CSV, name: str = "trades.csv") -> Response:
    response: Response = client.post("/api/analyses", files={"file": (name, content, "text/csv")})
    return response


def _error(response: Response) -> dict[str, str]:
    body: dict[str, dict[str, str]] = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    return body["error"]


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield _client()


# --- the happy path -----------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_then_fetch_the_report(client: TestClient) -> None:
    created = _upload(client)

    assert created.status_code == 202
    job_id = created.json()["id"]
    assert created.json()["status"] == "queued"
    assert created.headers["location"] == f"/api/analyses/{job_id}"

    fetched = client.get(f"/api/analyses/{job_id}")

    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == job_id
    assert body["status"] == "done"
    assert body["step"] is None
    assert body["error"] is None
    report = Report.model_validate(body["report"])
    assert report.summary.trades_read == 1
    assert [f.pattern for f in report.findings] == [
        "overtrading",
        "disposition_effect",
        "run_up_buying",
    ]


def test_every_finding_has_an_explanation_even_without_an_ai_model(client: TestClient) -> None:
    job_id = _upload(client).json()["id"]

    report = Report.model_validate(client.get(f"/api/analyses/{job_id}").json()["report"])

    for finding in report.findings:
        assert finding.explanation
        assert finding.explained_by == "tool"


def test_the_ai_model_is_not_called_when_there_is_not_enough_data() -> None:
    model = FakeChatModel(["unused"])
    client = _client(chat_model=model)

    _upload(client)

    assert model.calls == []


def test_the_report_is_never_cached(client: TestClient) -> None:
    created = _upload(client)
    fetched = client.get(f"/api/analyses/{created.json()['id']}")

    assert created.headers["cache-control"] == "no-store"
    assert fetched.headers["cache-control"] == "no-store"


def test_the_api_docs_list_every_endpoint(client: TestClient) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]

    assert set(paths["/api/analyses"]) == {"post"}
    assert set(paths["/api/analyses/{job_id}"]) == {"get", "delete"}
    assert "/api/health" in paths
    assert client.get("/api/docs").status_code == 200


# --- rate limiting ------------------------------------------------------------------------


def test_a_visitor_who_uploads_too_often_is_slowed_down() -> None:
    client = _client(uploads_per_hour=2)

    assert _upload(client).status_code == 202
    assert _upload(client).status_code == 202
    response = _upload(client)

    assert response.status_code == 429
    assert _error(response)["code"] == "rate_limited"
    assert int(response.headers["retry-after"]) > 0


def test_the_limit_only_counts_uploads() -> None:
    client = _client(uploads_per_hour=1)
    job_id = _upload(client).json()["id"]

    for _ in range(5):
        assert client.get(f"/api/analyses/{job_id}").status_code == 200
        assert client.get("/api/health").status_code == 200


def test_the_allowance_comes_back_after_an_hour() -> None:
    clock = Clock()
    client = _client(uploads_per_hour=1, now=clock)
    _upload(client)
    assert _upload(client).status_code == 429

    clock.now += timedelta(hours=1, minutes=1)

    assert _upload(client).status_code == 202


def test_there_is_no_limit_unless_one_is_set() -> None:
    client = _client(max_jobs=100)

    assert all(_upload(client).status_code == 202 for _ in range(15))


def test_refused_uploads_still_count_and_still_carry_security_headers() -> None:
    client = _client(uploads_per_hour=1)
    _upload(client)

    response = _upload(client)

    assert response.status_code == 429
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


# --- invite-only --------------------------------------------------------------------------


def _upload_with_code(client: TestClient, code: str | None) -> Response:
    headers = {} if code is None else {"X-Access-Code": code}
    response: Response = client.post(
        "/api/analyses", files={"file": ("trades.csv", CSV, "text/csv")}, headers=headers
    )
    return response


def test_an_invite_only_site_refuses_an_upload_with_no_code() -> None:
    client = _client(access_code="open-sesame")

    response = _upload_with_code(client, None)

    assert response.status_code == 401
    assert _error(response)["code"] == "access_code_required"


def test_an_invite_only_site_refuses_a_wrong_code_and_does_not_echo_it() -> None:
    client = _client(access_code="open-sesame")

    response = _upload_with_code(client, "guess-123")

    assert response.status_code == 401
    assert _error(response)["code"] == "access_code_invalid"
    assert "guess-123" not in response.text
    assert "open-sesame" not in response.text


def test_the_right_code_lets_an_upload_through() -> None:
    client = _client(access_code="open-sesame")

    response = _upload_with_code(client, "open-sesame")

    assert response.status_code == 202
    job_id = response.json()["id"]
    assert client.get(f"/api/analyses/{job_id}").json()["status"] == "done"


def test_a_code_that_only_starts_right_is_refused() -> None:
    client = _client(access_code="open-sesame")

    assert _upload_with_code(client, "open-sesam").status_code == 401
    assert _upload_with_code(client, "open-sesame!").status_code == 401


def test_the_code_is_only_needed_to_upload() -> None:
    client = _client(access_code="open-sesame")
    job_id = _upload_with_code(client, "open-sesame").json()["id"]

    assert client.get(f"/api/analyses/{job_id}").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.delete(f"/api/analyses/{job_id}").status_code == 204


def test_without_a_configured_code_no_code_is_needed(client: TestClient) -> None:
    assert _upload_with_code(client, None).status_code == 202


def test_the_page_can_ask_whether_a_code_is_needed() -> None:
    assert _client(access_code="x").get("/api/config").json() == {"access_code_required": True}
    assert _client().get("/api/config").json() == {"access_code_required": False}


def test_wrong_guesses_count_towards_the_rate_limit() -> None:
    client = _client(access_code="open-sesame", uploads_per_hour=3)

    codes = [_upload_with_code(client, f"guess-{n}").status_code for n in range(4)]

    assert codes == [401, 401, 401, 429]


# --- the frontend and security headers ----------------------------------------------------


@pytest.fixture
def site(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>TradeMind</title>", encoding="utf-8"
    )
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return tmp_path


def test_the_built_frontend_is_served_from_the_root(site: Path) -> None:
    client = _client(static_dir=site)

    page = client.get("/")
    script = client.get("/assets/app.js")

    assert page.status_code == 200
    assert "<title>TradeMind</title>" in page.text
    assert script.status_code == 200
    assert "console.log" in script.text


def test_the_api_still_wins_over_the_frontend(site: Path) -> None:
    client = _client(static_dir=site)

    assert client.get("/api/health").json()["status"] == "ok"
    assert _upload(client).status_code == 202


def test_a_missing_file_is_a_json_not_found(site: Path) -> None:
    response = _client(static_dir=site).get("/assets/missing.js")

    assert response.status_code == 404
    assert _error(response)["code"] == "not_found"


def test_files_outside_the_frontend_folder_cannot_be_read(
    site: Path, tmp_path_factory: Any
) -> None:
    secret = tmp_path_factory.mktemp("elsewhere") / "secret.txt"
    secret.write_text("hunter2", encoding="utf-8")
    client = _client(static_dir=site)

    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        assert "hunter2" not in client.get(path).text


def test_there_is_no_frontend_when_the_folder_has_no_index(tmp_path: Path) -> None:
    client = _client(static_dir=tmp_path)

    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_responses_carry_security_headers(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy


def test_refused_uploads_carry_the_headers_too() -> None:
    client = _client(max_upload_bytes=1000)

    response = _upload(client, "x" * 200_000)

    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_the_interactive_docs_are_not_blocked_by_the_policy(client: TestClient) -> None:
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


# --- deleting and expiring ----------------------------------------------------------------


def test_delete_removes_the_analysis_straight_away(client: TestClient) -> None:
    job_id = _upload(client).json()["id"]

    assert client.delete(f"/api/analyses/{job_id}").status_code == 204
    assert client.get(f"/api/analyses/{job_id}").status_code == 404
    assert client.delete(f"/api/analyses/{job_id}").status_code == 404


def test_an_analysis_disappears_an_hour_after_it_finishes() -> None:
    clock = Clock()
    client = _client(now=clock)
    job_id = _upload(client).json()["id"]

    clock.now += timedelta(minutes=59)
    assert client.get(f"/api/analyses/{job_id}").status_code == 200

    clock.now += timedelta(minutes=2)
    response = client.get(f"/api/analyses/{job_id}")
    assert response.status_code == 404
    assert _error(response)["code"] == "not_found"


def test_the_server_refuses_new_work_when_it_holds_too_many() -> None:
    client = _client(max_jobs=1)
    _upload(client)

    response = _upload(client)

    assert response.status_code == 503
    assert _error(response)["code"] == "busy"


# --- bad uploads --------------------------------------------------------------------------


def test_a_file_that_is_not_named_csv_is_rejected(client: TestClient) -> None:
    response = _upload(client, name="trades.txt")

    assert response.status_code == 400
    assert _error(response)["code"] == "not_a_csv"


def test_a_file_that_is_not_text_is_rejected(client: TestClient) -> None:
    response = _upload(client, b"\xff\xfe\xfa\x00\x80")

    assert response.status_code == 400
    assert _error(response)["code"] == "not_a_csv"


def test_a_csv_from_an_unknown_broker_is_rejected_without_echoing_it(client: TestClient) -> None:
    response = _upload(client, "Ticker,Shares,SecretColumn\nAAA,5,hunter2\n")

    assert response.status_code == 422
    error = _error(response)
    assert error["code"] == "unrecognised_broker"
    assert "sharesies" in error["message"]
    assert "hunter2" not in response.text
    assert "SecretColumn" not in response.text


def test_an_empty_file_is_rejected(client: TestClient) -> None:
    response = _upload(client, "")

    assert response.status_code == 422
    assert _error(response)["code"] == "unrecognised_broker"


def test_a_file_with_no_buys_or_sells_is_rejected(client: TestClient) -> None:
    response = _upload(client, SHARESIES_HEADER + "\n")

    assert response.status_code == 422
    assert _error(response)["code"] == "no_trades_found"


def test_a_file_just_over_the_limit_is_rejected() -> None:
    client = _client(max_upload_bytes=1000)

    response = _upload(client, CSV + " " * 1000)

    assert response.status_code == 413
    assert _error(response)["code"] == "file_too_large"


def test_a_much_bigger_upload_is_refused_before_it_is_read() -> None:
    client = _client(max_upload_bytes=1000)

    response = _upload(client, "x" * 200_000)

    assert response.status_code == 413
    assert _error(response)["code"] == "file_too_large"


def test_an_upload_that_does_not_say_its_size_is_refused(client: TestClient) -> None:
    response = client.post("/api/analyses", content=(chunk for chunk in [b"a,b\n"]))

    assert response.status_code == 411
    assert _error(response)["code"] == "length_required"


def test_a_request_without_the_file_field_is_rejected(client: TestClient) -> None:
    response = client.post("/api/analyses", files={"wrong": ("trades.csv", CSV, "text/csv")})

    assert response.status_code == 422
    assert _error(response)["code"] == "invalid_request"


def test_unknown_routes_and_methods_use_the_same_error_shape(client: TestClient) -> None:
    assert _error(client.get("/api/analyses/does-not-exist"))["code"] == "not_found"
    assert _error(client.get("/api/nothing-here"))["code"] == "not_found"
    assert _error(client.get("/api/analyses"))["code"] == "method_not_allowed"


# --- things going wrong inside the job ----------------------------------------------------


class _BrokenPrices(FakePriceSource):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def fetch_prices(self, market: str, symbol: str, start: date, end: date) -> PriceHistory | None:
        raise self._error


def test_a_market_data_outage_is_reported_without_internal_details() -> None:
    client = _client(_BrokenPrices(PriceSourceError("HTTP 503 from upstream-host.example")))
    job_id = _upload(client).json()["id"]

    body = client.get(f"/api/analyses/{job_id}").json()

    assert body["status"] == "failed"
    assert body["report"] is None
    assert body["error"]["code"] == "price_source_error"
    assert body["error"]["message"] == "We couldn't get market prices. Try again later."
    assert "upstream-host" not in str(body)


def test_an_unexpected_crash_is_generic_and_leaks_nothing(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="trademind.api")
    client = _client(_BrokenPrices(RuntimeError("ZZQQ-secret-value from the file")))
    job_id = _upload(client).json()["id"]

    body = client.get(f"/api/analyses/{job_id}").json()

    assert body["status"] == "failed"
    assert body["error"]["code"] == "internal_error"
    assert "ZZQQ" not in str(body)
    assert "ZZQQ" not in caplog.text
    assert "RuntimeError" in caplog.text  # only the type is logged


def test_logs_hold_counts_and_timings_but_no_trade_data(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client = _client()
    row = sharesies_row("T1", "2024-03-04 02:00:00 (UTC)", code="ZZQQ", price="987.65")

    _upload(client, sharesies_csv(row))

    assert "analysis finished: trades=1 decisions=1" in caplog.text
    assert "ZZQQ" not in caplog.text
    assert "987.65" not in caplog.text
    assert "T1" not in caplog.text
