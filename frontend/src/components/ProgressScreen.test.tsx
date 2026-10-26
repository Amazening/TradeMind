import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { ProgressScreen } from "./ProgressScreen";

function stepText(label: string): string {
  const item = screen.getByText(label).closest("li");
  return item?.textContent ?? "";
}

describe("ProgressScreen", () => {
  it("lists the four steps, with the first marked as in progress before work starts", () => {
    render(<ProgressScreen step={null} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(stepText("Reading your trades")).toContain("in progress");
    expect(stepText("Getting market prices")).toContain("waiting");
  });

  it("marks earlier steps done, the current one in progress, and later ones waiting", () => {
    render(<ProgressScreen step="finding_patterns" />);

    expect(stepText("Reading your trades")).toContain("done");
    expect(stepText("Getting market prices")).toContain("done");
    expect(stepText("Finding patterns")).toContain("in progress");
    expect(stepText("Writing explanations")).toContain("waiting");
  });

  it("marks the current step for assistive technology", () => {
    render(<ProgressScreen step="getting_prices" />);

    const current = screen.getByText("Getting market prices").closest("li");
    expect(current).toHaveAttribute("aria-current", "true");
  });

  it("announces the step that is running", () => {
    render(<ProgressScreen step="writing_explanations" />);

    expect(screen.getByRole("status")).toHaveTextContent("Now: Writing explanations");
  });

  it("has a heading that takes focus", () => {
    render(<ProgressScreen step="getting_prices" />);

    expect(screen.getByRole("heading", { name: /working on your report/i })).toHaveFocus();
  });

  it("has no accessibility problems that can be found without a browser", async () => {
    const { container } = render(<ProgressScreen step="getting_prices" />);

    expect((await axe(container)).violations).toEqual([]);
  });
});
