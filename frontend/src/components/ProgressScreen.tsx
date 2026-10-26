import type { Step } from "../types";
import { useFocusOnMount } from "../useFocusOnMount";

interface Props {
  /** The step now running, or null while the file is being sent. */
  step: Step | null;
}

const STEPS: { id: "reading" | Step; label: string }[] = [
  { id: "reading", label: "Reading your trades" },
  { id: "getting_prices", label: "Getting market prices" },
  { id: "finding_patterns", label: "Finding patterns" },
  { id: "writing_explanations", label: "Writing explanations" },
];

type StepState = "done" | "current" | "waiting";

function stateOf(index: number, step: Step | null): StepState {
  // Reading the trades happens as the file is uploaded, so it is done once work starts.
  const current = step === null ? 0 : STEPS.findIndex((s) => s.id === step);
  if (index < current) return "done";
  if (index === current) return "current";
  return "waiting";
}

const STATE_WORDS: Record<StepState, string> = {
  done: "done",
  current: "in progress",
  waiting: "waiting",
};

export function ProgressScreen({ step }: Props) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  const currentLabel = STEPS[step === null ? 0 : STEPS.findIndex((s) => s.id === step)]?.label;

  return (
    <section aria-labelledby="progress-heading" className="screen">
      <h1 id="progress-heading" ref={heading} tabIndex={-1}>
        Working on your report
      </h1>
      <p className="lead">This usually takes under a minute. Please keep this page open.</p>
      <ol className="steps">
        {STEPS.map((item, index) => {
          const state = stateOf(index, step);
          return (
            <li key={item.id} className={`step ${state}`} aria-current={state === "current"}>
              <span className="step-mark" aria-hidden="true" />
              <span>
                {item.label}
                <span className="visually-hidden"> ({STATE_WORDS[state]})</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p role="status" className="visually-hidden">
        Now: {currentLabel}
      </p>
    </section>
  );
}
