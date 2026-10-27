"""The example report on the website. It must stay made up, valid, and in step with its script."""

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from trademind.core.models import Report

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "frontend" / "public" / "sample-report.json"
SCRIPT = ROOT / "scripts" / "make_sample_report.py"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_sample_report", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sample() -> Report:
    return Report.model_validate_json(SAMPLE.read_text(encoding="utf-8"))


def test_the_example_is_a_valid_report(sample: Report) -> None:
    assert [f.pattern for f in sample.findings] == [
        "overtrading",
        "disposition_effect",
        "run_up_buying",
    ]
    assert sample.disclaimer


def test_the_example_shows_a_mix_of_results(sample: Report) -> None:
    results = {f.result for f in sample.findings}

    assert "detected" in results
    assert "not_detected" in results


def test_every_finding_has_an_explanation(sample: Report) -> None:
    assert all(f.explanation and f.explained_by for f in sample.findings)


def test_the_example_only_names_made_up_shares(sample: Report) -> None:
    text = SAMPLE.read_text(encoding="utf-8")

    symbols = set(re.findall(r"\b(?:ASX|NZX|NYSE|NASDAQ):([A-Z0-9.]+)", text))

    assert symbols
    assert all(symbol.startswith("DEMO") for symbol in symbols)


def test_the_example_carries_no_marker_of_real_data() -> None:
    text = SAMPLE.read_text(encoding="utf-8")

    assert "data/private" not in text
    assert "Mazen" not in text


def test_the_script_still_makes_the_same_findings_as_the_committed_file(sample: Report) -> None:
    rebuilt = _script().build_report(None)

    assert [f.result for f in rebuilt.findings] == [f.result for f in sample.findings]
    assert [f.metrics for f in rebuilt.findings] == [f.metrics for f in sample.findings]
    assert rebuilt.summary == sample.summary
    assert rebuilt.period == sample.period


def test_the_file_is_plain_json() -> None:
    assert isinstance(json.loads(SAMPLE.read_text(encoding="utf-8")), dict)
