import { links } from "../../lib/route";
import Icon from "../common/Icon";

export function Topbar({ crumbs, theme, onToggleTheme }) {
  return (
    <header className="topbar">
      <a className="brand" href={links.newRun}><span className="brand-mark" aria-hidden="true">TM</span>Tender matcher</a>
      <nav className="crumbs" aria-label="Breadcrumb">
        <ol>{crumbs.map((c, i) => <li key={c} aria-current={i === crumbs.length - 1 ? "page" : undefined}>{c}</li>)}</ol>
      </nav>
      <span className="spacer" />
      <button className="icon-button" onClick={onToggleTheme} aria-label={theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme"}>
        <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
      </button>
    </header>
  );
}

export function Sidebar({ page }) {
  const active = (name) => (page === name || (name === "runs" && (page === "run" || page === "compare")) ? "page" : undefined);
  return (
    <nav className="sidebar" aria-label="Main">
      <a className="nav-link" href={links.newRun} aria-current={active("new")}><Icon name="plus" />New run</a>
      <a className="nav-link" href={links.runs} aria-current={active("runs")}><Icon name="list" />Runs</a>
      <a className="nav-link" href={links.documents} aria-current={active("documents")}><Icon name="upload" />Add documents</a>
      <p className="side-note">Scores come from the manufacturers' own documents. Every answer links to its page.</p>
    </nav>
  );
}
