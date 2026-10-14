import { useEffect, useMemo, useState } from "react";
import { pageOf, sortRows } from "../lib/tables";
import { usePrinting } from "./PrintContext";

/**
 * A table with sortable columns, a sticky header and paging.
 * columns: [{ key, label, render?, sortValue?, numeric?, sortable? }]. onSelect makes whole rows clickable (keyboard users use the control inside the row).
 */
export default function DataTable({ caption, columns, rows, rowKey, defaultSort = null, pageSize = 25, selectedKey = null, onSelect, className = "" }) {
  const [sort, setSort] = useState(defaultSort);
  const [page, setPage] = useState(0);
  const printing = usePrinting();
  const sorted = useMemo(() => sortRows(rows, sort, columns), [rows, sort, columns]);
  const shown = printing ? { rows: sorted, current: 0, pages: 1, from: sorted.length ? 1 : 0, to: sorted.length } : pageOf(sorted, page, pageSize);
  useEffect(() => { setPage(0); }, [rows.length, sort]);

  function toggle(column) {
    setSort(sort?.key === column.key && sort.direction === "ascending" ? { key: column.key, direction: "descending" } : { key: column.key, direction: "ascending" });
  }

  return (
    <div className={className}>
      <div className="table-wrap">
        <table>
          <caption className="visually-hidden">{caption}</caption>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={c.numeric ? "num" : ""} aria-sort={sort?.key === c.key ? sort.direction : undefined}>
                  {c.sortable === false ? c.label : <button className="sort-button" onClick={() => toggle(c)}>{c.label}</button>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.rows.map((row) => {
              const key = rowKey(row);
              return (
                <tr key={key} className={`${onSelect ? "selectable" : ""} ${key === selectedKey ? "is-selected" : ""}`} onClick={onSelect ? () => onSelect(row) : undefined}>
                  {columns.map((c) => <td key={c.key} className={c.numeric ? "num" : ""}>{c.render ? c.render(row) : row[c.key]}</td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {shown.pages > 1 && (
        <nav className="pager" aria-label={`${caption}: pages`}>
          <span>{shown.from}–{shown.to} of {sorted.length}</span>
          <span className="actions">
            <button className="button secondary small" disabled={shown.current === 0} onClick={() => setPage(shown.current - 1)}>Previous</button>
            <span aria-current="page">Page {shown.current + 1} of {shown.pages}</span>
            <button className="button secondary small" disabled={shown.current >= shown.pages - 1} onClick={() => setPage(shown.current + 1)}>Next</button>
          </span>
        </nav>
      )}
    </div>
  );
}
