import { countsOf, percent } from "../../lib/format";
import { progressOf, rowsOf } from "../../lib/review";
import Ranking from "./Ranking";

function Kpi({ label, value, sub }) {
  return (
    <div className="kpi">
      <p className="label-caps">{label}</p>
      <p className="kpi-value">{value}</p>
      {sub && <p className="kpi-sub">{sub}</p>}
    </div>
  );
}

export default function Overview({ report, decisions, onOpen }) {
  const best = report.makers.find((m) => m.rank === 1);
  const all = report.makers.flatMap(rowsOf);
  const { flagged, reviewed } = progressOf(all, decisions);
  const judged = best ? countsOf(rowsOf(best)) : null;
  return (
    <div className="stack">
      <div className="kpis">
        <Kpi label="Best match" value={best ? best.manufacturer : "None"} sub={best ? `${percent(best.compatibility)} compatibility` : "No manufacturer could be assessed"} />
        <Kpi label="Manufacturers" value={report.makers.length} sub={`${report.makers.filter((m) => m.rank).length} ranked`} />
        <Kpi label="To confirm with the maker" value={report.unsupported.length} sub="requirements not scored" />
        <Kpi label="Rows reviewed" value={`${reviewed} of ${flagged}`} sub={judged ? `${judged["fully matched"]} fully matched for ${best.manufacturer}` : "rows flagged for a person"} />
      </div>
      <section className="card" aria-labelledby="ranking-title">
        <div className="card-head"><h2 id="ranking-title">Ranking</h2><span className="hint">Open a manufacturer to see its requirements</span></div>
        <Ranking makers={report.makers} onOpen={onOpen} />
      </section>
      {report.notes.length > 0 && (
        <details className="card fold">
          <summary>Notes on how this tender was read ({report.notes.length})</summary>
          <ul className="notes">{report.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </details>
      )}
    </div>
  );
}
