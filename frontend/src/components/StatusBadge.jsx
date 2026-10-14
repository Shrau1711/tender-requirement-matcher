import { FLAG_HELP, STATUS_CLASS } from "../lib/format";

export default function StatusBadge({ status, flags = [], review = false }) {
  return (
    <span className="badge-group">
      <span className={`badge badge-${STATUS_CLASS[status]}`}>{status}</span>
      {flags.length > 0
        ? flags.map((f) => <span key={f} className="badge badge-review" title={FLAG_HELP[f]}>check: {f}</span>)
        : review && <span className="badge badge-review">check</span>}
    </span>
  );
}
