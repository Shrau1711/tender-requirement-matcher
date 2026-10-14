import { useMemo, useState } from "react";
import { api } from "../api";
import { matches } from "../lib/tables";
import DataTable from "./DataTable";
import { EmptyState } from "./States";

export default function ToConfirm({ report, run }) {
  const [query, setQuery] = useState("");
  const rows = useMemo(() => report.unsupported.filter((u) => matches(`${u.item} ${u.wanted} ${u.why}`, query)), [report, query]);
  const columns = useMemo(() => [
    { key: "item", label: "Item" },
    { key: "wanted", label: "Requirement" },
    { key: "tender_page", label: "In the tender", render: (u) => (u.tender_file ? <a href={api.tenderUrl(run.id, u.tender_file, u.tender_page)} target="_blank" rel="noreferrer">{u.tender_file}, page {u.tender_page}</a> : `page ${u.tender_page}`) },
    { key: "why", label: "Why it is not scored" },
  ], [run.id]);
  if (report.unsupported.length === 0) return <EmptyState title="Nothing to confirm">Every requirement could be judged from the collected documents.</EmptyState>;
  return (
    <section className="card">
      <div className="card-head"><h2>To confirm with the manufacturer</h2><span className="hint">{rows.length} of {report.unsupported.length}</span></div>
      <p className="hint">These requirements are not scored. Either a catalogue cannot show them, or none of the collected documents covers them.</p>
      <div className="table-tools"><label className="field grow"><span>Search</span><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label></div>
      <DataTable caption="Requirements to confirm with the manufacturer" columns={columns} rows={rows} rowKey={(u) => `${u.item}|${u.wanted}|${u.tender_page}`} pageSize={20} />
    </section>
  );
}
