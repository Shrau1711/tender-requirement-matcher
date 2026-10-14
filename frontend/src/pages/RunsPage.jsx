import { useMemo, useState } from "react";
import { api } from "../api";
import DataTable from "../components/DataTable";
import { EmptyState } from "../components/States";
import { useNotify } from "../components/Notifier";
import { go } from "../hooks/useRoute";
import { callsSummary, shortDate } from "../lib/format";
import { links } from "../lib/route";
import { matches } from "../lib/tables";

const STATUS_BADGE = { done: "badge-full", failed: "badge-missing", running: "badge-partial", queued: "badge-unsupported" };

function RenameForm({ run, onSave, onCancel }) {
  const [text, setText] = useState(run.tender);
  return (
    <form className="table-tools" style={{ margin: 0 }} onSubmit={(e) => { e.preventDefault(); onSave(text); }}>
      <input type="text" value={text} onChange={(e) => setText(e.target.value)} aria-label="New name" maxLength={200} autoFocus />
      <button className="button small">Save</button>
      <button type="button" className="button secondary small" onClick={onCancel}>Cancel</button>
    </form>
  );
}

export default function RunsPage({ runs, refresh }) {
  const notify = useNotify();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState(null);
  const [picked, setPicked] = useState([]);
  const shown = useMemo(() => runs.filter((r) => (!status || r.status === status) && matches(`${r.tender} ${r.category}`, query)), [runs, query, status]);

  async function rename(run, name) {
    try { await api.rename(run.id, name); setEditing(null); refresh(); notify("Run renamed"); } catch (e) { notify(`Could not rename: ${e.message}`); }
  }
  async function remove(run) {
    if (!window.confirm(`Delete "${run.tender}" and its report?`)) return;
    try { await api.remove(run.id); setPicked(picked.filter((id) => id !== run.id)); refresh(); notify("Run deleted"); } catch (e) { notify(`Could not delete: ${e.message}`); }
  }
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((p) => p !== id) : [...picked, id].slice(-2));

  const columns = useMemo(() => [
    { key: "pick", label: "Compare", sortable: false, render: (r) => <input type="checkbox" disabled={r.status !== "done"} checked={picked.includes(r.id)} onChange={() => toggle(r.id)} aria-label={`Select ${r.tender} to compare`} /> },
    { key: "tender", label: "Tender", render: (r) => (editing === r.id ? <RenameForm run={r} onSave={(name) => rename(r, name)} onCancel={() => setEditing(null)} /> : <a href={links.run(r.id)}>{r.tender}</a>) },
    { key: "category", label: "Category" },
    { key: "status", label: "Status", render: (r) => <span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status}</span> },
    { key: "created_at", label: "Started", render: (r) => <span style={{ whiteSpace: "nowrap" }}>{shortDate(r.created_at)}</span> },
    { key: "model_calls", label: "Model calls", render: (r) => <span className="cell-sub" style={{ whiteSpace: "nowrap" }}>{callsSummary(r.model_calls)}</span> },
    { key: "actions", label: "Actions", sortable: false, render: (r) => <span className="actions"><a className="button secondary small" href={links.run(r.id)}>Open</a><button className="button secondary small" onClick={() => setEditing(r.id)} aria-label={`Rename ${r.tender}`}>Rename</button><button className="button danger small" onClick={() => remove(r)} aria-label={`Delete ${r.tender}`}>Delete</button></span> },
  ], [picked, editing]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="stack">
      <div className="page-head">
        <div><h1 id="runs-title" tabIndex={-1}>Runs</h1><p>Every tender you have matched. Pick two finished runs to compare them.</p></div>
        <div className="actions">
          <button className="button dark" disabled={picked.length !== 2} onClick={() => go(links.compare(picked[0], picked[1]))}>Compare selected ({picked.length}/2)</button>
          <a className="button" href={links.newRun}>New run</a>
        </div>
      </div>
      {runs.length === 0 ? <EmptyState title="No runs yet" action={<a className="button" href={links.newRun}>Match a tender</a>}>Upload a tender to get started.</EmptyState> : (
        <section className="card">
          <div className="table-tools">
            <label className="field grow"><span>Search runs</span><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
            <label className="field"><span>Status</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{["done", "running", "queued", "failed"].map((s) => <option key={s}>{s}</option>)}</select></label>
          </div>
          {shown.length ? <DataTable caption="Runs" columns={columns} rows={shown} rowKey={(r) => r.id} pageSize={15} /> : <EmptyState title="No runs match">Change the search or the status.</EmptyState>}
        </section>
      )}
    </div>
  );
}
