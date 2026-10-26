import { STATUS_CLASS } from "../../lib/format";

const COUNTED = ["fully matched", "partially matched", "missing capability"];

/** The requirements a score is made of, as one bar split by status. */
export default function StatusStrip({ counts }) {
  const total = COUNTED.reduce((sum, s) => sum + counts[s], 0);
  const label = COUNTED.map((s) => `${counts[s]} ${s}`).join(", ");
  return (
    <div>
      <div className="strip" role="img" aria-label={label}>
        {COUNTED.map((s) => total > 0 && counts[s] > 0 && <span key={s} className={`strip-part fill-${STATUS_CLASS[s]}`} style={{ flexGrow: counts[s] }} />)}
      </div>
      <span className="strip-legend">{counts["fully matched"]} full, {counts["partially matched"]} partial, {counts["missing capability"]} missing</span>
    </div>
  );
}
