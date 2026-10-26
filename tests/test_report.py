from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes import FakePriceSource, daily
from tests.helpers import sharesies_csv, sharesies_row
from tests.scenarios import flat, history_of, nzx_trade
from trademind.analysis import DISCLAIMER, SCHEMA_VERSION, analyse
from trademind.cli import app
from trademind.core.models import DataNote, Report
from trademind.enrichment import PriceHistory
from trademind.reporting import render_text

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


def _report(**kwargs: object) -> Report:
    trades = [
        nzx_trade(1, date(2023, 1, 2), quantity="10"),
        nzx_trade(2, date(2023, 2, 2), quantity="5"),
    ]
    history = history_of(trades, {"NZX:AAA": flat()})
    history.data_notes.append(DataNote(level="info", message="A note"))
    return analyse(history, now=NOW)


def test_report_has_the_summary_period_and_three_findings_in_order() -> None:
    report = _report()

    assert report.schema_version == SCHEMA_VERSION == "1.0"
    assert report.generated_at == NOW
    assert report.broker == "test"
    assert (report.period.start, report.period.end) == (date(2023, 1, 2), date(2023, 2, 2))
    assert report.summary.trades_read == 2
    assert report.summary.decisions == 2
    assert report.summary.user_decisions == 2
    assert report.summary.platform_decisions == 0
    assert report.summary.markets == ["NZX"]
    assert report.summary.instruments == 1
    assert [f.pattern for f in report.findings] == [
        "overtrading",
        "disposition_effect",
        "run_up_buying",
    ]
    assert report.disclaimer == DISCLAIMER
    assert [n.message for n in report.data_notes] == ["A note"]


def test_json_round_trip_keeps_everything() -> None:
    report = _report()

    data = report.model_dump(mode="json")

    assert Report.model_validate(data) == report
    assert data["period"] == {"start": "2023-01-02", "end": "2023-02-02"}
    assert data["findings"][0]["explanation"] is None


def test_every_finding_has_the_fields_the_spec_lists() -> None:
    for finding in _report().model_dump(mode="json")["findings"]:
        assert set(finding) == {
            "pattern",
            "title",
            "result",
            "confidence",
            "sample",
            "metrics",
            "threshold",
            "evidence",
            "notes",
            "explanation",
        }


def test_text_report_shows_results_notes_and_disclaimer() -> None:
    text = render_text(_report())

    assert "Not enough data" in text
    assert "[info] A note" in text
    assert text.endswith(DISCLAIMER)


def test_text_report_shows_an_explanation_when_there_is_one() -> None:
    report = _report()
    report.findings[0].explanation = "You traded a lot."

    assert "You traded a lot." in render_text(report)


@pytest.fixture
def trades_file(tmp_path: Path) -> Path:
    file = tmp_path / "trades.csv"
    file.write_text(
        sharesies_csv(sharesies_row("T1", "2024-03-04 02:00:00 (UTC)", price="2.00")),
        encoding="utf-8",
    )
    return file


def test_cli_analyse_prints_the_json_report(
    trades_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakePriceSource(
        {"ASX:AAA": PriceHistory(currency="AUD", closes=daily(date(2023, 1, 1), 800), splits=[])}
    )
    monkeypatch.setattr("trademind.cli.YahooPriceSource", lambda: fake)

    result = CliRunner().invoke(app, ["analyse", str(trades_file), "--no-cache"])

    assert result.exit_code == 0
    report = Report.model_validate_json(result.stdout)
    assert report.summary.trades_read == 1
    assert len(report.findings) == 3


def test_cli_analyse_text_format(trades_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trademind.cli.YahooPriceSource", lambda: FakePriceSource())

    result = CliRunner().invoke(
        app, ["analyse", str(trades_file), "--format", "text", "--no-cache"]
    )

    assert result.exit_code == 0
    assert "TradeMind report (sharesies)" in result.stdout
    assert DISCLAIMER in result.stdout
