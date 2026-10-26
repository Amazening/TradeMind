// These mirror the JSON the API returns (docs/02-spec.md, section 6.3).

export type PatternResult = "detected" | "not_detected" | "insufficient_data";
export type Confidence = "low" | "medium" | "high";

export interface Evidence {
  decision_id: string | null;
  note: string;
}

export interface Finding {
  pattern: string;
  title: string;
  result: PatternResult;
  confidence: Confidence | null;
  sample: { decisions: number; cases: number };
  metrics: Record<string, number>;
  threshold: string;
  evidence: Evidence[];
  notes: string[];
  explanation: string | null;
  explained_by: "ai" | "tool" | null;
}

export interface DataNote {
  level: "info" | "warning";
  message: string;
}

export interface Report {
  schema_version: string;
  generated_at: string;
  broker: string;
  period: { start: string; end: string };
  summary: {
    trades_read: number;
    decisions: number;
    user_decisions: number;
    platform_decisions: number;
    markets: string[];
    instruments: number;
  };
  findings: Finding[];
  data_notes: DataNote[];
  disclaimer: string;
}

export type Status = "queued" | "running" | "done" | "failed";
export type Step = "getting_prices" | "finding_patterns" | "writing_explanations";

export interface Analysis {
  id: string;
  status: Status;
  step: Step | null;
  report: Report | null;
  error: { code: string; message: string } | null;
}
