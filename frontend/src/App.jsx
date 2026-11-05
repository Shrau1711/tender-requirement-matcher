import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { NotifyProvider, useNotify } from "./components/shell/Notifier";
import { Sidebar, Topbar } from "./components/shell/Shell";
import { go, useRoute } from "./hooks/useRoute";
import { useRun } from "./hooks/useRun";
import { useTheme } from "./hooks/useTheme";
import ComparePage from "./pages/ComparePage";
import DocumentsPage from "./pages/DocumentsPage";
import ReportPage from "./pages/ReportPage";
import RunStatus from "./pages/RunStatus";
import RunsPage from "./pages/RunsPage";
import UploadPage from "./pages/UploadPage";
import { links } from "./lib/route";

function RunPage({ route, onChange }) {
  const { run, report, error } = useRun(route.id, onChange);
  const notify = useNotify();
  if (report && run) {
    const remove = async () => {
      try { await api.remove(route.id); onChange(); go(links.runs); } catch (e) { notify(`Could not delete: ${e.message}`); }
    };
    return <ReportPage run={run} report={report} tab={route.tab} makerName={route.maker} onDelete={remove} />;
  }
  return <RunStatus run={run} error={error} />;
}

export default function App() {
  const route = useRoute();
  const [theme, toggleTheme] = useTheme();
  const [runs, setRuns] = useState([]);
  const main = useRef();
  const refresh = useCallback(() => api.runs().then(setRuns).catch(() => {}), []);
  useEffect(() => { refresh(); }, [refresh, route.page]);
  useEffect(() => { main.current?.focus(); window.scrollTo(0, 0); }, [route.page, route.id]);  // a new page starts at the top, with focus in it

  const name = (id) => runs.find((r) => r.id === id)?.tender ?? "Run";
  const crumbs = {
    new: ["New run"], runs: ["Runs"], run: ["Runs", name(route.id)], compare: ["Runs", "Compare"], documents: ["Documents"],
  }[route.page];

  return (
    <NotifyProvider>
      <a className="skip-link" href="#main">Skip to the content</a>
      <div className="app">
        <Topbar crumbs={crumbs} theme={theme} onToggleTheme={toggleTheme} />
        <Sidebar page={route.page} />
        <main id="main" ref={main} tabIndex={-1}>
          {route.page === "new" && <UploadPage onStarted={(run) => { refresh(); go(links.run(run.id)); }} />}
          {route.page === "runs" && <RunsPage runs={runs} refresh={refresh} />}
          {route.page === "run" && <RunPage key={route.id} route={route} onChange={refresh} />}
          {route.page === "compare" && <ComparePage a={route.a} b={route.b} runs={runs} />}
          {route.page === "documents" && <DocumentsPage />}
        </main>
      </div>
    </NotifyProvider>
  );
}
