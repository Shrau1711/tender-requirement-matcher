import { useMemo, useState } from "react";
import { api } from "../../api";
import { pagesToCheck, progressOf, rowsOf } from "../../lib/review";
import FlaggedRow from "./FlaggedRow";
import { EmptyState } from "../common/States";

const clear = (rows) => rows.map((r) => ({ key: r.key, decision: null }));

export default function PagesToCheck({ report, run, makerName, onMaker, decisions, save }) {
  const [onlyPending, setOnlyPending] = useState(true);
  const maker = report.makers.find((m) => m.manufacturer === makerName) ?? report.makers[0];
  const rows = useMemo(() => (maker ? rowsOf(maker) : []), [maker]);
  const pages = pagesToCheck(rows, decisions);
  const shown = onlyPending ? pages.filter((p) => p.pending.length) : pages;
  const { flagged, reviewed } = progressOf(rows, decisions);
  if (!maker) return <EmptyState title="No manufacturers">This report has no manufacturers to show.</EmptyState>;

  function confirmPage(page) {
    const items = page.pending.map((r) => ({ key: r.key, decision: "confirmed" }));
    save(items, `Confirmed ${items.length} on page ${page.page}`, { label: "Undo", run: () => save(clear(page.pending), `Undid ${items.length} on page ${page.page}`) });
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="table-tools">
          <label className="field"><span>Manufacturer</span><select value={maker.manufacturer} onChange={(e) => onMaker(e.target.value)}>{report.makers.map((m) => <option key={m.manufacturer}>{m.manufacturer}</option>)}</select></label>
          <label className="check"><input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} />Only pages with rows still to review</label>
        </div>
        <p><strong>{reviewed} of {flagged}</strong> flagged requirements reviewed</p>
        <div className="meter" role="img" aria-label={`${reviewed} of ${flagged} reviewed`}><span style={{ "--value": `${flagged ? (100 * reviewed) / flagged : 0}%` }} /></div>
        <p className="hint">Open the page, then go through the requirements listed under it. Each one says what the tender asks, what the document says, and what to check. Confirm a row when you agree with the result; every confirmation can be undone.</p>
      </section>
      {shown.length === 0 ? <EmptyState title={flagged ? "Everything on these pages is reviewed" : "Nothing to check"}>{flagged ? "Untick the filter to see the pages again." : "No requirement for this manufacturer needs a person's look."}</EmptyState> : (
        <ul className="page-list">
          {shown.map((p) => {
            const done = p.rows.length - p.pending.length;
            return (
              <li key={`${p.document}#${p.page}`} className="page-card">
                <div className="page-head-row">
                  <div className="what">
                    <a href={api.documentUrl(run.category, maker.manufacturer, p.document, p.page)} target="_blank" rel="noreferrer">{p.document}, page {p.page}</a>
                    <p className="hint">{p.rows.length} {p.rows.length === 1 ? "requirement" : "requirements"}{done ? `, ${done} reviewed` : ""}</p>
                  </div>
                  <div className="actions">
                    <button className="button small" disabled={!p.pending.length} onClick={() => confirmPage(p)}>Confirm {p.pending.length} on this page</button>
                    <button className="button secondary small" disabled={!done} onClick={() => save(clear(p.rows.filter((r) => decisions.has(r.key))), `Cleared ${done} on page ${p.page}`)}>Undo {done || ""} reviewed</button>
                  </div>
                </div>
                <ul className="flagged-list">
                  {p.rows.map((r) => <FlaggedRow key={r.key} row={r} decision={decisions.get(r.key)} onSave={save} />)}
                </ul>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
