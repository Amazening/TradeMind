from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes import FakePriceSource, daily
from tests.helpers import sharesies_csv, sharesies_row
from trademind import __version__
from trademind.cli import app
from trademind.enrichment import PriceHistory

runner = CliRunner()


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_import_prints_a_summary(tmp_path: Path) -> None:
    file = tmp_path / "trades.csv"
    file.write_text(
        sharesies_csv(
            sharesies_row("T1", "2024-03-04 02:00:00 (UTC)", quantity="10"),
            sharesies_row("T2", "2024-03-04 02:00:05 (UTC)", quantity="5"),
            sharesies_row("T3", "2024-04-01 02:00:00 (UTC)", kind="SELL", quantity="15"),
            sharesies_row("T4", "2024-04-02 02:00:00 (UTC)", kind="DIVIDEND"),
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["import", str(file)])

    assert result.exit_code == 0
    assert "Broker: sharesies" in result.stdout
    assert "Trades read: 3 (buys 2, sells 1, transfers out 0)" in result.stdout
    assert "Decisions: 2 (yours 2, platform 0)" in result.stdout
    assert "Period: 2024-03-04 to 2024-04-01" in result.stdout
    assert "Markets: ASX" in result.stdout
    assert "Skipped rows: 1" in result.stdout
    assert "row 5: Unknown transaction method: DIVIDEND" in result.stdout


def test_import_holdings_lists_open_positions(tmp_path: Path) -> None:
    file = tmp_path / "trades.csv"
    file.write_text(
        sharesies_csv(
            sharesies_row("T1", quantity="10", price="2.00", fee="0"),
            sharesies_row("T2", code="BBB", quantity="4", price="5.00", fee="0"),
            sharesies_row("T3", code="BBB", quantity="4", price="5.00", fee="0", kind="SELL"),
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["import", str(file), "--holdings"])

    assert result.exit_code == 0
    assert "ASX:AAA  10 shares  avg cost 2.0000" in result.stdout
    assert "BBB" not in result.stdout


def test_import_reports_unrecognised_files(tmp_path: Path) -> None:
    file = tmp_path / "other.csv"
    file.write_text("Date,Ticker\n2024-01-01,AAA\n", encoding="utf-8")

    result = runner.invoke(app, ["import", str(file)])

    assert result.exit_code == 1
    assert "unrecognised_broker" in result.output


def test_enrich_prints_coverage_and_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakePriceSource(
        {"ASX:AAA": PriceHistory(currency="AUD", closes=daily(date(2023, 1, 1), 800), splits=[])}
    )
    monkeypatch.setattr("trademind.cli.YahooPriceSource", lambda: fake)
    file = tmp_path / "trades.csv"
    file.write_text(
        sharesies_csv(
            sharesies_row("T1", "2024-03-04 02:00:00 (UTC)", price="2.00"),
            sharesies_row("T2", "2024-03-05 02:00:00 (UTC)", code="GONE", price="1.00"),
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["enrich", str(file), "--no-cache"])

    assert result.exit_code == 0
    assert "Instruments with market prices: 1" in result.stdout
    assert "Instruments without: 1" in result.stdout
    assert "ASX:AAA" in result.stdout
    assert "No market prices for ASX:GONE" in result.stdout


def test_import_missing_file_is_an_error() -> None:
    result = runner.invoke(app, ["import", "does-not-exist.csv"])

    assert result.exit_code != 0
