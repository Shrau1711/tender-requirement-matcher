import axe from "axe-core";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import App from "./App";
import report from "./fixtures/sampleReport.json";

const run = { id: "abc", tender: "GeM-Bidding-DEMO", category: "valves", status: "done", created_at: "2026-10-13T08:00:00+00:00", finished_at: "2026-10-13T08:05:00+00:00", model_calls: "12 calls", error: null, progress: null };

function saved(items, existing = []) {
  const map = new Map(existing.map((r) => [r.key, r]));
  items.forEach((i) => (i.decision ? map.set(i.key, { ...i, updated_at: "now" }) : map.delete(i.key)));
  return [...map.values()];
}

beforeEach(() => {
  let store = [];
  vi.spyOn(api, "runs").mockResolvedValue([run]);
  vi.spyOn(api, "run").mockResolvedValue(run);
  vi.spyOn(api, "report").mockResolvedValue(report);
  vi.spyOn(api, "reviews").mockImplementation(async () => store);
  vi.spyOn(api, "saveReviews").mockImplementation(async (_, items) => (store = saved(items, store)));
  vi.spyOn(api, "config").mockResolvedValue({ max_model_calls: 300, max_upload_mb: 60 });
  vi.spyOn(api, "categories").mockResolvedValue([{ name: "valves", manufacturers: ["alpha", "beta"], documents: 4 }]);
  window.location.hash = "";
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const open = (hash) => { window.location.hash = hash; return render(<App />); };
const noContrast = { iframes: false, rules: { "color-contrast": { enabled: false } } };  // jsdom cannot inspect frames; the PDF frame has a title
async function violations(container) {
  const result = await axe.run(container, noContrast);
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html.slice(0, 90)).join(" | ")}`);
}

describe("the report", () => {
  it("opens on the overview with the best match and the ranking", async () => {
    open("#/runs/abc");
    expect(await screen.findByRole("heading", { name: "GeM-Bidding-DEMO" })).toBeInTheDocument();
    expect(screen.getByText("Best match")).toBeInTheDocument();
    expect(screen.getAllByText("87.5%").length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /Overview/, selected: true })).toBeInTheDocument();
  });

  it("moves between tabs with the keyboard", async () => {
    open("#/runs/abc");
    const overview = await screen.findByRole("tab", { name: /Overview/ });
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByRole("tab", { name: /Requirements/, selected: true })).toBeInTheDocument());
    expect(window.location.hash).toContain("/requirements");
  });

  it("shows a requirement's evidence, the source page, and saves a decision", async () => {
    open("#/runs/abc/requirements/alpha");
    fireEvent.click(await screen.findByRole("button", { name: /Open body material/ }));
    const panel = screen.getByRole("complementary", { name: "Requirement details" });
    expect(within(panel).getByTitle("alpha-catalogue.pdf, page 6")).toHaveAttribute("src", expect.stringContaining("alpha-catalogue.pdf#page=6"));
    fireEvent.change(within(panel).getByRole("textbox"), { target: { value: "checked on page 6" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Save decision" }));
    await waitFor(() => expect(api.saveReviews).toHaveBeenCalled());
    const [, items] = api.saveReviews.mock.calls[0];
    expect(items[0]).toMatchObject({ decision: "confirmed", status: null, note: "checked on page 6" });
    expect(JSON.parse(items[0].key)).toEqual(["alpha", "Butterfly valves, wafer type", "body_material", "Grey cast iron IS 210 FG 260", 1]);
    expect((await screen.findAllByText("Confirmed")).length).toBeGreaterThan(0);
  });

  it("filters the requirements and says how many are shown", async () => {
    open("#/runs/abc/requirements/alpha");
    await screen.findByText(/7 of 7 requirements shown/);
    fireEvent.click(screen.getByRole("button", { name: /grade not stated/ }));
    expect(screen.getByText(/1 of 7 requirements shown/)).toBeInTheDocument();
  });

  it("confirms every pending requirement on a page in one click", async () => {
    open("#/runs/abc/pages/alpha");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm 1 on this page" }));
    await waitFor(() => expect(api.saveReviews).toHaveBeenCalledWith("abc", expect.arrayContaining([expect.objectContaining({ decision: "confirmed" })])));
    expect(await screen.findByText(/1 of 1/)).toBeInTheDocument();
  });

  it("tells the reviewer what to check for each flagged row", async () => {
    open("#/runs/abc/pages/alpha");
    expect((await screen.findAllByText("Tender asks")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Look for the exact one/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Document says/).length).toBeGreaterThan(0);
  });

  it("lets a mistaken confirmation be undone: from the message, from the page, and per row", async () => {
    open("#/runs/abc/pages/alpha");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm 1 on this page" }));
    expect(await screen.findByText(/Confirmed 1 on page 6/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(screen.getByText(/0 of 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(screen.getByText(/1 of 1/)).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Only pages with rows still to review"));  // the reviewed page is hidden until the filter is off
    fireEvent.click(await screen.findByRole("button", { name: /Undo 1 reviewed/ }));
    await waitFor(() => expect(screen.getByText(/0 of 1/)).toBeInTheDocument());
  });

  it("compares the manufacturers side by side", async () => {
    open("#/runs/abc/compare");
    expect(await screen.findByRole("heading", { name: "Manufacturers side by side" })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Only where manufacturers differ"));
    expect(screen.getByText(/of 7 requirements/)).toBeInTheDocument();
  });

  it("lists what to confirm with the manufacturer and links to the tender", async () => {
    open("#/runs/abc/confirm");
    expect(await screen.findByRole("heading", { name: "To confirm with the manufacturer" })).toBeInTheDocument();
    expect(screen.getByText(/3 of 3/)).toBeInTheDocument();
  });

  it("switches to the dark theme and remembers it", async () => {
    open("#/runs/abc");
    fireEvent.click(await screen.findByRole("button", { name: "Switch to the dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to the light theme" })).toBeInTheDocument();
  });
});

describe("the other pages", () => {
  it("starts a run: only PDFs are accepted and the cost is explained", async () => {
    open("#/new");
    expect(await screen.findByText(/at most 300 per run/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start matching" })).toBeDisabled();
    const input = document.querySelector("input[type=file]");
    fireEvent.change(input, { target: { files: [new File(["x"], "notes.txt")] } });
    expect(screen.getByRole("alert")).toHaveTextContent("not a PDF");
    fireEvent.change(input, { target: { files: [new File(["%PDF"], "bid.pdf", { type: "application/pdf" })] } });
    expect(screen.getByRole("button", { name: "Start matching" })).toBeEnabled();
    const advanced = screen.getByText("Advanced").closest("details");
    expect(advanced).not.toHaveAttribute("open");  // the manual category choice is tucked away
    const category = within(advanced).getByLabelText("Product category (optional)");
    expect(category).toHaveValue("");  // by default each item's category is found in the tender
    expect(within(advanced).getByRole("option", { name: /Find it in the tender/ })).toBeInTheDocument();
  });

  it("shows no note when the call limit is 0, and the server's plain refusal after an upload", async () => {
    const config = vi.spyOn(api, "config").mockResolvedValue({ max_model_calls: 0, max_upload_mb: 60 });
    vi.spyOn(api, "start").mockRejectedValue(new Error("This demo replays saved examples only."));
    open("#/new");
    await waitFor(() => expect(config).toHaveBeenCalled());
    await act(async () => {});  // let the limits arrive
    expect(document.querySelector(".notice")).toBeNull();
    expect(screen.queryByText(/replays saved examples|per run/)).not.toBeInTheDocument();
    fireEvent.change(document.querySelector("input[type=file]"), { target: { files: [new File(["%PDF"], "bid.pdf", { type: "application/pdf" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Start matching" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/^This demo replays saved examples only\.$/);
  });

  it("starts a run with a chosen category, or without one so the server finds it", async () => {
    const start = vi.spyOn(api, "start").mockResolvedValue(run);
    open("#/new");
    await screen.findByText(/at most 300 per run/);
    fireEvent.change(document.querySelector("input[type=file]"), { target: { files: [new File(["%PDF"], "bid.pdf", { type: "application/pdf" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Start matching" }));
    await waitFor(() => expect(start).toHaveBeenCalledWith(expect.objectContaining({ category: "" })));
  });

  it("shows the server's refusal of an upload as plain text", async () => {
    vi.spyOn(api, "start").mockRejectedValue(new Error("This demo replays saved examples only."));
    open("#/new");
    await screen.findByText(/at most 300 per run/);
    fireEvent.change(document.querySelector("input[type=file]"), { target: { files: [new File(["%PDF"], "bid.pdf", { type: "application/pdf" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Start matching" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/^This demo replays saved examples only\.$/);
  });

  it("starts a run with the category chosen under Advanced", async () => {
    const start = vi.spyOn(api, "start").mockResolvedValue(run);
    open("#/new");
    await screen.findByRole("option", { name: /^valves/ });
    fireEvent.change(document.querySelector("input[type=file]"), { target: { files: [new File(["%PDF"], "bid.pdf", { type: "application/pdf" })] } });
    fireEvent.click(screen.getByText("Advanced"));
    fireEvent.change(screen.getByLabelText("Product category (optional)"), { target: { value: "valves" } });
    fireEvent.click(screen.getByRole("button", { name: "Start matching" }));
    await waitFor(() => expect(start).toHaveBeenCalledWith(expect.objectContaining({ category: "valves" })));
  });

  it("says why a run could not be deleted or renamed, from the list and from the report", async () => {
    const kept = "The saved examples cannot be deleted or renamed in this demo.";
    vi.spyOn(api, "remove").mockRejectedValue(new Error(kept));
    vi.spyOn(api, "rename").mockRejectedValue(new Error(kept));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    open("#/runs");
    fireEvent.click(await screen.findByRole("button", { name: "Delete GeM-Bidding-DEMO" }));
    expect(await screen.findByText(`Could not delete: ${kept}`)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rename GeM-Bidding-DEMO" }));
    fireEvent.submit(document.querySelector("form"));
    expect(await screen.findByText(`Could not rename: ${kept}`)).toBeInTheDocument();
    cleanup();
    open("#/runs/abc");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(await screen.findByText(`Could not delete: ${kept}`)).toBeInTheDocument();
    expect(window.location.hash).toBe("#/runs/abc");  // still on the report
  });

  it("lists, searches and compares runs", async () => {
    vi.spyOn(api, "runs").mockResolvedValue([run, { ...run, id: "def", tender: "Pump tender" }]);
    open("#/runs");
    expect(await screen.findByRole("link", { name: "Pump tender" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search runs"), { target: { value: "pump" } });
    expect(screen.queryByRole("link", { name: "GeM-Bidding-DEMO" })).not.toBeInTheDocument();
  });

  it("shows what a running job is doing", async () => {
    vi.spyOn(api, "run").mockResolvedValue({ ...run, status: "running", progress: "Searching the documents for evidence on 40 requirements" });
    open("#/runs/abc");
    expect(await screen.findByText(/Searching the documents for evidence on 40 requirements/)).toBeInTheDocument();
  });

  it("shows what a run will cost and lets the person say yes or no", async () => {
    const estimate = { requirements: 12, questions: 40, tokens: 200000, rupees: 20, minutes_low: 2, minutes_high: 6, notes: ["Only part of the tender was evaluated."] };
    vi.spyOn(api, "run").mockResolvedValue({ ...run, status: "awaiting", estimate });
    const proceed = vi.spyOn(api, "proceed").mockResolvedValue({});
    open("#/runs/abc");
    expect(await screen.findByRole("heading", { name: "Ready to match" })).toBeInTheDocument();
    expect(screen.getByText(/₹20/)).toBeInTheDocument();
    expect(screen.getByText(/2–6 minutes/)).toBeInTheDocument();
    expect(screen.getByText("Only part of the tender was evaluated.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
    await waitFor(() => expect(proceed).toHaveBeenCalledWith("abc"));
  });

  it("says nothing is spent when a run was cancelled", async () => {
    vi.spyOn(api, "run").mockResolvedValue({ ...run, status: "cancelled", error: "Cancelled" });
    open("#/runs/abc");
    expect(await screen.findByRole("heading", { name: "Cancelled" })).toBeInTheDocument();
  });

  it("says plainly when a run failed", async () => {
    vi.spyOn(api, "run").mockResolvedValue({ ...run, status: "failed", error: "ClientError: 429" });
    open("#/runs/abc");
    expect(await screen.findByRole("alert")).toHaveTextContent("ClientError: 429");
  });
});

describe("accessibility (axe, without colour contrast, which tokens.test.js checks)", () => {
  it.each(["#/new", "#/runs", "#/runs/abc", "#/runs/abc/requirements/alpha", "#/runs/abc/compare", "#/runs/abc/pages/alpha", "#/runs/abc/confirm", "#/runs/abc/method"])("%s has no violations", async (hash) => {
    const { container } = open(hash);
    await waitFor(() => expect(document.querySelector("main h1, main h2")).not.toBeNull());
    await new Promise((r) => setTimeout(r, 30));
    expect(await violations(container)).toEqual([]);
  });

  it("has no violations with the details panel open", async () => {
    const { container } = open("#/runs/abc/requirements/alpha");
    fireEvent.click(await screen.findByRole("button", { name: /Open body material/ }));
    expect(await violations(container)).toEqual([]);
  });
});

describe("the tender layout tab", () => {
  const layout = {
    tender: "GeM-Bidding-DEMO", requirements: 3, shared_rows: 1,
    items: [
      { title: "BUTTERFLY VALVE DN 200", category: "valves", family: "butterfly valve", family_from: "title", not_named: ["face_to_face_dimension"],
        rows: [{ name: "Standard", value: "IS 13095", file: "bid.pdf", page: 2, requirements: ["design_standard equals IS 13095"], shared_with: ["GATE VALVE"], standards: ["IS13095"] }] },
      { title: "VALVE MOTORISED 300", category: "valves", family: null, family_from: null, not_named: [], rows: [] },
    ],
    standards: [{ name: "API598", also_written: ["API 598"], named_together: ["API600"] }],
  };

  it("shows items, their family, shared rows with a link to the tender page, and the standards", async () => {
    vi.spyOn(api, "layout").mockResolvedValue(layout);
    open("#/runs/abc/layout");
    const item = await screen.findByRole("region", { name: "BUTTERFLY VALVE DN 200" });
    expect(api.layout).toHaveBeenCalledWith("abc");
    expect(within(item).getByText(/Family: butterfly valve \(named in the item's title\)/)).toBeInTheDocument();
    expect(within(item).getByText(/also for GATE VALVE/)).toBeInTheDocument();
    expect(within(item).getByRole("link", { name: "page 2" })).toHaveAttribute("href", expect.stringContaining("/runs/abc/tender/bid.pdf#page=2"));
    expect(within(item).getByText("1 attributes of this kind of product the reading does not name")).toBeInTheDocument();
    expect(screen.getByText(/Family: not named/)).toBeInTheDocument();
    expect(screen.getByText(/named together with API600 \(not necessarily equivalent\)/)).toBeInTheDocument();
  });

  it("is only fetched when the tab is opened, and says plainly when the reading is not saved", async () => {
    const spy = vi.spyOn(api, "layout").mockRejectedValue(new Error("This tender's reading is not saved yet, so its layout cannot be shown without asking the model."));
    open("#/runs/abc/overview");
    await screen.findByRole("heading", { name: "GeM-Bidding-DEMO" });
    expect(spy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: /Tender layout/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not saved yet");
  });

  it("has no accessibility problems axe can find", async () => {
    vi.spyOn(api, "layout").mockResolvedValue(layout);
    const { container } = open("#/runs/abc/layout");
    await screen.findByRole("region", { name: "BUTTERFLY VALVE DN 200" });
    expect(await violations(container)).toEqual([]);
  });
});
