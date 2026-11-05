import { api } from "../../api";
import { useAsync } from "../../hooks/useAsync";

const FROM = { title: "named in the item's title", "type value": "from the type the tender asks for" };

/** The tender as it was read: items, the printed rows (a row shared by several items once), the requirements each row splits into, and the standards cited. Built on the server from the saved reading; nothing is asked of the model. */
export default function TenderLayout({ run }) {
  const { data: layout, error, loading } = useAsync(() => api.layout(run.id), [run.id]);
  if (loading) return <p className="hint" role="status">Reading the tender's saved layout…</p>;
  if (error) return <div className="problem" role="alert">{error}</div>;
  return (
    <div className="stack">
      <p className="hint">
        {`${layout.items.length} items, ${layout.requirements} requirements, ${layout.shared_rows} printed rows shared by several items. `}
        Product families come from each category's category.json. This view is for reading only; it does not change any score.
      </p>
      {layout.items.map((item) => (
        <section className="card stack" key={item.title} aria-label={item.title}>
          <div>
            <h2>{item.title}</h2>
            <p className="hint">
              {item.category ? `Category: ${item.category}. ` : "Category not recognised. "}
              {item.family ? `Family: ${item.family} (${FROM[item.family_from]}).` : "Family: not named."}
            </p>
          </div>
          <ul className="layout-rows">
            {item.rows.map((row) => (
              <li key={`${row.file}:${row.page}:${row.name}:${row.value}`}>
                <strong>{row.name}</strong>: {row.value}{" "}
                <a href={api.tenderUrl(run.id, row.file, row.page)} target="_blank" rel="noreferrer">page {row.page}</a>
                {row.shared_with.length > 0 && <span className="hint"> · also for {row.shared_with.join(", ")}</span>}
                <ul>
                  {row.requirements.map((r) => <li key={r}>{r}</li>)}
                  {row.standards.length > 0 && <li>cites {row.standards.join(", ")}</li>}
                </ul>
              </li>
            ))}
          </ul>
          {item.not_named.length > 0 && (
            <details className="fold">
              <summary>{`${item.not_named.length} attributes of this kind of product the reading does not name`}</summary>
              <p className="hint">category.json lists these for {item.family ?? item.category}. The tender may still ask for them under another name.</p>
              <p>{item.not_named.join(", ")}</p>
            </details>
          )}
        </section>
      ))}
      {layout.standards.length > 0 && (
        <section className="card">
          <h2>Standards cited</h2>
          <ul className="layout-rows">
            {layout.standards.map((s) => (
              <li key={s.name}>
                <strong>{s.name}</strong>
                {s.also_written.length > 0 && <span> · also written {s.also_written.join(", ")}</span>}
                {s.named_together.length > 0 && <span className="hint"> · named together with {s.named_together.join(", ")} (not necessarily equivalent)</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
