import { FLAG_HELP, STATUSES } from "../../lib/format";
import StatusBadge from "../common/StatusBadge";

export default function MethodTab({ report }) {
  return (
    <div className="stack">
      <section className="card">
        <h2>How the compatibility is calculated</h2>
        <p style={{ marginTop: "0.5rem", maxWidth: "75ch" }}>{report.method}</p>
      </section>
      <section className="card">
        <h2>What each status means</h2>
        <dl className="defs" style={{ marginTop: "0.6rem" }}>
          {STATUSES.map((s) => <div key={s}><dt><StatusBadge status={s} /></dt><dd>{report.definitions[s]}</dd></div>)}
        </dl>
      </section>
      <section className="card">
        <h2>Why a row is marked "check"</h2>
        <dl className="defs" style={{ marginTop: "0.6rem" }}>
          {Object.entries(FLAG_HELP).map(([flag, text]) => <div key={flag}><dt><span className="badge badge-review">check: {flag}</span></dt><dd>{text}</dd></div>)}
        </dl>
      </section>
    </div>
  );
}
