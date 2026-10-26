"""The facts behind each finding, as plain sentences written by code.

A language model is bad at keeping numbers and labels straight, and at reading statistics such as
p-values. So it is never given raw metrics. It gets these sentences, including the conclusion,
which are always correct, and may only rewrite them. The sentences contain no trades, share names,
dates or amounts.
"""

from trademind.core.models import Finding


def facts_for(finding: Finding) -> list[str]:
    builder = _BUILDERS.get(finding.pattern)
    return builder(finding) if builder else []


def _percent(value: float) -> str:
    """14.04 -> '14%', 7.3 -> '7.3%'. Under 10 keeps one decimal."""
    return f"{value:.1f}%" if abs(value) < 10 else f"{value:.0f}%"


def _conclusion(finding: Finding, found: str, not_found: str) -> str:
    return found if finding.result == "detected" else not_found


def _overtrading(finding: Finding) -> list[str]:
    m = finding.metrics
    return [
        f"The tool compared {m['months']:.0f} months in which your portfolio was worth at least "
        "NZ$500.",
        f"Each month you traded about {_percent(m['avg_monthly_turnover_pct'])} of your "
        f"portfolio on average. Over a year that adds up to about "
        f"{_percent(m['annualised_turnover_pct'])}.",
        "A large study of US households called more than 8.8% a month frequent trading.",
        f"This is based on {finding.sample.decisions} of your own buy and sell decisions.",
        _conclusion(
            finding,
            "Your figure is more than 8.8% a month, so this pattern was found.",
            "Your figure is not more than 8.8% a month, so this pattern was not found.",
        ),
    ]


def _disposition(finding: Finding) -> list[str]:
    m = finding.metrics
    return [
        f"This is based on {finding.sample.decisions} times you sold a share.",
        f"On those days, you sold {_percent(m['pgr'] * 100)} of the winning positions you held "
        f"and {_percent(m['plr'] * 100)} of the losing positions you held.",
        _conclusion(
            finding,
            "The gap in favour of selling winners is bigger than luck would explain, so this "
            "pattern was found.",
            "You did not sell winners more often than losers by more than luck would explain, "
            "so this pattern was not found.",
        ),
    ]


def _run_up(finding: Finding) -> list[str]:
    m = finding.metrics
    return [
        f"This is based on {finding.sample.decisions} of your buys that had a full year of "
        "earlier prices.",
        f"{m['run_up_buys']:.0f} of them ({_percent(m['run_up_share'] * 100)}) came right after "
        "a big rise in the share's price.",
        "A big rise means one in the top 10% of that share's rises over the year before.",
        "By luck alone, about 10% of buys would come after a big rise.",
        _conclusion(
            finding,
            "Your share is more than luck would explain, so this pattern was found.",
            "Your share is not more than luck would explain, so this pattern was not found.",
        ),
    ]


_BUILDERS = {
    "overtrading": _overtrading,
    "disposition_effect": _disposition,
    "run_up_buying": _run_up,
}
