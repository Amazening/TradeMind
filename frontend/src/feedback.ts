import type { Report } from "./types";

export const COMMENT_LIMIT = 1000;

const DAYS_IN_MONTH = 30.44;

function months(report: Report): number {
  const start = Date.parse(report.period.start);
  const end = Date.parse(report.period.end);
  return Math.max(1, Math.round((end - start) / 86_400_000 / DAYS_IN_MONTH));
}

function counts(values: Record<string, number>): string {
  const entries = Object.entries(values);
  return entries.length === 0 ? "none" : entries.map(([label, n]) => `${label} ${n}`).join(", ");
}

/**
 * A short summary of how the file was read, for a tester to send to the developer.
 *
 * It holds counts and labels only. It never holds share names, dates or amounts, and it is
 * built here from the report, so nothing leaves the browser until the person sends it.
 */
export function buildFeedbackText(report: Report, comment: string): string {
  const { summary, diagnostics } = report;
  const lines = [
    "TradeMind feedback",
    `Version: ${report.tool_version} (report format ${report.schema_version})`,
    `Broker: ${report.broker}`,
    `History length: about ${months(report)} months`,
    `Trades read: ${summary.trades_read}`,
    `Decisions: ${summary.user_decisions} by you, ${summary.platform_decisions} by the platform`,
    `Shares: ${summary.instruments}. Markets: ${summary.markets.join(", ")}`,
  ];

  if (diagnostics) {
    lines.push(
      `Rows in the file: ${diagnostics.rows_read}. Skipped: ${diagnostics.rows_skipped}`,
      `Why rows were skipped: ${counts(diagnostics.skipped_reasons)}`,
      `Transaction method: ${counts(diagnostics.transaction_methods)}`,
      `Initiated by: ${counts(diagnostics.initiated_by)}`,
      `Buys worth under 1 in their own currency, by who started them: ${counts(diagnostics.small_buys)}`,
      `Shares without market prices: ${diagnostics.shares_without_market_prices}`,
      `Shares adjusted for splits: ${diagnostics.shares_adjusted_for_splits}`,
    );
  }

  lines.push("Results:");
  for (const finding of report.findings) {
    lines.push(
      `- ${finding.title}: ${finding.result.replaceAll("_", " ")}, confidence ${finding.confidence ?? "none"}, ` +
        `${finding.sample.decisions} decisions, ${finding.sample.cases} cases`,
    );
  }

  const warnings = report.data_notes.filter((note) => note.level === "warning").length;
  const infos = report.data_notes.length - warnings;
  lines.push(`Notes about the data: ${warnings} warnings, ${infos} information`);

  const trimmed = comment.trim().slice(0, COMMENT_LIMIT);
  lines.push("", "Comment from the person who tried it:", trimmed === "" ? "(none)" : trimmed);
  return lines.join("\n");
}
