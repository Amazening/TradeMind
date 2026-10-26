import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import App from "./App";
import { analysis, apiError, csvFile, json, report, stubFetch } from "./test/fixtures";

const POLL_MS = 5;

type Reply = () => Response;

/** A fake API. `polls` are the replies to GET /api/analyses/abc123, in order. The last repeats. */
function fakeApi(polls: Reply[], options: { del?: Reply; post?: Reply } = {}) {
  let next = 0;
  return stubFetch((url, init) => {
    if (init?.method === "POST") {
      return options.post ? options.post() : json({ id: "abc123", status: "queued" }, 202);
    }
    if (init?.method === "DELETE") {
      return options.del ? options.del() : new Response(null, { status: 204 });
    }
    const reply = polls[Math.min(next, polls.length - 1)];
    next += 1;
    if (!reply) throw new Error(`No reply set up for ${url}`);
    return reply();
  });
}

const done: Reply = () => json(analysis({ status: "done", step: null, report }));
const running = (step: "getting_prices" | "finding_patterns" | "writing_explanations"): Reply =>
  () => json(analysis({ step }));

async function chooseAndSend(name = "trades.csv") {
  const user = userEvent.setup();
  await user.upload(screen.getByLabelText(/choose your csv file/i), csvFile(name));
  await user.click(screen.getByRole("button", { name: /analyse my trades/i }));
  return user;
}

