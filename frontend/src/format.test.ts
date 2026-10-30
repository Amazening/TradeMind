import { describe, expect, it } from "vitest";
import {
  RESULT_LABEL,
  chance,
  formatBytes,
  formatDate,
  metricRows,
  percent,
  sourceLabel,
} from "./format";
import { disposition, overtrading, runUp } from "./test/fixtures";

describe("formatBytes", () => {
  it("uses bytes, KB and MB", () => {
    expect(formatBytes(512)).toBe("512 bytes");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(1.5 * 1024 * 1024)).toBe("1.5 MB");
  });
});

describe("formatDate", () => {
  it("writes a date in New Zealand English without shifting the day", () => {
    expect(formatDate("2024-03-04")).toBe("4 March 2024");
    expect(formatDate("2026-01-01")).toBe("1 January 2026");
  });

  it("returns the text unchanged if it is not a date", () => {
    expect(formatDate("not a date")).toBe("not a date");
  });
});

describe("percent and chance", () => {
  it("keeps one decimal under 10 and none above", () => {
    expect(percent(14.04)).toBe("14%");
    expect(percent(7.3)).toBe("7.3%");
    expect(percent(168.48)).toBe("168%");
  });

  it("writes a very small chance as less than 0.1%", () => {
    expect(chance(0.0000004)).toBe("less than 0.1%");
    expect(chance(0.97)).toBe("97%");
    expect(chance(0.0123)).toBe("1.2%");
  });
});

describe("metricRows", () => {
  it("labels the overtrading numbers", () => {
    expect(metricRows(overtrading)).toEqual([
      { label: "Average monthly turnover", value: "14%" },
      { label: "The same over a year", value: "168%" },
      { label: "Months compared", value: "36" },
    ]);
  });

  it("turns proportions into percentages", () => {
    const rows = metricRows(disposition);

    expect(rows).toContainEqual({ label: "Winning positions sold", value: "10%" });
    expect(rows).toContainEqual({ label: "Losing positions sold", value: "12%" });
    expect(rows).toContainEqual({
      label: "Chance of a gap this big or bigger by luck alone",
      value: "70%",
    });
  });

  it("has no rows when there are no numbers", () => {
    expect(metricRows(runUp)).toEqual([]);
  });

  it("ignores a pattern it does not know", () => {
    expect(metricRows({ ...overtrading, pattern: "something_new" })).toEqual([]);
  });
});

describe("labels", () => {
  it("names each result without calling it good or bad", () => {
    expect(RESULT_LABEL).toEqual({
      detected: "Found",
      not_detected: "Not found",
      insufficient_data: "Not enough data",
    });
  });

  it("says who wrote an explanation", () => {
    expect(sourceLabel(overtrading)).toMatch(/AI/);
    expect(sourceLabel(disposition)).toBe("Written by TradeMind.");
    expect(sourceLabel({ ...overtrading, explained_by: null })).toBeNull();
  });
});
