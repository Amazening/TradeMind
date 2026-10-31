"""Plain English explanations of findings (spec section 7).

Privacy: the model only ever sees a few plain sentences about one finding. It never sees trades,
share names, dates or amounts.

Accuracy: models mix up labels and invent details, so the sentences it receives are written by
code (`facts.py`) and it may only rewrite them. Its reply is then checked. A reply that gives
advice, names a share, or uses a number, time span or number word that is not in the facts is
thrown away. The report is complete without explanations, so a failure here never breaks it.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from trademind.core.errors import ExplainerError
from trademind.core.models import DataNote, Finding, Report
from trademind.reporting.facts import facts_for
from trademind.reporting.models import ChatModel

PROMPT_VERSION = "4"
MAX_ATTEMPTS = 2
MAX_LENGTH = 700

SYSTEM_PROMPT = """\
You rewrite facts about a person's share trading history in friendly, plain English.
Write 2 to 4 short sentences for the person who owns the history.

Rules:
- Use only the facts given. Do not add any other fact, number, date or time span.
- Do not say how long the history is, or when the trades happened, unless a fact says so.
- Use plain New Zealand English and simple words, as if for a 12 year old. Use "you" and "your".
- Do not give advice. Do not tell the person what to do, buy, sell or hold. Do not say what they
  should or should not do.
- Do not guess why they traded. Do not say the result is good or bad.
- Do not name any shares.
- If the pattern was not detected, say so plainly. Do not say they are safe or doing well.
- Include the conclusion fact, so the person knows whether the pattern was found.
- Do not compare the person with other people unless a fact does.
- Do not explain causes. Do not say why something happened.
- Reply with the sentences only. Start with the first sentence: no greeting, no heading, no list
  and no dashes.
