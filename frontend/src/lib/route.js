/** The address in the browser's #hash decides which page is shown, so every page has its own link and the back button works. */
export function parseRoute(hash) {
  const [page, a, b, c] = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (page === "runs" && a) return { page: "run", id: a, tab: b ?? "overview", maker: c ?? null };
  if (page === "runs") return { page: "runs" };
  if (page === "compare" && a && b) return { page: "compare", a, b };
  return { page: "new" };
}

const part = (value) => encodeURIComponent(value);

export const links = {
  newRun: "#/new",
  runs: "#/runs",
  run: (id, tab = "overview", maker = null) => `#/runs/${part(id)}/${part(tab)}${maker ? `/${part(maker)}` : ""}`,
  compare: (a, b) => `#/compare/${part(a)}/${part(b)}`,
};
