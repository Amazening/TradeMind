import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import { overtrading, report } from "../test/fixtures";
import { FindingCard } from "./FindingCard";
import { ReportScreen, downloadReport } from "./ReportScreen";

function setup(onDelete = vi.fn(async () => null as string | null)) {
  const onReset = vi.fn();
  const view = render(<ReportScreen report={report} onDelete={onDelete} onReset={onReset} />);
  return { onDelete, onReset, ...view };
}

describe("ReportScreen", () => {
  it("summarises the period and the trades", () => {
    setup();

    expect(screen.getByRole("heading", { level: 1, name: "Your report" })).toHaveFocus();
    expect(screen.getByText(/4 March 2024 to 31 January 2025/)).toBeInTheDocument();
    expect(screen.getByText(/412 trades, 190 decisions by you and 20 by the platform/)).toBeInTheDocument();
    expect(screen.getByText(/14 shares on ASX, NYSE, NZX/)).toBeInTheDocument();
  });

  it("leaves out the platform count when there are no platform decisions", () => {
    const quiet = { ...report, summary: { ...report.summary, platform_decisions: 0 } };
    render(<ReportScreen report={quiet} onDelete={vi.fn()} onReset={vi.fn()} />);

    expect(screen.queryByText(/by the platform/)).not.toBeInTheDocument();
  });

  it("shows one card per finding with a result label", () => {
    setup();

    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(3);
    expect(within(cards[0]!).getByText("Found")).toBeInTheDocument();
    expect(within(cards[1]!).getByText("Not found")).toBeInTheDocument();
    expect(within(cards[2]!).getByText("Not enough data")).toBeInTheDocument();
  });

  it("lists warnings before notes in the data section, with a hidden prefix for screen readers", () => {
    setup();

    const items = within(screen.getByRole("region", { name: /about your data/i })).getAllByRole(
      "listitem",
    );
    expect(items[0]).toHaveTextContent("Warning: No market prices for ASX:XYZ");
    expect(items[1]).toHaveTextContent("Note: ASX:ABC: 8 trades before");
  });

  it("always shows the disclaimer", () => {
    setup();

    expect(screen.getByText(report.disclaimer)).toBeInTheDocument();
  });

  it("starts again when asked", async () => {
    const { onReset } = setup();

    await userEvent.click(screen.getByRole("button", { name: /check another file/i }));

    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("asks before deleting, and can be cancelled", async () => {
    const { onDelete } = setup();

    await userEvent.click(screen.getByRole("button", { name: /delete my data/i }));
    expect(screen.getByText(/can't get it back/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByText(/can't get it back/i)).not.toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("deletes after confirmation", async () => {
    const { onDelete } = setup();

    await userEvent.click(screen.getByRole("button", { name: /delete my data/i }));
    await userEvent.click(screen.getByRole("button", { name: /yes, delete it/i }));

    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("shows a problem if the deletion fails, and keeps the report", async () => {
    const onDelete = vi.fn(async () => "We couldn't delete it. Try again.");
    setup(onDelete);

    await userEvent.click(screen.getByRole("button", { name: /delete my data/i }));
    await userEvent.click(screen.getByRole("button", { name: /yes, delete it/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't delete it");
    expect(screen.getByRole("heading", { name: "Your report" })).toBeInTheDocument();
  });

  it("downloads the report as JSON named after its date", async () => {
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

    downloadReport(report);

    expect(clicked[0]?.download).toBe("trademind-report-2026-10-26.json");
    expect(JSON.parse(await created[0]!.text())).toEqual(report);
  });

  it("has no accessibility problems that can be found without a browser", async () => {
    const { container } = setup();

    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("FindingCard", () => {
  it("shows the explanation, who wrote it, the numbers and the basis", () => {
    render(<FindingCard finding={overtrading} />);

    expect(screen.getByText(/you traded about 14% of your portfolio/i)).toBeInTheDocument();
    expect(screen.getByText(/written by ai/i)).toBeInTheDocument();
    expect(screen.getByText("Confidence: High")).toBeInTheDocument();
    expect(screen.getByText("Average monthly turnover")).toBeInTheDocument();
    expect(screen.getByText(/based on 120 of your decisions/i)).toBeInTheDocument();
    expect(screen.getByText(/rule used: average monthly turnover above 8.8%/i)).toBeInTheDocument();
  });

  it("keeps the trades behind a result closed until asked", async () => {
    render(<FindingCard finding={overtrading} />);
    const summary = screen.getByText(/show the trades behind this \(2\)/i);

    expect(screen.getByText(/sold asx:abc/i)).not.toBeVisible();
    await userEvent.click(summary);

    expect(screen.getByText(/sold asx:abc/i)).toBeVisible();
  });

  it("has no trades section when there is no evidence", () => {
    render(<FindingCard finding={{ ...overtrading, evidence: [] }} />);

    expect(screen.queryByText(/show the trades behind this/i)).not.toBeInTheDocument();
  });

  it("does not show a basis line when there is not enough data", () => {
    render(
      <FindingCard
        finding={{ ...overtrading, result: "insufficient_data", confidence: null, metrics: {} }}
      />,
    );

    expect(screen.queryByText(/based on/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });

  it("shows the notes that come with a finding", () => {
    render(<FindingCard finding={overtrading} />);

    expect(screen.getByText(/valued at your last trade price/i)).toBeInTheDocument();
  });
});
