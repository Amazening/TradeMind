import { FailedScreen } from "./components/FailedScreen";
import { ProgressScreen } from "./components/ProgressScreen";
import { ReportScreen } from "./components/ReportScreen";
import { UploadScreen } from "./components/UploadScreen";
import { useAnalysis } from "./useAnalysis";
import { useSiteConfig } from "./useConfig";

interface Props {
  /** How often to ask for progress, in milliseconds. Tests use a small number. */
  pollMs?: number;
}

export default function App({ pollMs }: Props) {
  const { state, touched, start, showExample, remove, reset } = useAnalysis(pollMs);
  const { accessCodeRequired, aiExplanations } = useSiteConfig();

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to the main content
      </a>
      <header className="site-header">
        <span className="brand">TradeMind</span>
      </header>
      <main id="main">
        {(state.kind === "idle" || state.kind === "uploading") && (
          <UploadScreen
            onSubmit={start}
            onShowExample={showExample}
            accessCodeRequired={accessCodeRequired}
            aiExplanations={aiExplanations}
            busy={state.kind === "uploading"}
            focusHeading={touched}
            error={state.kind === "idle" ? state.error : undefined}
            notice={state.kind === "idle" ? state.notice : undefined}
          />
        )}
        {state.kind === "running" && <ProgressScreen step={state.step} />}
        {state.kind === "done" && (
          <ReportScreen report={state.report} onDelete={remove} onReset={reset} />
        )}
        {state.kind === "example" && (
          <ReportScreen
            report={state.report}
            example
            onDelete={async () => null}
            onReset={reset}
          />
        )}
        {state.kind === "failed" && <FailedScreen message={state.message} onRetry={reset} />}
      </main>
      <footer className="site-footer">
        <p>
          TradeMind describes your past trading. It is not financial advice and does not tell you
          what to buy or sell.
        </p>
      </footer>
    </>
  );
}
