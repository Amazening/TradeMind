from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tests.fakes import FakeChatModel
from trademind.core.errors import ExplainerError
from trademind.core.models import (
    DataNote,
    Evidence,
    Finding,
    FindingSample,
    Report,
    ReportPeriod,
    ReportSummary,
)
from trademind.reporting.explain import (
    SYSTEM_PROMPT,
    ExplanationCache,
    build_prompt,
    check_explanation,
    explain_report,
    not_enough_data_text,
    tool_text,
)

GOOD = "You traded about 14% of your portfolio each month. That is based on 36 months of trades."


def _overtrading() -> Finding:
    return Finding(
        pattern="overtrading",
        title="Trading a large share of the portfolio",
        result="detected",
        confidence="high",
        sample=FindingSample(decisions=120, cases=36),
        metrics={
            "avg_monthly_turnover_pct": 14.04,
            "annualised_turnover_pct": 168.48,
            "months": 36.0,
        },
        threshold="Average monthly turnover above 8.8%",
        evidence=[
            Evidence(decision_id=None, note="March 2024: 96.5% of the portfolio traded"),
            Evidence(decision_id="d-9", note="Sold ASX:ABC on 2024-03-14"),
        ],
        notes=["3 shares without market prices were left out: ASX:XYZ."],
    )


def _disposition() -> Finding:
    return Finding(
        pattern="disposition_effect",
        title="Selling winners sooner than losers",
        result="not_detected",
        confidence="low",
        sample=FindingSample(decisions=12, cases=100),
        metrics={"pgr": 0.1, "plr": 0.12, "score": -0.02, "p_value": 0.7},
        threshold="Share of gains sold above share of losses sold, with p below 0.05",
        evidence=[],
        notes=[],
    )


def _runup_insufficient() -> Finding:
    return Finding(
        pattern="run_up_buying",
        title="Buying after a sharp rise",
        result="insufficient_data",
        confidence=None,
        sample=FindingSample(decisions=4, cases=4),
        metrics={},
        threshold="Share of buys after a top-10% rise above 10%, with p below 0.05",
        evidence=[],
        notes=[],
    )


def _report() -> Report:
    return Report(
        schema_version="1.1",
        tool_version="0.2.0",
        generated_at=datetime(2026, 10, 26, tzinfo=UTC),
        broker="sharesies",
        period=ReportPeriod(start=date(2021, 6, 28), end=date(2026, 10, 21)),
        summary=ReportSummary(
            trades_read=10,
            decisions=8,
            user_decisions=8,
            platform_decisions=0,
            markets=["ASX"],
            instruments=2,
        ),
        findings=[_overtrading(), _disposition(), _runup_insufficient()],
        data_notes=[DataNote(level="info", message="Existing note")],
        disclaimer="Not advice.",
    )


# --- the prompt ---------------------------------------------------------------------------


def test_prompt_has_the_numbers_and_no_share_names_or_dates() -> None:
    prompt = build_prompt(_overtrading())

    assert "Trading a large share of the portfolio" in prompt
    assert "Result: detected (confidence high)" in prompt
    assert "- This is based on 120 of your own buy and sell decisions." in prompt
    assert "about 14% of your portfolio" in prompt
    assert "about 168%" in prompt
    assert "so this pattern was found" in prompt
    assert "ASX" not in prompt
    assert "ABC" not in prompt
    assert "XYZ" not in prompt
    assert "2024" not in prompt  # evidence and notes are never sent
    assert "14.04" not in prompt  # raw metrics are never sent


def test_prompt_leaves_out_confidence_when_there_is_none() -> None:
    finding = _overtrading().model_copy(update={"confidence": None})

    assert "Result: detected\n" in build_prompt(finding)


def test_the_conclusion_follows_the_result_not_the_p_value() -> None:
    found = build_prompt(_overtrading())
    not_found = build_prompt(_overtrading().model_copy(update={"result": "not_detected"}))

    assert "so this pattern was found" in found
    assert "so this pattern was not found" in not_found
    assert "p_value" not in not_found


def test_system_prompt_forbids_advice() -> None:
    assert "Do not give advice" in SYSTEM_PROMPT
    assert "Do not name any shares" in SYSTEM_PROMPT


