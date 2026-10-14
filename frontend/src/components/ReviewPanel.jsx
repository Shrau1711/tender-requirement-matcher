import { useState } from "react";
import { api } from "../api";
import { FLAG_ACTION } from "../lib/format";
import { DECISION_STATUSES } from "../lib/review";
import Icon from "./Icon";
import StatusBadge from "./StatusBadge";

function DecisionForm({ row, existing, onSave, onNext }) {
  const [choice, setChoice] = useState(existing?.decision ?? "confirmed");
  const [status, setStatus] = useState(existing?.status ?? row.status);
  const [note, setNote] = useState(existing?.note ?? "");
  const item = () => ({ key: row.key, decision: choice, status: choice === "changed" ? status : null, note: note.trim() });
  return (
    <form className="decision" onSubmit={(e) => { e.preventDefault(); onSave([item()], "Decision saved"); }}>
      <fieldset>
        <legend>Your decision</legend>
        <label className="radio"><input type="radio" name={`decision-${row.key}`} checked={choice === "confirmed"} onChange={() => setChoice("confirmed")} />The result is right</label>
        <label className="radio"><input type="radio" name={`decision-${row.key}`} checked={choice === "changed"} onChange={() => setChoice("changed")} />The status should be different</label>
      </fieldset>
      {choice === "changed" && (
        <label className="field"><span>Correct status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>{DECISION_STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
        </label>
      )}
      <label className="field"><span>Note <span className="hint">(optional)</span></span><textarea value={note} onChange={(e) => setNote(e.target.value)} /></label>
      <div className="actions">
        <button className="button small">Save decision</button>
        <button type="button" className="button secondary small" onClick={async () => { if (await onSave([item()], "Decision saved")) onNext(); }}>Save and go to next to check</button>
        {existing && <button type="button" className="button secondary small" onClick={() => onSave([{ key: row.key, decision: null }], "Decision cleared")}>Clear</button>}
      </div>
      <p className="panel-note">Decisions are saved with this run and included in the Excel export. They do not change the computed score.</p>
    </form>
  );
}

/** One requirement in detail: why it got its status, the quote, the source page itself, and where a person records their decision. */
export default function ReviewPanel({ row, run, decision, onSave, onNext, onClose }) {
  const source = row.document ? api.documentUrl(run.category, row.maker, row.document, row.page) : null;
  return (
    <aside className="card review-panel" aria-label="Requirement details">
      <header>
        <div>
          <p className="label-caps">{row.item}</p>
          <h2>{row.attribute.replaceAll("_", " ")}: {row.wanted}</h2>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close details"><Icon name="x" /></button>
      </header>
      <StatusBadge status={row.status} flags={row.flags} review={row.review} /> <span className="hint">score {row.score}</span>
      <p className="reason">{row.reason}</p>
      {row.flags.length > 0 && (
        <div className="notice" aria-label="What to check">
          <strong>What to check</strong>
          {row.flags.map((f) => <span key={f} className="check-line">{FLAG_ACTION[f]}</span>)}
        </div>
      )}
      {source ? (
        <>
          <blockquote>
            <p>{row.quote}</p>
            <footer>{row.document}, page {row.page}{row.product ? `, about ${row.product}` : ""} · <a href={source} target="_blank" rel="noreferrer">Open in a new tab<span className="visually-hidden"> (opens on page {row.page})</span></a></footer>
          </blockquote>
          <iframe key={source} className="pdf-frame" title={`${row.document}, page ${row.page}`} src={source} />
        </>
      ) : <p className="hint">No document passage was used for this requirement.</p>}
      <p className="hint">Asked for in the tender{row.tender_file ? `, ${row.tender_file}` : ""}, page {row.tender_page}{row.tender_file && <> · <a href={api.tenderUrl(run.id, row.tender_file, row.tender_page)} target="_blank" rel="noreferrer">Open tender page {row.tender_page}</a></>}</p>
      <DecisionForm key={row.key} row={row} existing={decision} onSave={onSave} onNext={onNext} />
    </aside>
  );
}
