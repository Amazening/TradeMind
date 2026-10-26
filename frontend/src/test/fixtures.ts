import { vi } from "vitest";
import type { Analysis, Finding, Report } from "../types";

/** Made-up data. Nothing here is from a real portfolio. */
export const overtrading: Finding = {
  pattern: "overtrading",
  title: "Trading a large share of the portfolio",
  result: "detected",
  confidence: "high",
  sample: { decisions: 120, cases: 36 },
  metrics: { avg_monthly_turnover_pct: 14.04, annualised_turnover_pct: 168.48, months: 36 },
  threshold: "Average monthly turnover above 8.8%",
  evidence: [
    { decision_id: null, note: "March 2024: 96.5% of the portfolio traded (4 buys, 5 sells)" },
    { decision_id: "d-9", note: "Sold ASX:ABC on 2024-03-14" },
  ],
  notes: ["Shares without market prices are valued at your last trade price."],
  explanation: "You traded about 14% of your portfolio each month, over 36 months.",
  explained_by: "ai",
};

export const disposition: Finding = {
  pattern: "disposition_effect",
  title: "Selling winners sooner than losers",
  result: "not_detected",
  confidence: "low",
  sample: { decisions: 12, cases: 100 },
  metrics: { pgr: 0.1, plr: 0.12, score: -0.02, p_value: 0.7 },
  threshold: "Share of gains sold above share of losses sold, with p below 0.05",
  evidence: [],
  notes: [],
  explanation: "You did not sell winners more often than losers, so this pattern was not found.",
  explained_by: "tool",
};

export const runUp: Finding = {
  pattern: "run_up_buying",
  title: "Buying after a sharp rise",
  result: "insufficient_data",
  confidence: null,
  sample: { decisions: 4, cases: 4 },
  metrics: {},
  threshold: "Share of buys after a top-10% rise above 10%, with p below 0.05",
  evidence: [],
  notes: [],
  explanation: "There is not enough data to check this pattern. It needs at least 15 buys.",
  explained_by: "tool",
};

export const report: Report = {
  schema_version: "1.0",
  generated_at: "2026-10-26T09:00:00Z",
  broker: "sharesies",
  period: { start: "2024-03-04", end: "2025-01-31" },
  summary: {
    trades_read: 412,
    decisions: 210,
    user_decisions: 190,
    platform_decisions: 20,
    markets: ["ASX", "NYSE", "NZX"],
    instruments: 22,
  },
  findings: [overtrading, disposition, runUp],
  data_notes: [
    { level: "info", message: "ASX:ABC: 8 trades before 2024-06-03 were adjusted for a 1:10 share split." },
    { level: "warning", message: "No market prices for ASX:XYZ. Only your own trade prices are used." },
  ],
  disclaimer: "This report describes past trading behaviour. It is not financial advice.",
};

export function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return { id: "abc123", status: "running", step: "getting_prices", report: null, error: null, ...overrides };
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export function apiError(status: number, code: string, message: string): Response {
  return json({ error: { code, message } }, status);
}

export type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

/** Replaces `fetch` with a fake. Returns the mock so tests can check the calls. */
export function stubFetch(handler: Handler) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(String(input), init),
  );
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function csvFile(name = "trades.csv", size = 200): File {
  return new File(["a".repeat(size)], name, { type: "text/csv" });
}
