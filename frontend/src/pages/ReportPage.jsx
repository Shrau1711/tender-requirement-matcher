import { useEffect, useState } from "react";
import { api } from "../api";
import CompareMakers from "../components/report/CompareMakers";
import Icon from "../components/common/Icon";
import MethodTab from "../components/report/MethodTab";
import Overview from "../components/report/Overview";
import PagesToCheck from "../components/review/PagesToCheck";
import { PrintContext } from "../components/common/PrintContext";
import Requirements from "../components/report/Requirements";
import TenderLayout from "../components/report/TenderLayout";
import { TabPanel, Tabs } from "../components/common/Tabs";
import ToConfirm from "../components/review/ToConfirm";
import { useReviews } from "../hooks/useReviews";
import { shortDate } from "../lib/format";
import { go } from "../hooks/useRoute";
import { links } from "../lib/route";
import { progressOf, rowsOf } from "../lib/review";

export default function ReportPage({ run, report, tab, makerName, onDelete }) {
  const { decisions, save } = useReviews(run.id);
  const [printing, setPrinting] = useState(false);
  const first = report.makers[0]?.manufacturer ?? null;
  const maker = makerName ?? first;
  const { flagged, reviewed } = progressOf(report.makers.flatMap(rowsOf), decisions);

  useEffect(() => {
    if (!printing) return undefined;
    const done = () => setPrinting(false);
    window.addEventListener("afterprint", done);
    const timer = setTimeout(() => window.print(), 50);  // let the whole report render first
    return () => { window.removeEventListener("afterprint", done); clearTimeout(timer); };
  }, [printing]);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "requirements", label: "Requirements" },
    { id: "compare", label: "Compare" },
    { id: "pages", label: "Pages to check", count: `${reviewed}/${flagged}` },
    { id: "confirm", label: "To confirm", count: report.unsupported.length },
    { id: "layout", label: "Tender layout" },
    { id: "method", label: "Method" },
  ];
  const selected = tabs.some((t) => t.id === tab) ? tab : "overview";
  const open = (id, name = maker) => go(links.run(run.id, id, name));
  const shared = { report, run, makerName: maker, onMaker: (name) => go(links.run(run.id, selected, name)), decisions, save };

  return (
    <PrintContext.Provider value={printing}>
      <div className="page-head">
        <div>
          <h1 id="report-title" tabIndex={-1}>{run.tender}</h1>
          <p>{report.tender === run.tender ? "" : `${report.tender} · `}Matched against {run.category || "…"} on {shortDate(run.finished_at ?? run.created_at)}</p>
        </div>
        <div className="actions">
          <a className="button secondary" href={api.downloadUrl(run.id, "xlsx")} download><Icon name="download" />Excel</a>
          <button className="button secondary" onClick={() => setPrinting(true)}><Icon name="print" />PDF</button>
          <a className="button secondary" href={api.downloadUrl(run.id, "md")} download>Markdown</a>
          <a className="button secondary" href={api.downloadUrl(run.id, "json")} download>JSON</a>
          <button className="button danger" onClick={() => window.confirm("Delete this run, its report and the decisions saved with it?") && onDelete()}>Delete</button>
        </div>
      </div>
      <Tabs tabs={tabs} selected={selected} onSelect={(id) => open(id)} name="Report sections" />
      <TabPanel id="overview" label="Overview" selected={selected} printing={printing}><Overview report={report} decisions={decisions} onOpen={(name) => open("requirements", name)} /></TabPanel>
      <TabPanel id="requirements" label="Requirements" selected={selected} printing={printing}><Requirements {...shared} /></TabPanel>
      <TabPanel id="compare" label="Compare manufacturers" selected={selected} printing={printing}><CompareMakers report={report} /></TabPanel>
      <TabPanel id="pages" label="Pages to check" selected={selected} printing={printing}><PagesToCheck {...shared} /></TabPanel>
      <TabPanel id="confirm" label="To confirm with the manufacturer" selected={selected} printing={printing}><ToConfirm report={report} run={run} /></TabPanel>
      <TabPanel id="layout" label="Tender layout" selected={selected} printing={false}><TenderLayout run={run} /></TabPanel>
      <TabPanel id="method" label="Method" selected={selected} printing={printing}><MethodTab report={report} /></TabPanel>
    </PrintContext.Provider>
  );
}