"""


@dataclass(frozen=True)
class PatternInfo:
    what: str
    needs: str


PATTERNS: dict[str, PatternInfo] = {
    "overtrading": PatternInfo(
        what=(
            "Overtrading means trading a large share of the portfolio each month. This tool "
            "flags average monthly turnover above 8.8%. Turnover is the smaller of what you "
            "bought and what you sold, so money you add and invest does not count."
        ),
        needs="at least 6 months with a portfolio worth NZ$500 or more, and 10 decisions in them",
    ),
    "disposition_effect": PatternInfo(
        what=(
            "The disposition effect is selling shares that are up sooner than shares that are down."
        ),
        needs="at least 10 sales, with at least 5 winning and 5 losing positions to compare",
    ),
    "run_up_buying": PatternInfo(
        what="Buying after a run-up means buying a share just after its price rose sharply.",
        needs="at least 15 buys that each have a full year of earlier prices",
    ),
}

_ADVICE = re.compile(
    r"\b(should|shouldn't|must|ought|need to|needs to|recommend\w*|advis\w*|suggest\w*|"
    r"consider|try to|avoid|stop|you could|you can)\b",
    re.IGNORECASE,
)
_SHARE_NAME = re.compile(r"\b[A-Z]{2,6}:[A-Z0-9.]{1,6}\b")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[a-z]+")

# Words for spans of time and for amounts. A model uses these to invent details ("over the past
# two and a half years"), so each one must also appear in the facts.
_TIME_STEMS = {
    "recently": "recently",
    "lately": "lately",
    "year": "year",
    "years": "year",
    "month": "month",
    "months": "month",
    "week": "week",
    "weeks": "week",
    "day": "day",
    "days": "day",
    "decade": "decade",
    "decades": "decade",
    "yesterday": "yesterday",
    "today": "today",
}
# Number words. One may be used if its value is one of the facts' numbers ("thirteen" when the
# fact says 13). Vague amounts such as "half" or "twice" are only allowed if the facts use them.
_NUMBER_WORD_VALUES = dict(
    one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11,
    twelve=12, thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17, eighteen=18,
    nineteen=19, twenty=20, thirty=30, forty=40, fifty=50, hundred=100, thousand=1000,
)  # fmt: skip
_VAGUE_AMOUNT_WORDS = frozenset(["half", "twice", "double", "triple", "dozen", "quarter", "third"])
# Claims about causes, motives, other people, or whether something is good or bad. The facts make
# none of these, so a reply that does has invented something. Each word is allowed only if the
# facts use the word themselves.
_CAUSES = "reason reasons caused causes causing factor why"
_MOTIVES = "wanted want wants hoped hope felt feel feeling fear afraid worried worry greed greedy"
_MOTIVES += " panic emotion emotional emotions overconfident impulse impulsive"
_OTHER_PEOPLE = (
    "others other people everyone investor investors average typical usual normal common"
)
_OTHER_PEOPLE += " unusual"
_JUDGEMENT = "good bad poor wrong mistake mistakes smart wise unwise risky safe safely success"
_UNSUPPORTED_CLAIM_WORDS = frozenset(f"{_CAUSES} {_MOTIVES} {_OTHER_PEOPLE} {_JUDGEMENT}".split())
_CHATTY_START = re.compile(r"^\W*(okay|ok|sure|certainly|here|of course|alright|great)\b", re.I)


def build_prompt(finding: Finding) -> str:
    """The user message for one finding. Contains no trades, share names, dates or amounts."""
    info = PATTERNS[finding.pattern]
    confidence = f" (confidence {finding.confidence})" if finding.confidence else ""
    facts = "\n".join(f"- {fact}" for fact in facts_for(finding))
    return (
        f"Pattern: {finding.title}\n"
        f"What it measures: {info.what}\n"
        f"Result: {finding.result.replace('_', ' ')}{confidence}\n"
        f"Facts:\n{facts}"
    )


def check_explanation(text: str, finding: Finding) -> str | None:
    """None if the text is acceptable. Otherwise the reason it is not."""
    if not text.strip():
        return "it was empty"
    if len(text) > MAX_LENGTH:
        return "it was too long"
    if _CHATTY_START.match(text) or "\n\n" in text or re.search(r"^\s*[-*\d]+[.)]?\s", text, re.M):
        return "it was not just the sentences (no greeting, heading or list)"
    if _SHARE_NAME.search(text):
        return "it named a share"
    advice = _ADVICE.search(text)
    if advice:
        return f"it used advice wording ({advice.group(0)!r})"

    facts_text = " ".join(facts_for(finding)).lower()
    allowed = _allowed_numbers(finding, facts_text)
    for match in _NUMBER.findall(text):
        value = float(match.replace(",", ""))
        if not any(abs(value - a) <= max(0.051, abs(a) * 0.005) for a in allowed):
            return f"it used a number that was not given ({match})"

    facts_words = set(_WORD.findall(facts_text))
    facts_stems = {_TIME_STEMS[w] for w in facts_words if w in _TIME_STEMS}
    for word in _WORD.findall(text.lower()):
        if word in _TIME_STEMS and _TIME_STEMS[word] not in facts_stems:
            return f"it mentioned a time span that was not given ({word})"
        if word in _VAGUE_AMOUNT_WORDS and word not in facts_words:
            return f"it used a number word that was not given ({word})"
        if word in _NUMBER_WORD_VALUES and word not in facts_words:
            value = _NUMBER_WORD_VALUES[word]
            if not any(abs(value - a) <= 0.051 for a in allowed):
                return f"it used a number word that was not given ({word})"
        if word in _UNSUPPORTED_CLAIM_WORDS and word not in facts_words:
            return f"it made a claim that was not in the facts ({word})"
    return None


def _allowed_numbers(finding: Finding, facts_text: str) -> list[float]:
    allowed = [float(finding.sample.decisions), float(finding.sample.cases)]
    for value in finding.metrics.values():
        allowed.extend((value, value * 100))
    allowed.extend(float(n.replace(",", "")) for n in _NUMBER.findall(facts_text))
    return allowed


def tool_text(finding: Finding) -> str:
    """The facts, one per line. Written by code, so it is always correct."""
    return "\n".join(facts_for(finding))


def not_enough_data_text(finding: Finding) -> str:
    """Written by code, not by the model. Nothing is sent anywhere."""
    needs = PATTERNS[finding.pattern].needs
    return (
        f"There is not enough data to check this pattern. It needs {needs}. "
        f"Your history has {finding.sample.decisions} decisions that count."
    )


class ExplanationCache:
    """Accepted explanations, keyed by a hash of the model and prompt. In memory, or on disk if
    a directory is given. The files hold the explanation and nothing else."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory
        self._memory: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        if key in self._memory:
            return self._memory[key]
        if self._directory is not None:
            try:
                text = (self._directory / f"{key}.json").read_text(encoding="utf-8")
                return str(json.loads(text)["text"])
            except (OSError, ValueError, KeyError, TypeError):
                return None
        return None

    def set(self, key: str, text: str) -> None:
        self._memory[key] = text
        if self._directory is not None:
            try:
                self._directory.mkdir(parents=True, exist_ok=True)
                (self._directory / f"{key}.json").write_text(
                    json.dumps({"text": text}), encoding="utf-8"
                )
            except OSError:
                pass  # a cache that cannot be written is not an error


