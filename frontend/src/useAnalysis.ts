import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteAnalysis, getAnalysis, uploadCsv } from "./api";
import type { Report, Step } from "./types";

export type AnalysisState =
  | { kind: "idle"; error?: string; notice?: string }
  | { kind: "uploading" }
  | { kind: "running"; id: string; step: Step | null }
  | { kind: "done"; id: string; report: Report }
  | { kind: "failed"; message: string };

const MAX_POLL_FAILURES = 3;
const EXPIRED_MESSAGE =
  "This report is no longer available. It may have expired. Upload your file again.";

export interface AnalysisControls {
  state: AnalysisState;
  /** True once the person has started anything, so later screens can move focus. */
  touched: boolean;
  start: (file: File) => Promise<void>;
  /** Deletes the report on the server. Returns an error message, or null on success. */
  remove: () => Promise<string | null>;
  reset: () => void;
}

export function useAnalysis(pollMs = 1000): AnalysisControls {
  const [state, setState] = useState<AnalysisState>({ kind: "idle" });
  const [touched, setTouched] = useState(false);
  const runningId = state.kind === "running" ? state.id : null;

  useEffect(() => {
    if (runningId === null) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;

    const poll = async (): Promise<void> => {
      try {
        const analysis = await getAnalysis(runningId);
        if (cancelled) return;
        failures = 0;
        if (analysis.status === "done" && analysis.report) {
          setState({ kind: "done", id: runningId, report: analysis.report });
        } else if (analysis.status === "failed") {
          setState({
            kind: "failed",
            message: analysis.error?.message ?? "Something went wrong. Please try again.",
          });
        } else {
          setState((previous) =>
            previous.kind === "running" && previous.step === analysis.step
              ? previous
              : { kind: "running", id: runningId, step: analysis.step },
          );
          timer = setTimeout(poll, pollMs);
        }
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ kind: "failed", message: EXPIRED_MESSAGE });
          return;
        }
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) {
          setState({
            kind: "failed",
            message: error instanceof ApiError ? error.message : "Something went wrong.",
          });
        } else {
          timer = setTimeout(poll, pollMs);
        }
      }
    };

    timer = setTimeout(poll, 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [runningId, pollMs]);

  const start = useCallback(async (file: File): Promise<void> => {
    setTouched(true);
    setState({ kind: "uploading" });
    try {
      const { id } = await uploadCsv(file);
      setState({ kind: "running", id, step: "getting_prices" });
    } catch (error) {
      setState({
        kind: "idle",
        error: error instanceof ApiError ? error.message : "Something went wrong. Please try again.",
      });
    }
  }, []);

  const remove = useCallback(async (): Promise<string | null> => {
    if (state.kind !== "done") return null;
    try {
      await deleteAnalysis(state.id);
    } catch (error) {
      // Already gone counts as deleted.
      if (!(error instanceof ApiError && error.status === 404)) {
        return error instanceof ApiError ? error.message : "We couldn't delete it. Try again.";
      }
    }
    setState({ kind: "idle", notice: "Your report and trade data were deleted." });
    return null;
  }, [state]);

  const reset = useCallback((): void => setState({ kind: "idle" }), []);

  return { state, touched, start, remove, reset };
}
