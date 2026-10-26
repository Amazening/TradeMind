import { useId } from "react";
import { CONFIDENCE_LABEL, RESULT_LABEL, metricRows, sourceLabel } from "../format";
import type { Finding } from "../types";

export function FindingCard({ finding }: { finding: Finding }) {
  const titleId = useId();
  const rows = metricRows(finding);
  const source = sourceLabel(finding);

  return (
    <article className="card" aria-labelledby={titleId}>
      <header className="card-header">
        <h3 id={titleId}>{finding.title}</h3>
        <span className={`badge ${finding.result}`}>{RESULT_LABEL[finding.result]}</span>
      </header>

      {finding.confidence && (
        <p className="meta">Confidence: {CONFIDENCE_LABEL[finding.confidence]}</p>
      )}

      {finding.explanation && <p className="explanation">{finding.explanation}</p>}
      {source && <p className="meta">{source}</p>}

      {rows.length > 0 && (
        <dl className="metrics">
          {rows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {finding.result !== "insufficient_data" && (
        <p className="meta">
          Based on {finding.sample.decisions} of your decisions. Rule used: {finding.threshold}.
        </p>
      )}

      {finding.notes.map((note) => (
        <p key={note} className="meta note">
          {note}
        </p>
      ))}

      {finding.evidence.length > 0 && (
        <details className="evidence">
          <summary>Show the trades behind this ({finding.evidence.length})</summary>
          <ul>
            {finding.evidence.map((item, index) => (
              <li key={`${item.decision_id ?? "summary"}-${index}`}>{item.note}</li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
