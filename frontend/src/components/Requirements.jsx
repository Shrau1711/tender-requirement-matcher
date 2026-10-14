import { useMemo, useState } from "react";
import { STATUSES, flagCounts } from "../lib/format";
import { decisionLabel, filterRows, isPending, progressOf, rowsOf } from "../lib/review";
import DataTable from "./DataTable";
import { EmptyState } from "./States";
import ReviewPanel from "./ReviewPanel";
import StatusBadge from "./StatusBadge";

const NO_FILTERS = { status: null, flag: null, onlyCheck: false, hideReviewed: false, query: "" };

function ReviewCell({ row, decision }) {
  if (decision) return <span className={`badge ${decision.decision === "changed" ? "badge-changed" : "badge-done"}`}>{decisionLabel(decision)}</span>;
  return row.review ? <span className="badge badge-review">To check</span> : <span className="muted">–</span>;
}

export default function Requirements({ report, run, makerName, onMaker, decisions, save }) {
  const [filters, setFilters] = useState(NO_FILTERS);
  const [selected, setSelected] = useState(null);
  const maker = report.makers.find((m) => m.manufacturer === makerName) ?? report.makers[0];
  const rows = useMemo(() => (maker ? rowsOf(maker) : []), [maker]);
  const visible = useMemo(() => filterRows(rows, filters, decisions), [rows, filters, decisions]);
  const counts = useMemo(() => Object.fromEntries(STATUSES.map((s) => [s, rows.filter((r) => r.status === s).length])), [rows]);
  const flags = Object.entries(flagCounts(rows));
  const { flagged, reviewed } = progressOf(rows, decisions);
  const row = rows.find((r) => r.key === selected) ?? null;
  const manyItems = new Set(rows.map((r) => r.item)).size > 1;  // with one item the column would only repeat its name
  const set = (change) => setFilters({ ...filters, ...change });

  const columns = useMemo(() => [
    { key: "requirement", label: "Requirement", sortValue: (r) => `${r.attribute} ${r.wanted}`, render: (r) => (
      <button className="row-title" onClick={() => setSelected(r.key)} aria-label={`Open ${r.attribute.replaceAll("_", " ")}, ${r.wanted}`}>
        <span className="attribute">{r.attribute.replaceAll("_", " ")}</span><span className="wanted">{r.wanted}</span>
      </button>
    ) },
    ...(manyItems ? [{ key: "item", label: "Item", render: (r) => <span className="cell-sub">{r.item}</span> }] : []),
    { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} flags={r.flags} review={r.review} /> },
    { key: "score", label: "Score", numeric: true },
    { key: "review", label: "Review", sortValue: (r) => (decisions.has(r.key) ? 2 : r.review ? 0 : 1), render: (r) => <ReviewCell row={r} decision={decisions.get(r.key)} /> },
  ], [decisions, manyItems]);

  function next() {
    const pending = visible.filter((r) => isPending(r, decisions) && r.key !== selected);
    const after = pending.find((r) => visible.indexOf(r) > visible.findIndex((v) => v.key === selected)) ?? pending[0];
    setSelected(after ? after.key : null);
  }

  if (!maker) return <EmptyState title="No manufacturers">This report has no manufacturers to show.</EmptyState>;
  return (
    <div className="stack">
      <section className="card" aria-label="Filters">
        <div className="table-tools">
          <label className="field"><span>Manufacturer</span>
            <select value={maker.manufacturer} onChange={(e) => { onMaker(e.target.value); setSelected(null); setFilters(NO_FILTERS); }}>
              {report.makers.map((m) => <option key={m.manufacturer}>{m.manufacturer}</option>)}
            </select>
          </label>
          <label className="field grow"><span>Search requirements and evidence</span><input type="search" value={filters.query} onChange={(e) => set({ query: e.target.value })} placeholder="e.g. impeller, IS 210, 16 bar" /></label>
          <label className="check"><input type="checkbox" checked={filters.onlyCheck} onChange={(e) => set({ onlyCheck: e.target.checked })} />Only rows to check ({maker.review_needed})</label>
          <label className="check"><input type="checkbox" checked={filters.hideReviewed} onChange={(e) => set({ hideReviewed: e.target.checked })} />Hide reviewed ({reviewed} of {flagged})</label>
        </div>
        <div className="chips" role="group" aria-label="Filter by status">
          <span className="label-caps">Status</span>
          {STATUSES.map((s) => <button key={s} className="chip" aria-pressed={filters.status === s} onClick={() => set({ status: filters.status === s ? null : s })}>{s} ({counts[s]})</button>)}
        </div>
        {flags.length > 0 && (
          <div className="chips" role="group" aria-label="Filter by reason to check">
            <span className="label-caps">Reason to check</span>
            {flags.map(([name, n]) => <button key={name} className="chip" aria-pressed={filters.flag === name} onClick={() => set({ flag: filters.flag === name ? null : name })}>{name} ({n})</button>)}
          </div>
        )}
        <p className="hint" aria-live="polite">{visible.length} of {rows.length} requirements shown</p>
      </section>
      <div className={row ? "review-layout with-panel" : "review-layout"}>
        {visible.length === 0
          ? <EmptyState title="No requirements match">Change or clear the filters.<br /><button className="button secondary small" onClick={() => setFilters(NO_FILTERS)}>Clear filters</button></EmptyState>
          : <DataTable caption={`${maker.manufacturer}: requirements`} columns={columns} rows={visible} rowKey={(r) => r.key} selectedKey={selected} onSelect={(r) => setSelected(r.key)} />}
        {row && <ReviewPanel row={row} run={run} decision={decisions.get(row.key)} onSave={save} onNext={next} onClose={() => setSelected(null)} />}
      </div>
    </div>
  );
}
