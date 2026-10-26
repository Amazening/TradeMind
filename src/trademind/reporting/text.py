"""Plain text version of a report, for the command line."""

from trademind.core.models import Finding, Report

_RESULT_WORDS = {
    "detected": "Detected",
    "not_detected": "Not detected",
    "insufficient_data": "Not enough data",
}


def render_text(report: Report) -> str:
    summary = report.summary
    lines = [
        f"TradeMind report ({report.broker})",
        f"Period: {report.period.start} to {report.period.end}",
        f"Trades: {summary.trades_read}   Decisions: {summary.decisions} "
        f"(yours {summary.user_decisions}, platform {summary.platform_decisions})",
        f"Markets: {', '.join(summary.markets)}   Instruments: {summary.instruments}",
        "",
    ]
    for finding in report.findings:
        lines.extend(_finding_lines(finding))
        lines.append("")
    if report.data_notes:
        lines.append("Data notes:")
        lines.extend(f"  [{note.level}] {note.message}" for note in report.data_notes)
        lines.append("")
    lines.append(report.disclaimer)
    return "\n".join(lines)


def _finding_lines(finding: Finding) -> list[str]:
    confidence = f", confidence {finding.confidence}" if finding.confidence else ""
    lines = [
        f"{finding.title}: {_RESULT_WORDS[finding.result]}{confidence}",
        f"  Rule: {finding.threshold}",
        f"  Based on {finding.sample.decisions} decisions, {finding.sample.cases} cases",
    ]
    if finding.metrics:
        lines.append(
            "  " + ", ".join(f"{name} {value:g}" for name, value in finding.metrics.items())
        )
    if finding.explanation:
        lines.append(f"  {finding.explanation}")
    lines.extend(f"  Note: {note}" for note in finding.notes)
    if finding.evidence:
        lines.append("  Evidence:")
        lines.extend(f"    {item.note}" for item in finding.evidence)
    return lines
