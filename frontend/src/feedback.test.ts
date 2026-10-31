import { describe, expect, it } from "vitest";
import { COMMENT_LIMIT, buildFeedbackText } from "./feedback";
import { report } from "./test/fixtures";

describe("buildFeedbackText", () => {
  it("has the version, the history length and the counts", () => {
    const text = buildFeedbackText(report, "");

    expect(text).toContain("Version: 0.2.0 (report format 1.1)");
    expect(text).toContain("History length: about 36 months");
    expect(text).toContain("Trades read: 412");
    expect(text).toContain("Decisions: 190 by you, 20 by the platform");
    expect(text).toContain("Initiated by: Operator 1, System 19, you 395");
    expect(text).toContain("under 1 in their own currency, by who started them: System 12, you 40");
    expect(text).toContain("Why rows were skipped: Unknown transaction method: DIVIDEND 3");
  });

  it("lists each result with its confidence and sample size", () => {
    const text = buildFeedbackText(report, "");

    expect(text).toContain("Trading a large share of the portfolio: detected, confidence high, 120 decisions, 36 cases");
    expect(text).toContain("Buying after a sharp rise: insufficient data, confidence none");
  });

  it("holds no share names, dates or amounts from the report", () => {
    const text = buildFeedbackText(report, "");

    // The fixture's notes and evidence name shares and dates. None of it may get through.
    for (const value of ["ABC", "XYZ", "2022", "2024", "2025", "2026", "14.04", "96.5"]) {
      expect(text).not.toContain(value);
    }
  });

  it("counts the notes without repeating them", () => {
    expect(buildFeedbackText(report, "")).toContain("Notes about the data: 1 warnings, 1 information");
  });

  it("adds the comment as written, and says when there is none", () => {
    expect(buildFeedbackText(report, "  Looks right to me  ")).toContain(
      "Comment from the person who tried it:\nLooks right to me",
    );
    expect(buildFeedbackText(report, "   ")).toContain("(none)");
  });

  it("cuts a long comment", () => {
    const text = buildFeedbackText(report, "x".repeat(COMMENT_LIMIT + 50));

    expect(text.endsWith("x".repeat(COMMENT_LIMIT))).toBe(true);
    expect(text).not.toContain("x".repeat(COMMENT_LIMIT + 1));
  });

  it("still works for a report made before diagnostics existed", () => {
    const text = buildFeedbackText({ ...report, diagnostics: null }, "");

    expect(text).toContain("Trades read: 412");
    expect(text).not.toContain("Initiated by");
  });
});
