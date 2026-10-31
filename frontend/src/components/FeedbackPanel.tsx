import { useId, useState } from "react";
import { COMMENT_LIMIT, buildFeedbackText } from "../feedback";
import type { Report } from "../types";

interface Props {
  report: Report;
}

function downloadText(text: string, report: Report): void {
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `trademind-feedback-${report.generated_at.slice(0, 10)}.txt`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/**
 * Optional. Makes a short summary of how the file was read, for the person to send to the
 * developer. Nothing is sent from this page. The summary has counts only.
 */
export function FeedbackPanel({ report }: Props) {
  const commentId = useId();
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState("");

  const text = buildFeedbackText(report, comment);

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("Copied. Paste it into a message to the person who gave you the code.");
    } catch {
      setStatus("Could not copy. Select the text above and copy it yourself.");
    }
  };

  return (
    <details className="feedback">
      <summary>Help improve TradeMind (optional)</summary>

      <p>
        Nothing is sent from this page. This makes a short summary of how your file was read. You
        can copy it or save it, and send it to the person who gave you the code, if you want to.
      </p>
      <p>
        The summary has counts only. It has no share names, dates or amounts. Your comment is
        included as you write it.
      </p>

      <div className="field">
        <label htmlFor={commentId}>Comment (optional)</label>
        <textarea
          id={commentId}
          value={comment}
          maxLength={COMMENT_LIMIT}
          rows={3}
          onChange={(event) => setComment(event.target.value)}
        />
      </div>

      <h3>What would be shared</h3>
      <pre className="feedback-text" aria-label="What would be shared" tabIndex={0}>
        {text}
      </pre>

      <div className="actions">
        <button type="button" className="button" onClick={copy}>
          Copy summary
        </button>
        <button type="button" className="button secondary" onClick={() => downloadText(text, report)}>
          Save as text file
        </button>
      </div>
      <p role="status" className="meta">
        {status}
      </p>
    </details>
  );
}
