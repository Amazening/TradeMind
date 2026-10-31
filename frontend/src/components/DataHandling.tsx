interface Props {
  /** Whether an AI service words the results. It is only mentioned if it is used. */
  aiExplanations: boolean;
}

const REPO_URL = "https://github.com/Amazening/TradeMind";

/** What happens to an uploaded file, in plain words. Each line matches what the server does. */
export function DataHandling({ aiExplanations }: Props) {
  return (
    <details className="data-handling">
      <summary>How your data is handled</summary>

      <h3>Your file</h3>
      <p>
        It is sent to this site over HTTPS and held in memory only. It is not written to disk. Your
        report and trade data are deleted one hour after the report is ready, or when you press
        Delete.
      </p>

      <h3>What the server keeps</h3>
      <p>
        There are no accounts. The server&apos;s logs hold counts and timings. They do not hold
        share names, amounts or report links. The server also keeps public market prices on disk,
        so it does not ask for them again. They are named after the share codes that were looked
        up and cover the dates asked for. They hold no amounts, names or user details.
      </p>

      <h3>What goes to other services</h3>
      <ul>
        <li>
          <strong>Yahoo Finance</strong> gets the share codes, currencies and dates needed to find
          prices. It does not get your amounts or your name.
        </li>
        {aiExplanations && (
          <li>
            <strong>An AI service (Groq)</strong> gets short sentences with percentages and
            counts, to word your results. It does not get your trades, share names, dates or
            amounts.
          </li>
        )}
      </ul>

      <h3>Who can see your report</h3>
      <p>
        Anyone who has your report link can open the report until it is deleted. Please do not
        share the link.
      </p>

      <h3>Feedback</h3>
      <p>
        Nothing is sent to the person who runs the site unless you send it. On your report page you
        can make a short summary of how your file was read. It has counts only, with no share names,
        dates or amounts. You can read it, then copy it or save it, and send it yourself if you
        want to.
      </p>

      <h3>Limits</h3>
      <p>
        This is a personal project run by one person. It has not had an independent security
        audit. The person who runs the site runs the server, so you are trusting them with your
        file.
      </p>

      <h3>Run it yourself</h3>
      <p>
        The code is public at{" "}
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          github.com/Amazening/TradeMind
        </a>
        . You can run it on your own computer. Only the price look-ups leave your computer.
      </p>
    </details>
  );
}