# --- checking the reply -------------------------------------------------------------------


def test_good_reply_is_accepted() -> None:
    assert check_explanation(GOOD, _overtrading()) is None


def test_numbers_may_be_rounded_or_written_as_percentages() -> None:
    finding = _disposition()
    text = "You sold 10% of your winning positions and 12% of your losing ones, from 100 cases."

    assert check_explanation(text, finding) is None


def test_numbers_from_the_rule_and_description_are_allowed() -> None:
    text = "The rule looks for more than 8.8% a month, and you did 14.04%. That is 120 decisions."

    assert check_explanation(text, _overtrading()) is None


@pytest.mark.parametrize(
    "text",
    [
        "You should trade less often.",
        "I recommend you slow down.",
        "Consider selling less often.",
        "Try to avoid trading so much.",
        "You could hold for longer.",
    ],
)
def test_advice_is_rejected(text: str) -> None:
    problem = check_explanation(text, _overtrading())

    assert problem is not None
    assert "advice" in problem


def test_a_share_name_is_rejected() -> None:
    problem = check_explanation("You sold ASX:ABC a lot, 36 months in all.", _overtrading())

    assert problem == "it named a share"


def test_a_number_that_was_not_given_is_rejected() -> None:
    problem = check_explanation("You traded 99% of your portfolio each month.", _overtrading())

    assert problem is not None
    assert "99" in problem


def test_empty_and_very_long_replies_are_rejected() -> None:
    assert check_explanation("  ", _overtrading()) == "it was empty"
    assert check_explanation("word " * 200, _overtrading()) == "it was too long"


@pytest.mark.parametrize(
    "text",
    [
        "Okay, here is what we found. You traded 14% of your portfolio each month.",
        "Here you go. You traded 14% of your portfolio each month.",
        "You traded 14% each month.\n\nThat is based on 120 decisions.",
        "- You traded 14% each month.\n- That is based on 120 decisions.",
    ],
)
def test_greetings_and_lists_are_rejected(text: str) -> None:
    problem = check_explanation(text, _overtrading())

    assert problem is not None
    assert "no greeting" in problem


def test_time_spans_and_number_words_that_were_not_given_are_rejected() -> None:
    finding = _disposition()  # its facts mention no time at all

    assert "time span" in (check_explanation("You sold winners recently.", finding) or "")
    assert "time span" in (check_explanation("You sold winners this year.", finding) or "")
    assert "number word" in (check_explanation("You sold about a third of winners.", finding) or "")
    assert "number word" in (check_explanation("Twice as many were sold.", finding) or "")


def test_a_number_word_is_allowed_when_its_number_is_a_fact() -> None:
    # Models often write "thirteen" for 13. That is the same fact, so it is fine.
    finding = _overtrading().model_copy(update={"sample": FindingSample(decisions=13, cases=36)})

    assert check_explanation("Thirteen of your decisions were checked.", finding) is None
    problem = check_explanation("Fifteen of your decisions were checked.", finding)
    assert problem is not None
    assert "number word" in problem


def test_a_time_span_in_the_facts_is_allowed() -> None:
    # The overtrading facts talk about months and a year.
    text = "Over 36 months you traded about 14% of your portfolio each month."

    assert check_explanation(text, _overtrading()) is None


@pytest.mark.parametrize(
    "text",
    [
        "You traded a lot because you wanted quick gains, based on 120 decisions.",
        "That is the reason for your 14% figure.",
        "That is higher than most people, at 14%.",
        "That is higher than the average investor, at 14%.",
        "This is normal for 120 decisions.",
        "You felt sure about it and traded 14% each month.",
        "That is a good result, at 14%.",
        "You were greedy, trading 14% each month.",
    ],
)
def test_invented_causes_motives_and_comparisons_are_rejected(text: str) -> None:
    assert check_explanation(text, _overtrading()) is not None


def test_not_enough_data_text_is_written_by_code() -> None:
    text = not_enough_data_text(_runup_insufficient())

    assert "not enough data" in text
    assert "at least 15 buys" in text
    assert "4 decisions" in text


# --- explaining a report ------------------------------------------------------------------


