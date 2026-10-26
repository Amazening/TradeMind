import { useFocusOnMount } from "../useFocusOnMount";

interface Props {
  message: string;
  onRetry: () => void;
}

export function FailedScreen({ message, onRetry }: Props) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  return (
    <section aria-labelledby="failed-heading" className="screen">
      <h1 id="failed-heading" ref={heading} tabIndex={-1}>
        We couldn't make your report
      </h1>
      <p role="alert" className="error">
        {message}
      </p>
      <button type="button" className="button" onClick={onRetry}>
        Try again
      </button>
    </section>
  );
}
