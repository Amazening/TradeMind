import { useState } from "react";
import { formatDate } from "../format";
import type { Report } from "../types";
import { useFocusOnMount } from "../useFocusOnMount";
import { FindingCard } from "./FindingCard";

interface Props {
  report: Report;
  /** Deletes the report. Returns an error message, or null on success. */
  onDelete: () => Promise<string | null>;
  onReset: () => void;
}

export function downloadReport(report: Report): void {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `trademind-report-${report.generated_at.slice(0, 10)}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function ReportScreen({ report, onDelete, onReset }: Props) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { summary } = report;
  const warnings = report.data_notes.filter((note) => note.level === "warning");
  const infos = report.data_notes.filter((note) => note.level === "info");

  const confirmDelete = async (): Promise<void> => {
    setDeleting(true);
    const error = await onDelete();
    // On success the screen is replaced, so only a failure needs handling here.
    setDeleting(false);
    if (error) setDeleteError(error);
  };

  return (
    <section aria-labelledby="report-heading" className="screen">
      <h1 id="report-heading" ref={heading} tabIndex={-1}>
        Your report
      </h1>

      <p className="lead">
        {formatDate(report.period.start)} to {formatDate(report.period.end)}.{" "}
        {summary.trades_read} trades, {summary.user_decisions} decisions by you
        {summary.platform_decisions > 0 && ` and ${summary.platform_decisions} by the platform`}, in{" "}
        {summary.instruments} shares on {summary.markets.join(", ")}.
      </p>
      <p className="meta">
        Confidence shows how much data a result rests on. Low means just enough. High means plenty.
      </p>

      <h2>What we found</h2>
      <div className="cards">
        {report.findings.map((finding) => (
          <FindingCard key={finding.pattern} finding={finding} />
        ))}
      </div>

      {report.data_notes.length > 0 && (
        <section aria-labelledby="notes-heading" className="data-notes">
          <h2 id="notes-heading">About your data</h2>
          <ul>
            {[...warnings, ...infos].map((note) => (
              <li key={note.message} className={note.level}>
                <span className="visually-hidden">{note.level === "warning" ? "Warning: " : "Note: "}</span>
                {note.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="disclaimer">{report.disclaimer}</p>

      <div className="actions">
        <button type="button" className="button" onClick={() => downloadReport(report)}>
          Download report (JSON)
        </button>
        <button type="button" className="button secondary" onClick={onReset}>
          Check another file
        </button>
        {!confirming && (
          <button type="button" className="button danger" onClick={() => setConfirming(true)}>
            Delete my data
          </button>
        )}
      </div>

      {confirming && (
        <div role="group" aria-label="Confirm delete" className="confirm">
          <p>Delete this report now? You can't get it back.</p>
          <button type="button" className="button danger" disabled={deleting} onClick={confirmDelete}>
            {deleting ? "Deleting..." : "Yes, delete it"}
          </button>
          <button type="button" className="button secondary" onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </div>
      )}
      {deleteError && (
        <p role="alert" className="error">
          {deleteError}
        </p>
      )}
    </section>
  );
}
