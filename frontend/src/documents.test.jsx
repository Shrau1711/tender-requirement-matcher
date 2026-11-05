import axe from "axe-core";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import App from "./App";

const added = { category: "valves", manufacturer: "ksb", file: "boax.pdf", source_url: "https://ksb.com/boax.pdf", date_downloaded: "2026-11-04", chunks: 34, problem: null };

beforeEach(() => {
  vi.spyOn(api, "runs").mockResolvedValue([]);
  vi.spyOn(api, "categories").mockResolvedValue([{ name: "valves", manufacturers: ["delval", "ksb"], documents: 4 }, { name: "pumps", manufacturers: ["grundfos"], documents: 2 }]);
  vi.spyOn(api, "addDocument").mockResolvedValue(added);
  window.location.hash = "#/documents";
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function fill({ maker = "ksb", from = "Upload a PDF" } = {}) {
  render(<App />);
  await screen.findByRole("option", { name: "valves" });  // the categories have loaded, so choosing one sticks
  fireEvent.change(screen.getByLabelText("Product category"), { target: { value: "valves" } });
  fireEvent.change(screen.getByLabelText(/^Manufacturer/), { target: { value: maker } });
  fireEvent.click(screen.getByLabelText(from));
}
const pdf = new File(["%PDF-1.4"], "boax.pdf", { type: "application/pdf" });
const button = () => screen.getByRole("button", { name: "Add the document" });

describe("adding a manufacturer document", () => {
  it("is a page of its own, linked from the side bar", async () => {
    window.location.hash = "";
    render(<App />);
    fireEvent.click(await screen.findByRole("link", { name: "Add documents" }));
    expect(await screen.findByRole("heading", { name: "Add a manufacturer document" })).toBeInTheDocument();
  });

  it("offers the chosen category's manufacturers and uploads a PDF with its source", async () => {
    await fill();
    expect([...document.querySelectorAll("#makers option")].map((o) => o.value)).toEqual(["delval", "ksb"]);
    expect(button()).toBeDisabled();  // no file yet
    fireEvent.change(screen.getByLabelText("PDF"), { target: { files: [pdf] } });
    fireEvent.change(screen.getByLabelText(/^Where it came from/), { target: { value: "https://ksb.com/boax.pdf" } });
    fireEvent.click(button());
    await waitFor(() => expect(api.addDocument).toHaveBeenCalledWith({ category: "valves", manufacturer: "ksb", file: pdf, source: "https://ksb.com/boax.pdf" }));
    expect(await screen.findByText("Added boax.pdf to ksb (valves), recorded with the date 2026-11-04. 34 passages are now searchable.")).toHaveAttribute("role", "status");
  });

  it("fetches from an address, for a new manufacturer too", async () => {
    await fill({ maker: "new-maker", from: "From a web address" });
    fireEvent.change(screen.getByLabelText(/^Address of the PDF/), { target: { value: "https://m.com/sheet.pdf" } });
    fireEvent.click(button());
    await waitFor(() => expect(api.addDocument).toHaveBeenCalledWith({ category: "valves", manufacturer: "new-maker", url: "https://m.com/sheet.pdf" }));
  });

  it("shows the server's refusal, and a saved file that could not be read yet", async () => {
    api.addDocument.mockRejectedValueOnce(new Error("This document is already in ksb's folder."));
    await fill();
    fireEvent.change(screen.getByLabelText("PDF"), { target: { files: [pdf] } });
    fireEvent.click(button());
    expect(await screen.findByRole("alert")).toHaveTextContent("already in ksb's folder");

    api.addDocument.mockResolvedValueOnce({ ...added, chunks: null, problem: "Saved and recorded, but reading it failed. The next run tries again." });
    fireEvent.change(screen.getByLabelText("PDF"), { target: { files: [pdf] } });
    fireEvent.click(button());
    expect(await screen.findByText(/Saved and recorded, but reading it failed/)).toHaveAttribute("role", "status");
  });

  it("has no accessibility problems axe can find", async () => {
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: "Add a manufacturer document" });
    const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations.map((v) => v.id)).toEqual([]);
  });
});
