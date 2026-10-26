import { useRef, useState } from "react";
import { api } from "../api";
import Icon from "../components/common/Icon";
import { ErrorState } from "../components/common/States";
import { useAsync } from "../hooks/useAsync";
import { fileSize } from "../lib/format";

const isPdf = (file) => file.name.toLowerCase().endsWith(".pdf");

export default function UploadPage({ onStarted }) {
  const { data: categories, error: loadError } = useAsync(api.categories, []);
  const { data: limits } = useAsync(api.config, []);
  const [files, setFiles] = useState([]);
  const [category, setCategory] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [over, setOver] = useState(false);
  const input = useRef();
  const chosen = category || categories?.[0]?.name || "";
  const totalMb = files.reduce((sum, f) => sum + f.size, 0) / (1024 * 1024);
  const tooBig = limits && totalMb > limits.max_upload_mb;

  function add(list) {
    const incoming = [...list];
    const bad = incoming.filter((f) => !isPdf(f));
    setError(bad.length ? `${bad.map((f) => f.name).join(", ")} ${bad.length > 1 ? "are" : "is"} not a PDF and was left out.` : null);
    setFiles((current) => [...current, ...incoming.filter(isPdf).filter((f) => !current.some((c) => c.name === f.name))]);
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      onStarted(await api.start({ files, category: chosen, name: name.trim() }));
    } catch (e) {
      setError(e.message); setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="stack" aria-labelledby="upload-title">
      <div className="page-head"><div><h1 id="upload-title" tabIndex={-1}>Match a tender</h1><p>Upload a tender's PDFs and see which manufacturers can supply it, with the page of evidence behind every answer.</p></div></div>
      <div className="card form-grid">
        <div className="field">
          <span className="field-label" id="files-label">Tender PDFs</span>
          <label
            className={over ? "dropzone over" : "dropzone"}
            onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }}
          >
            <input ref={input} type="file" accept="application/pdf" multiple aria-labelledby="files-label" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
            <Icon name="upload" size={22} />
            <p><strong>Choose PDFs</strong> or drop them here</p>
            <p className="hint">The bid document and any specification attached to it.</p>
          </label>
          {files.length > 0 && (
            <ul className="file-list" aria-label="Chosen files">
              {files.map((f) => (
                <li key={f.name}>
                  <span>{f.name} <span className="hint">{fileSize(f.size)}</span></span>
                  <button type="button" className="icon-button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))}><Icon name="x" /></button>
                </li>
              ))}
            </ul>
          )}
          {tooBig && <p className="problem" role="alert">These files add up to {totalMb.toFixed(1)} MB. The limit is {limits.max_upload_mb} MB.</p>}
        </div>
        <label className="field"><span>Product category</span>
          <select value={chosen} onChange={(e) => setCategory(e.target.value)} required>
            {(categories ?? []).map((c) => <option key={c.name} value={c.name}>{c.name} ({c.manufacturers.length} manufacturers, {c.documents} documents)</option>)}
          </select>
        </label>
        <label className="field"><span>Name for this run <span className="hint">(optional)</span></span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Defaults to the file name" />
        </label>
        {limits && (
          <p className="notice">
            Answers the system has found before are reused and cost nothing. A tender it has not seen makes calls to the language model, at most {limits.max_model_calls} per run. Before anything is spent you will see an estimate of the cost and time, and can cancel.
          </p>
        )}
        {(error || loadError) && <div className="problem" role="alert">{error || `Could not reach the server: ${loadError}`}</div>}
        <div><button className="button" disabled={busy || !files.length || !chosen || tooBig}>{busy ? "Uploading…" : "Start matching"}</button></div>
      </div>
      {loadError && <ErrorState title="The server is not reachable">Check that the backend is running, then reload this page.</ErrorState>}
    </form>
  );
}