describe("App", () => {
  it("takes a file through progress to the report", async () => {
    const fetchMock = fakeApi([running("getting_prices"), running("finding_patterns"), done]);
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    expect(await screen.findByRole("heading", { name: /working on your report/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Your report" })).toBeInTheDocument();
    expect(screen.getByText("Trading a large share of the portfolio")).toBeInTheDocument();
    expect(screen.getByText("Selling winners sooner than losers")).toBeInTheDocument();
    expect(screen.getByText("Buying after a sharp rise")).toBeInTheDocument();
    expect(screen.getByText(report.disclaimer)).toBeInTheDocument();

    const [uploadUrl, uploadInit] = fetchMock.mock.calls[0] ?? [];
    expect(uploadUrl).toBe("/api/analyses");
    expect(uploadInit?.method).toBe("POST");
    expect(uploadInit?.body).toBeInstanceOf(FormData);
    expect((uploadInit?.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("shows the step that is running while it waits", async () => {
    fakeApi([running("finding_patterns")]);
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    await waitFor(() => {
      const item = screen.getByText("Finding patterns").closest("li");
      expect(item).toHaveTextContent("in progress");
    });
    expect(screen.getByText("Getting market prices").closest("li")).toHaveTextContent("done");
  });

  it("shows the server's message when it rejects the file, and lets the person try again", async () => {
    fakeApi([done], {
      post: () =>
        apiError(
          422,
          "unrecognised_broker",
          "This file is not from a supported broker. Supported: sharesies",
        ),
    });
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    expect(await screen.findByRole("alert")).toHaveTextContent(/not from a supported broker/i);
    expect(screen.getByRole("heading", { name: /see the habits/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyse my trades/i })).toBeEnabled();
  });

  it("explains when the server cannot be reached", async () => {
    stubFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't reach trademind/i);
  });

  it("shows a failed analysis and goes back to the start when asked", async () => {
    fakeApi([
      () =>
        json(
          analysis({
            status: "failed",
            step: null,
            error: {
              code: "price_source_error",
              message: "We couldn't get market prices. Try again later.",
            },
          }),
        ),
    ]);
    render(<App pollMs={POLL_MS} />);
    const user = await chooseAndSend();

    expect(await screen.findByRole("heading", { name: /couldn't make your report/i })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("We couldn't get market prices. Try again later.");

    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.getByRole("heading", { name: /see the habits/i })).toBeInTheDocument();
  });

  it("says so when the report has expired while waiting", async () => {
    fakeApi([() => apiError(404, "not_found", "That analysis was not found.")]);
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    expect(await screen.findByRole("alert")).toHaveTextContent(/no longer available/i);
  });

  it("gives up after three failed checks in a row", async () => {
    stubFetch((_url, init) => {
      if (init?.method === "POST") return json({ id: "abc123", status: "queued" }, 202);
      throw new TypeError("Failed to fetch");
    });
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't reach trademind/i);
  });

  it("carries on after one failed check", async () => {
    let calls = 0;
    stubFetch((_url, init) => {
      if (init?.method === "POST") return json({ id: "abc123", status: "queued" }, 202);
      calls += 1;
      if (calls === 1) throw new TypeError("Failed to fetch");
      return calls === 2 ? json(analysis()) : json(analysis({ status: "done", step: null, report }));
    });
    render(<App pollMs={POLL_MS} />);

    await chooseAndSend();

    expect(await screen.findByRole("heading", { name: "Your report" })).toBeInTheDocument();
  });

  it("deletes the report on the server and returns to the start with a message", async () => {
    const fetchMock = fakeApi([done]);
    render(<App pollMs={POLL_MS} />);
    const user = await chooseAndSend();
    await screen.findByRole("heading", { name: "Your report" });

    await user.click(screen.getByRole("button", { name: /delete my data/i }));
    await user.click(screen.getByRole("button", { name: /yes, delete it/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/were deleted/i);
    expect(screen.getByRole("heading", { name: /see the habits/i })).toBeInTheDocument();
    const deleteCall = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE");
    expect(deleteCall?.[0]).toBe("/api/analyses/abc123");
  });

  it("counts a report that is already gone as deleted", async () => {
    fakeApi([done], { del: () => apiError(404, "not_found", "Not found") });
    render(<App pollMs={POLL_MS} />);
    const user = await chooseAndSend();
    await screen.findByRole("heading", { name: "Your report" });

    await user.click(screen.getByRole("button", { name: /delete my data/i }));
    await user.click(screen.getByRole("button", { name: /yes, delete it/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/were deleted/i);
  });

  it("keeps the report and shows a problem if the deletion fails", async () => {
    fakeApi([done], { del: () => apiError(500, "error", "Something went wrong. Please try again.") });
    render(<App pollMs={POLL_MS} />);
    const user = await chooseAndSend();
    await screen.findByRole("heading", { name: "Your report" });

    await user.click(screen.getByRole("button", { name: /delete my data/i }));
    await user.click(screen.getByRole("button", { name: /yes, delete it/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/something went wrong/i);
    expect(screen.getByRole("heading", { name: "Your report" })).toBeInTheDocument();
  });

  it("goes back to the start for another file", async () => {
    fakeApi([done]);
    render(<App pollMs={POLL_MS} />);
    const user = await chooseAndSend();
    await screen.findByRole("heading", { name: "Your report" });

    await user.click(screen.getByRole("button", { name: /check another file/i }));

    expect(screen.getByRole("heading", { name: /see the habits/i })).toBeInTheDocument();
  });

  it("always shows that this is not financial advice", async () => {
    render(<App pollMs={POLL_MS} />);

    expect(screen.getByText(/is not financial advice/i)).toBeInTheDocument();
  });

  it("can be used with the keyboard alone", async () => {
    fakeApi([done]);
    render(<App pollMs={POLL_MS} />);
    const user = userEvent.setup();

    await user.tab();
    expect(screen.getByRole("link", { name: /skip to the main content/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText(/choose your csv file/i)).toHaveFocus();

    await user.upload(screen.getByLabelText(/choose your csv file/i), csvFile());
    await user.tab();
    const analyse = screen.getByRole("button", { name: /analyse my trades/i });
    expect(analyse).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("heading", { name: "Your report" })).toHaveFocus();
  });

  it("does not take focus when the page first loads, but does when a screen changes", async () => {
    fakeApi([done]);
    render(<App pollMs={POLL_MS} />);

    expect(document.body).toHaveFocus();
    expect(screen.getByRole("heading", { name: /see the habits/i })).not.toHaveFocus();

    const user = await chooseAndSend();
    const report = await screen.findByRole("heading", { name: "Your report" });
    expect(report).toHaveFocus();

    await user.click(screen.getByRole("button", { name: /check another file/i }));
    expect(screen.getByRole("heading", { name: /see the habits/i })).toHaveFocus();
  });

  it("has a skip link and a main landmark", () => {
    render(<App pollMs={POLL_MS} />);

    expect(screen.getByRole("link", { name: /skip to the main content/i })).toHaveAttribute(
      "href",
      "#main",
    );
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("has no accessibility problems on the report page that can be found without a browser", async () => {
    fakeApi([done]);
    const { container } = render(<App pollMs={POLL_MS} />);
    await chooseAndSend();
    await screen.findByRole("heading", { name: "Your report" });

    expect((await axe(container)).violations).toEqual([]);
  });
});
