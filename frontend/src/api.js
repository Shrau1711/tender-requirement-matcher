const base = () => (window.APP_CONFIG?.apiUrl ?? "http://localhost:8000").replace(/\/$/, "");
const part = encodeURIComponent;

async function request(path, options) {
  const response = await fetch(`${base()}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : body.detail;
    throw new Error(detail ?? `The server answered ${response.status}.`);
  }
  return response;
}

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const DOWNLOADS = { md: "report.md", json: "report", xlsx: "report.xlsx" };

export const api = {
  config: async () => (await request("/config")).json(),
  categories: async () => (await request("/categories")).json(),
  runs: async () => (await request("/runs")).json(),
  run: async (id) => (await request(`/runs/${part(id)}`)).json(),
  report: async (id) => (await request(`/runs/${part(id)}/report`)).json(),
  layout: async (id) => (await request(`/runs/${part(id)}/layout`)).json(),
  rename: async (id, name) => (await request(`/runs/${part(id)}`, json("PATCH", { name }))).json(),
  proceed: async (id) => (await request(`/runs/${part(id)}/proceed`, { method: "POST" })).json(),
  cancel: async (id) => (await request(`/runs/${part(id)}/cancel`, { method: "POST" })).json(),
  remove: async (id) => request(`/runs/${part(id)}`, { method: "DELETE" }),
  reviews: async (id) => (await request(`/runs/${part(id)}/reviews`)).json(),
  saveReviews: async (id, items) => (await request(`/runs/${part(id)}/reviews`, json("PUT", { items }))).json(),
  start: async ({ files, category, name }) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    if (category) form.append("category", category);  // left out, the server finds it in the tender
    if (name) form.append("name", name);
    form.append("ask_first", "true");  // the run stops with its estimate until the person says yes
    return (await request("/runs", { method: "POST", body: form })).json();
  },
  addDocument: async ({ category, manufacturer, file, url, source }) => {
    const form = new FormData();
    form.append("manufacturer", manufacturer.trim());
    if (file) form.append("file", file);
    if (url) form.append("url", url.trim());
    if (source) form.append("source", source.trim());
    return (await request(`/categories/${part(category)}/documents`, { method: "POST", body: form })).json();
  },
  downloadUrl: (id, kind) => `${base()}/runs/${part(id)}/${DOWNLOADS[kind]}`,
  documentUrl: (category, maker, file, page) => `${base()}/categories/${part(category)}/manufacturers/${part(maker)}/documents/${part(file)}#page=${page}`,
  tenderUrl: (runId, file, page) => `${base()}/runs/${part(runId)}/tender/${part(file)}#page=${page}`,
};