def test_findings_get_explanations_and_the_original_report_is_unchanged() -> None:
    report = _report()
    model = FakeChatModel([GOOD, "You sold 10% of winners and 12% of losers, from 100 cases."])

    result = explain_report(report, model)

    assert result.findings[0].explanation == GOOD
    assert result.findings[0].explained_by == "ai"
    assert result.findings[1].explanation is not None
    assert result.findings[1].explained_by == "ai"
    assert report.findings[0].explanation is None
    assert report.findings[0].explained_by is None
    assert result.data_notes == report.data_notes


def test_insufficient_data_is_explained_without_calling_the_model() -> None:
    model = FakeChatModel([GOOD, "You sold 10% of winners and 12% of losers, from 100 cases."])

    result = explain_report(_report(), model)

    assert len(model.calls) == 2  # overtrading and disposition only
    assert result.findings[2].explanation == not_enough_data_text(_runup_insufficient())
    assert result.findings[2].explained_by == "tool"


def test_a_rejected_reply_is_retried_once_with_the_reason() -> None:
    model = FakeChatModel(["You should trade less.", GOOD])
    report = _report().model_copy(update={"findings": [_overtrading()]})

    result = explain_report(report, model)

    assert result.findings[0].explanation == GOOD
    assert len(model.calls) == 2
    assert "rejected because it used advice wording" in model.calls[1][1]


def test_two_rejected_replies_fall_back_to_the_tools_own_text_with_a_note() -> None:
    model = FakeChatModel(["You should trade less."])
    report = _report().model_copy(update={"findings": [_overtrading()]})

    result = explain_report(report, model)

    assert result.findings[0].explanation == tool_text(_overtrading())
    assert result.findings[0].explained_by == "tool"
    assert len(model.calls) == 2
    assert "could not be used for 1 findings" in result.data_notes[-1].message


def test_a_service_failure_stops_further_calls_and_the_report_stays_complete() -> None:
    model = FakeChatModel([ExplainerError("Groq rate limit reached.")])

    result = explain_report(_report(), model)

    assert len(model.calls) == 1
    for finding in result.findings:
        assert finding.explanation
        assert finding.explained_by == "tool"
    assert result.findings[0].explanation == tool_text(_overtrading())
    assert "could not be used for 2 findings" in result.data_notes[-1].message
    assert result.findings[0].metrics == _overtrading().metrics


def test_the_tools_own_text_passes_its_own_checks() -> None:
    # The fallback must never contain advice, a share name or a number that is not a fact.
    for finding in (_overtrading(), _disposition()):
        assert check_explanation(tool_text(finding), finding) is None


def test_accepted_explanations_are_cached_in_memory() -> None:
    model = FakeChatModel([GOOD])
    cache = ExplanationCache()
    report = _report().model_copy(update={"findings": [_overtrading()]})

    explain_report(report, model, cache)
    second = explain_report(report, model, cache)

    assert len(model.calls) == 1
    assert second.findings[0].explanation == GOOD


def test_the_disk_cache_survives_a_new_cache_object(tmp_path: Path) -> None:
    model = FakeChatModel([GOOD])
    report = _report().model_copy(update={"findings": [_overtrading()]})
    explain_report(report, model, ExplanationCache(tmp_path))

    second = explain_report(report, model, ExplanationCache(tmp_path))

    assert len(model.calls) == 1
    assert second.findings[0].explanation == GOOD
    [file] = tmp_path.glob("*.json")
    assert GOOD in file.read_text(encoding="utf-8")


def test_rejected_replies_are_not_cached() -> None:
    cache = ExplanationCache()
    report = _report().model_copy(update={"findings": [_overtrading()]})
    explain_report(report, FakeChatModel(["You should trade less."]), cache)

    model = FakeChatModel([GOOD])
    result = explain_report(report, model, cache)

    assert len(model.calls) == 1
    assert result.findings[0].explanation == GOOD


def test_a_different_finding_is_not_served_from_the_cache() -> None:
    model = FakeChatModel([GOOD])
    cache = ExplanationCache()
    first = _overtrading()
    other = first.model_copy(update={"metrics": {**first.metrics, "months": 40.0}})

    explain_report(_report().model_copy(update={"findings": [first]}), model, cache)
    explain_report(_report().model_copy(update={"findings": [other]}), model, cache)

    assert len(model.calls) == 2
