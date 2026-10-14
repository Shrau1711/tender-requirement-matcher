import { describe, expect, it } from "vitest";
import report from "../fixtures/sampleReport.json";
import { FLAG_ACTION, FLAG_HELP, callsSummary, countsOf, flagCounts, fileSize, percent } from "./format";
import { filterRows, pagesToCheck, progressOf, reviewKey, rowsOf } from "./review";
import { links, parseRoute } from "./route";
import { matches, pageOf, sortRows } from "./tables";

describe("routes", () => {
  it("round-trips every page through its link, including names with spaces", () => {
    expect(parseRoute(links.newRun)).toEqual({ page: "new" });
    expect(parseRoute(links.runs)).toEqual({ page: "runs" });
    expect(parseRoute(links.run("ab12", "requirements", "L & T"))).toEqual({ page: "run", id: "ab12", tab: "requirements", maker: "L & T" });
    expect(parseRoute(links.run("ab12"))).toEqual({ page: "run", id: "ab12", tab: "overview", maker: null });
    expect(parseRoute(links.compare("a", "b"))).toEqual({ page: "compare", a: "a", b: "b" });
    expect(parseRoute("")).toEqual({ page: "new" });
  });
});

describe("tables", () => {
  const rows = [{ n: "b", v: 2 }, { n: "a", v: 10 }, { n: "c", v: 2 }];
  const columns = [{ key: "n" }, { key: "v" }];
  it("sorts numbers as numbers, text as text, and keeps ties in order", () => {
    expect(sortRows(rows, { key: "v", direction: "ascending" }, columns).map((r) => r.n)).toEqual(["b", "c", "a"]);
    expect(sortRows(rows, { key: "v", direction: "descending" }, columns).map((r) => r.n)).toEqual(["a", "b", "c"]);
    expect(sortRows(rows, { key: "n", direction: "ascending" }, columns).map((r) => r.n)).toEqual(["a", "b", "c"]);
    expect(sortRows(rows, null, columns)).toBe(rows);
  });
  it("pages and clamps the page number", () => {
    expect(pageOf(rows, 0, 2)).toMatchObject({ pages: 2, from: 1, to: 2 });
    expect(pageOf(rows, 9, 2)).toMatchObject({ current: 1, from: 3, to: 3 });
    expect(pageOf([], 0, 2)).toMatchObject({ pages: 1, from: 0, to: 0 });
  });
  it("searches for every word, in any order", () => {
    expect(matches("Seat material EPDM", "epdm seat")).toBe(true);
    expect(matches("Seat material EPDM", "nbr")).toBe(false);
  });
});

describe("reviews", () => {
  const alpha = report.makers[0];
  const rows = rowsOf(alpha);
  it("builds the same row key as the backend", () => {
    expect(reviewKey("Acme", "Pump", { attribute: "head", wanted: "20 m", tender_page: 3 })).toBe('["Acme","Pump","head","20 m",3]');
  });
  it("lists only the scored rows of a maker, each with its item, maker and key", () => {
    expect(rows.length).toBe(7);
    expect(rows[0]).toMatchObject({ maker: "alpha", item: "Butterfly valves, wafer type" });
    expect(new Set(rows.map((r) => r.key)).size).toBe(rows.length);
  });
  it("counts progress on flagged rows only", () => {
    const flagged = rows.find((r) => r.review);
    expect(progressOf(rows, new Map())).toEqual({ flagged: 1, reviewed: 0 });
    expect(progressOf(rows, new Map([[flagged.key, {}]]))).toEqual({ flagged: 1, reviewed: 1 });
  });
  it("filters by status, reason, review state and search words", () => {
    const none = new Map();
    expect(filterRows(rows, { status: "fully matched" }, none).every((r) => r.status === "fully matched")).toBe(true);
    expect(filterRows(rows, { flag: "grade not stated" }, none)).toHaveLength(1);
    expect(filterRows(rows, { onlyCheck: true }, none).every((r) => r.review)).toBe(true);
    expect(filterRows(rows, { query: "epdm" }, none).length).toBeGreaterThan(0);
    const flagged = rows.find((r) => r.review);
    expect(filterRows(rows, { hideReviewed: true }, new Map([[flagged.key, {}]])).includes(flagged)).toBe(false);
  });
  it("groups flagged rows by page and says which are still pending", () => {
    const pages = pagesToCheck(rows, new Map());
    expect(pages).toHaveLength(1);
    expect(pages[0]).toMatchObject({ document: "alpha-catalogue.pdf", page: 6, flags: ["grade not stated"] });
    expect(pages[0].pending).toHaveLength(1);
    expect(pagesToCheck(rows, new Map([[pages[0].rows[0].key, {}]]))[0].pending).toHaveLength(0);
  });
});

describe("format", () => {
  it("formats scores, sizes and counts", () => {
    expect(percent(null)).toBe("not assessed");
    expect(percent(41.25)).toBe("41.3%");
    expect(fileSize(2048)).toBe("2 KB");
    expect(fileSize(3 * 1024 * 1024)).toBe("3.0 MB");
    expect(countsOf(rowsOf(report.makers[0]))["fully matched"]).toBe(3);
    expect(flagCounts(rowsOf(report.makers[0]))).toEqual({ "grade not stated": 1 });
  });
});

describe("flags and run summaries", () => {
  it("every reason has both an explanation and an instruction", () => {
    expect(Object.keys(FLAG_ACTION).sort()).toEqual(Object.keys(FLAG_HELP).sort());
  });
  it("shortens the model-call summary", () => {
    expect(callsSummary("model calls 0, from cache 254, tokens in 0 / out 0")).toBe("0 new · 254 cached");
    expect(callsSummary("12 calls")).toBe("12 calls");
    expect(callsSummary(null)).toBe("–");
  });
});
