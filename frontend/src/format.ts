import type { Confidence, Finding, PatternResult } from "./types";

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

export const RESULT_LABEL: Record<PatternResult, string> = {
  detected: "Found",
  not_detected: "Not found",
  insufficient_data: "Not enough data",
};

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "2024-03-04" -> "4 March 2024". The date has no time zone, so it is not shifted. */
export function formatDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return new Intl.DateTimeFormat("en-NZ", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

/** A value already in percent units: 14.04 -> "14%", 7.3 -> "7.3%". Under 10 keeps a decimal. */
export function percent(value: number): string {
  return Math.abs(value) < 10 ? `${value.toFixed(1)}%` : `${value.toFixed(0)}%`;
}

/** A chance between 0 and 1. */
export function chance(p: number): string {
  return p < 0.001 ? "less than 0.1%" : percent(p * 100);
}

export interface MetricRow {
  label: string;
  value: string;
}

interface MetricSpec {
  key: string;
  label: string;
  format: (value: number) => string;
}

const count = (value: number): string => String(Math.round(value));
const fraction = (value: number): string => percent(value * 100);

const METRICS: Record<string, MetricSpec[]> = {
  overtrading: [
    { key: "avg_monthly_turnover_pct", label: "Average monthly turnover", format: percent },
    { key: "annualised_turnover_pct", label: "The same over a year", format: percent },
    { key: "months", label: "Months compared", format: count },
  ],
  disposition_effect: [
    { key: "pgr", label: "Winning positions sold", format: fraction },
    { key: "plr", label: "Losing positions sold", format: fraction },
    { key: "p_value", label: "Chance of a gap this big by luck alone", format: chance },
  ],
  run_up_buying: [
    { key: "run_up_share", label: "Buys after a big rise", format: fraction },
    { key: "expected_share", label: "Expected by luck alone", format: fraction },
    { key: "run_up_buys", label: "Number of those buys", format: count },
    { key: "p_value", label: "Chance of a share this high by luck alone", format: chance },
  ],
};

export function metricRows(finding: Finding): MetricRow[] {
  const specs = METRICS[finding.pattern] ?? [];
  const rows: MetricRow[] = [];
  for (const spec of specs) {
    const value = finding.metrics[spec.key];
    if (value !== undefined) rows.push({ label: spec.label, value: spec.format(value) });
  }
  return rows;
}

export function sourceLabel(finding: Finding): string | null {
  if (finding.explained_by === "ai") return "Written by AI from the facts below, and checked by TradeMind.";
  if (finding.explained_by === "tool") return "Written by TradeMind.";
  return null;
}