def cache_key(model: ChatModel, user_prompt: str) -> str:
    material = "\n".join([PROMPT_VERSION, model.name, SYSTEM_PROMPT, user_prompt])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def explain_with_facts(report: Report) -> Report:
    """A copy of the report with the tool's own explanation on every finding. No model is used."""
    findings = [
        finding.model_copy(
            update={
                "explanation": not_enough_data_text(finding)
                if finding.result == "insufficient_data"
                else tool_text(finding),
                "explained_by": "tool",
            }
        )
        for finding in report.findings
    ]
    return report.model_copy(update={"findings": findings})


def explain_report(
    report: Report, model: ChatModel, cache: ExplanationCache | None = None
) -> Report:
    """A copy of the report with an explanation on every finding.

    The model's rewording is used when it passes the checks. Otherwise the facts are used as they
    are, marked as written by the tool, so the report is always complete.
    """
    cache = cache or ExplanationCache()
    findings: list[Finding] = []
    fallbacks = 0
    service_down = False

    for finding in report.findings:
        if finding.result == "insufficient_data":
            tool_says = not_enough_data_text(finding)
            findings.append(
                finding.model_copy(update={"explanation": tool_says, "explained_by": "tool"})
            )
            continue
        ai_says: str | None = None
        if not service_down:
            try:
                ai_says = _explain_one(finding, model, cache)
            except ExplainerError:
                service_down = True  # do not keep calling a service that is failing
        if ai_says is None:
            fallbacks += 1
            findings.append(
                finding.model_copy(
                    update={"explanation": tool_text(finding), "explained_by": "tool"}
                )
            )
            continue
        findings.append(finding.model_copy(update={"explanation": ai_says, "explained_by": "ai"}))
    return report.model_copy(update={"findings": findings, "data_notes": _notes(report, fallbacks)})


def _explain_one(finding: Finding, model: ChatModel, cache: ExplanationCache) -> str | None:
    """The accepted explanation, or None if the model's replies were all rejected.

    Raises ExplainerError if the service fails.
    """
    prompt = build_prompt(finding)
    key = cache_key(model, prompt)
    cached = cache.get(key)
    if cached is not None:
        return cached

    message = prompt
    for _ in range(MAX_ATTEMPTS):
        text = model.complete(SYSTEM_PROMPT, message).strip()  # may raise ExplainerError
        problem = check_explanation(text, finding)
        if problem is None:
            cache.set(key, text)
            return text
        message = f"{prompt}\n\nYour last reply was rejected because {problem}. Write it again."
    return None


def _notes(report: Report, fallbacks: int) -> list[DataNote]:
    if not fallbacks:
        return report.data_notes
    return [
        *report.data_notes,
        DataNote(
            level="info",
            message=(
                f"The AI explanation could not be used for {fallbacks} findings, so the tool's "
                "own summary is shown instead. The numbers and evidence are not affected."
            ),
        ),
    ]
