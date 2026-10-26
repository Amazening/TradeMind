import { useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import { MAX_UPLOAD_BYTES, formatBytes } from "../format";
import { useFocusOnMount } from "../useFocusOnMount";

interface Props {
  onSubmit: (file: File) => void;
  busy: boolean;
  /** A problem from the server, such as an unrecognised file. */
  error?: string;
  /** A message such as "Your data was deleted." */
  notice?: string;
  /** False on the very first screen, so the page does not steal focus when it loads. */
  focusHeading?: boolean;
}

/** Returns a message if the file cannot be used, or null if it looks fine. */
export function validateFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".csv")) return "Please choose a .csv file.";
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `That file is too big. The limit is ${MAX_UPLOAD_BYTES / 1024 / 1024} MB.`;
  }
  return null;
}

export function UploadScreen({ onSubmit, busy, error, notice, focusHeading = true }: Props) {
  const heading = useFocusOnMount<HTMLHeadingElement>(focusHeading);
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const choose = (chosen: File | undefined): void => {
    if (!chosen) return;
    setFile(chosen);
    setProblem(validateFile(chosen));
  };

  const onChange = (event: ChangeEvent<HTMLInputElement>): void => choose(event.target.files?.[0]);

  const onDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  };

  const onFormSubmit = (event: FormEvent): void => {
    event.preventDefault();
    if (file && !problem) onSubmit(file);
  };

  const message = problem ?? error ?? null;

  return (
    <section aria-labelledby="upload-heading" className="screen">
      <h1 id="upload-heading" ref={heading} tabIndex={-1}>
        See the habits in your share trades
      </h1>
      <p className="lead">
        Upload your trade history from your broker. TradeMind looks for three habits and tells you
        what it found. It does not tell you what to buy or sell.
      </p>
      <ul className="habits">
        <li>Trading a large share of your portfolio</li>
        <li>Selling shares that are up sooner than shares that are down</li>
        <li>Buying just after a share has risen sharply</li>
      </ul>

      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}

      <form onSubmit={onFormSubmit} noValidate>
        <div
          className={dragging ? "dropzone dragging" : "dropzone"}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            id="trades-file"
            type="file"
            accept=".csv,text/csv"
            className="visually-hidden"
            onChange={onChange}
            aria-describedby={message ? "file-help file-error" : "file-help"}
          />
          <label htmlFor="trades-file" className="button secondary">
            Choose your CSV file
          </label>
          <p id="file-help" className="help">
            or drop it here. Sharesies files only, .csv, up to 5 MB.
          </p>
          {file && (
            <p className="file-name">
              Selected: <strong>{file.name}</strong> ({formatBytes(file.size)})
            </p>
          )}
        </div>

        {message && (
          <p id="file-error" role="alert" className="error">
            {message}
          </p>
        )}

        <button type="submit" className="button" disabled={!file || problem !== null || busy}>
          {busy ? "Uploading..." : "Analyse my trades"}
        </button>
      </form>

      <aside className="privacy" aria-label="Privacy">
        <h2>Your file is not saved</h2>
        <p>
          It is read in memory to make your report. The report is deleted one hour after it is
          ready, or when you press Delete.
        </p>
      </aside>

      <details className="how-to">
        <summary>How do I get my file?</summary>
        <ol>
          <li>Open Sharesies on the web or in the app.</li>
          <li>Go to Account, then Reports.</li>
          <li>Choose Transaction Report. Pick dates that cover all your trades.</li>
          <li>Choose CSV and export it.</li>
        </ol>
        <p className="help">Only Sharesies files work for now.</p>
      </details>
    </section>
  );
}
