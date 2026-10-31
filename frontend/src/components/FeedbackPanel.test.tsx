import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";
import { report } from "../test/fixtures";
import { FeedbackPanel } from "./FeedbackPanel";
import { ReportScreen } from "./ReportScreen";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function open() {
  const user = userEvent.setup();
  render(<FeedbackPanel report={report} />);
  await user.click(screen.getByText("Help improve TradeMind (optional)"));
  return user;
}

describe("FeedbackPanel", () => {
  it("says nothing is sent, and shows exactly what would be shared", async () => {
    await open();

    expect(screen.getByText(/Nothing is sent from this page/)).toBeInTheDocument();
    const shared = screen.getByLabelText("What would be shared");
    expect(shared).toHaveTextContent("Version: 0.2.0");
    expect(shared).toHaveTextContent("Initiated by: Operator 1, System 19, you 395");
  });

  it("puts the comment into what would be shared as it is typed", async () => {
    const user = await open();

    await user.type(screen.getByLabelText("Comment (optional)"), "The small buys are mine");

    expect(screen.getByLabelText("What would be shared")).toHaveTextContent("The small buys are mine");
  });

  it("copies the summary", async () => {
    const user = await open();
    const writeText = vi.spyOn(navigator.clipboard, "writeText");

    await user.click(screen.getByRole("button", { name: "Copy summary" }));

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("TradeMind feedback"));
    expect(screen.getByRole("status")).toHaveTextContent(/^Copied/);
  });

  it("says so when it cannot copy", async () => {
    const user = await open();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("blocked"));

    await user.click(screen.getByRole("button", { name: "Copy summary" }));

    expect(screen.getByRole("status")).toHaveTextContent(/Could not copy/);
  });

  it("saves the summary as a text file named after the report date", async () => {
    const user = await open();
    const created: Blob[] = [];
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn((blob: Blob) => {
        created.push(blob);
        return "blob:fake";
      }),
      revokeObjectURL: vi.fn(),
    });
    const clicked: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this);
    });

    await user.click(screen.getByRole("button", { name: "Save as text file" }));

    expect(clicked[0]?.download).toBe("trademind-feedback-2026-10-26.txt");
    expect(await created[0]!.text()).toContain("TradeMind feedback");
  });

  it("has no accessibility problems that can be found without a browser", async () => {
    const user = userEvent.setup();
    const { container } = render(<ReportScreen report={report} onDelete={vi.fn()} onReset={vi.fn()} />);
    await user.click(screen.getByText("Help improve TradeMind (optional)"));

    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("ReportScreen and the feedback panel", () => {
  it("is on a real report", () => {
    render(<ReportScreen report={report} onDelete={vi.fn()} onReset={vi.fn()} />);

    expect(screen.getByText("Help improve TradeMind (optional)")).toBeInTheDocument();
  });

  it("is not on the example report, which is made up", () => {
    render(<ReportScreen report={report} example onDelete={vi.fn()} onReset={vi.fn()} />);

    expect(screen.queryByText("Help improve TradeMind (optional)")).not.toBeInTheDocument();
  });
});
