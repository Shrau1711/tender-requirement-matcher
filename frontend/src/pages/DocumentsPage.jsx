import { useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks/useAsync";

const EMPTY = { category: "", manufacturer: "", from: "file", file: null, url: "", source: "" };

/** Add a manufacturer's document: upload a PDF or give its address. The server saves it, records its source and date in sources.csv, and makes it searchable. */
export default function DocumentsPage() {
  const { data: categories, error: loadError } = useAsync(api.categories, []);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [added, setAdded] = useState(null);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.type === "file" ? e.target.files[0] ?? null : e.target.value });
  const makers = (categories ?? []).find((c) => c.name === form.category)?.manufacturers ?? [];
  const ready = form.category && form.manufacturer.trim() && (form.from === "file" ? form.file : form.url.trim());

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError(null); setAdded(null);
    try {
      const { from, file, url, source, ...rest } = form;
      setAdded(await api.addDocument(from === "file" ? { ...rest, file, source } : { ...rest, url }));
      setForm({ ...EMPTY, category: form.category });
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="stack" aria-labelledby="documents-title">
      <div className="page-head"><div><h1 id="documents-title" tabIndex={-1}>Add a manufacturer document</h1><p>Upload a catalogue or data sheet, or give its web address. It is saved in the manufacturer's folder, its source and date are recorded, and the next run can search it.</p></div></div>
      <div className="card form-grid">
        <label className="field"><span>Product category</span>
          <select value={form.category} onChange={set("category")}>
            <option value="">Choose a category</option>
            {(categories ?? []).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label className="field"><span>Manufacturer <span className="hint">(choose one, or type a new name in lower case, as in l_and_t)</span></span>
          <input type="text" list="makers" value={form.manufacturer} onChange={set("manufacturer")} />
          <datalist id="makers">{makers.map((m) => <option key={m} value={m} />)}</datalist>
        </label>
        <fieldset className="choice">
          <legend className="field-label">The document</legend>
          <label className="radio"><input type="radio" name="from" value="file" checked={form.from === "file"} onChange={set("from")} />Upload a PDF</label>
          <label className="radio"><input type="radio" name="from" value="url" checked={form.from === "url"} onChange={set("from")} />From a web address</label>
        </fieldset>
        {form.from === "file" ? (
          <>
            <label className="field"><span>PDF</span>
              <input key={added?.file ?? "empty"} type="file" accept="application/pdf" onChange={set("file")} />
            </label>
            <label className="field"><span>Where it came from <span className="hint">(optional web address, recorded as its source)</span></span>
              <input type="url" value={form.source} onChange={set("source")} placeholder="https://" />
            </label>
          </>
        ) : (
          <label className="field"><span>Address of the PDF <span className="hint">(fetched politely: the site's robots.txt is obeyed)</span></span>
            <input type="url" value={form.url} onChange={set("url")} placeholder="https://" />
          </label>
        )}
        <p className="hint">Pages that are only a picture are read by the page reader set on the server (OCR). The default, the language model, makes a paid call for each such page.</p>
        {(error || loadError) && <div className="problem" role="alert">{error || `Could not reach the server: ${loadError}`}</div>}
        {added && (
          <p className={added.problem ? "problem" : "notice"} role="status">
            {added.problem ?? `Added ${added.file} to ${added.manufacturer} (${added.category}), recorded with the date ${added.date_downloaded}. ${added.chunks} passages are now searchable.`}
          </p>
        )}
        <div><button className="button" disabled={busy || !ready}>{busy ? "Adding…" : "Add the document"}</button></div>
      </div>
    </form>
  );
}
