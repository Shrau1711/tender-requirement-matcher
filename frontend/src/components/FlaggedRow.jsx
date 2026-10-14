import { FLAG_ACTION } from "../lib/format";
import { decisionLabel } from "../lib/review";

const SHORT = 220;
const short = (text) => (text.length > SHORT ? `${text.slice(0, SHORT - 1)}…` : text);

/** What to check for one flagged row: what the tender asks, what the document says, why it is flagged, and what to do about it. */
export default function FlaggedRow({ row, decision, onSave }) {
  const done = decision ? decisionLabel(decision) : null;
  return (
    <li className="flagged-row">
      <div className="flagged-body">
        <p><strong>{row.attribute.replaceAll("_", " ")}</strong> <span className="muted">({row.item})</span></p>
        <dl className="compare-lines">
          <div><dt>Tender asks</dt><dd>{row.wanted}</dd></div>
          <div><dt>Document says</dt><dd>{row.quote ? `“${short(row.quote)}”` : "–"}</dd></div>
          <div><dt>Result</dt><dd>{row.status}, score {row.score}. {row.reason}</dd></div>
          <div><dt>What to check</dt><dd>{row.flags.length ? row.flags.map((f) => <span key={f} className="check-line">{FLAG_ACTION[f]}</span>) : "A person should look at this row."}</dd></div>
        </dl>
      </div>
      <div className="flagged-actions">
        {done && <span className={`badge ${decision.decision === "changed" ? "badge-changed" : "badge-done"}`}>{done}</span>}
        {done
          ? <button className="button secondary small" onClick={() => onSave([{ key: row.key, decision: null }], "Decision cleared")}>Undo</button>
          : <button className="button small" onClick={() => onSave([{ key: row.key, decision: "confirmed" }], "Confirmed", { label: "Undo", run: () => onSave([{ key: row.key, decision: null }], "Decision cleared") })}>Confirm</button>}
      </div>
    </li>
  );
}
