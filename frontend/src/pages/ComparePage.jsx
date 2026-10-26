import { useMemo } from "react";
import { api } from "../api";
import DataTable from "../components/common/DataTable";
import { ErrorState } from "../components/common/States";
import { useAsync } from "../hooks/useAsync";
import { percent } from "../lib/format";

const change = (a, b) => (a == null || b == null ? "–" : `${b - a >= 0 ? "+" : ""}${(b - a).toFixed(1)}`);

/** Two runs of the same kind side by side, for example the same tender before and after a fix. */
export default function ComparePage({ a, b, runs }) {
  const { data, error } = useAsync(() => Promise.all([api.report(a), api.report(b)]), [a, b]);
  const names = (id) => runs.find((r) => r.id === id)?.tender ?? id;
  const rows = useMemo(() => {
    if (!data) return [];
    const [first, second] = data.map((r) => new Map(r.makers.map((m) => [m.manufacturer, m])));
    return [...new Set([...first.keys(), ...second.keys()])].map((name) => ({ name, a: first.get(name)?.compatibility ?? null, b: second.get(name)?.compatibility ?? null }));
  }, [data]);
  const columns = useMemo(() => [
    { key: "name", label: "Manufacturer" },
    { key: "a", label: names(a), numeric: true, render: (r) => percent(r.a) },
    { key: "b", label: names(b), numeric: true, render: (r) => percent(r.b) },
    { key: "change", label: "Change", numeric: true, sortValue: (r) => (r.a == null || r.b == null ? 0 : r.b - r.a), render: (r) => change(r.a, r.b) },
  ], [a, b, runs]); // eslint-disable-line react-hooks/exhaustive-deps
  if (error) return <ErrorState title="Could not compare these runs">{error}</ErrorState>;
  return (
    <div className="stack">
      <div className="page-head"><div><h1 id="compare-title" tabIndex={-1}>Compare runs</h1><p>Compatibility of each manufacturer in the two runs. Change is in percentage points.</p></div></div>
      {data && data[0].tender !== data[1].tender && <p className="notice">These runs are for different tenders ({data[0].tender} and {data[1].tender}), so the numbers are not directly comparable.</p>}
      <section className="card">{data ? <DataTable caption="Compatibility in two runs" columns={columns} rows={rows} rowKey={(r) => r.name} pageSize={50} /> : <p className="muted" role="status">Loading both reports…</p>}</section>
    </div>
  );
}
