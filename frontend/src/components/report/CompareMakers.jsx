import { useMemo, useState } from "react";
import { percent } from "../../lib/format";
import { rowsOf } from "../../lib/review";
import DataTable from "../common/DataTable";
import StatusBadge from "../common/StatusBadge";

const idOf = (r) => JSON.stringify([r.item, r.attribute, r.wanted, r.tender_page]);

/** Every requirement as a row and every manufacturer as a column, so differences are easy to see. */
export default function CompareMakers({ report }) {
  const [differ, setDiffer] = useState(false);
  const [query, setQuery] = useState("");
  const makers = report.makers;
  const table = useMemo(() => {
    const byMaker = makers.map((m) => new Map(rowsOf(m).map((r) => [idOf(r), r])));
    const ids = [...new Set(byMaker.flatMap((m) => [...m.keys()]))];
    return ids.map((id) => {
      const cells = byMaker.map((m) => m.get(id) ?? null);
      const any = cells.find(Boolean);
      return { id, item: any.item, requirement: `${any.attribute.replaceAll("_", " ")}: ${any.wanted}`, cells, differs: new Set(cells.map((c) => c?.score ?? -1)).size > 1 };
    });
  }, [makers]);
  const rows = table.filter((r) => (!differ || r.differs) && `${r.item} ${r.requirement}`.toLowerCase().includes(query.toLowerCase()));
  const columns = useMemo(() => [
    { key: "requirement", label: "Requirement", render: (r) => <><strong>{r.requirement}</strong><br /><span className="cell-sub">{r.item}</span></> },
    ...makers.map((m, i) => ({
      key: `m${i}`, label: `${m.manufacturer} (${percent(m.compatibility)})`, sortValue: (r) => r.cells[i]?.score ?? -1,
      render: (r) => (r.cells[i] ? <span className="compare-cell"><StatusBadge status={r.cells[i].status} /><span className="cell-sub">score {r.cells[i].score}</span></span> : <span className="muted">not compared</span>),
    })),
  ], [makers]);
  return (
    <section className="card">
      <div className="card-head"><h2>Manufacturers side by side</h2><span className="hint">{rows.length} of {table.length} requirements</span></div>
      <div className="table-tools">
        <label className="field grow"><span>Search</span><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={differ} onChange={(e) => setDiffer(e.target.checked)} />Only where manufacturers differ</label>
      </div>
      <DataTable className="compare-wrap" caption="Requirements compared across manufacturers" columns={columns} rows={rows} rowKey={(r) => r.id} pageSize={30} />
    </section>
  );
}
