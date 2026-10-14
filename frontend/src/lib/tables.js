/** Sorting, paging and searching for the tables. Plain functions, so they are easy to test. */
export function sortRows(rows, sort, columns) {
  const column = sort && columns.find((c) => c.key === sort.key);
  if (!column) return rows;
  const value = column.sortValue ?? ((row) => row[column.key]);
  const direction = sort.direction === "descending" ? -1 : 1;
  return rows
    .map((row, index) => ({ row, index, v: value(row) }))
    .sort((a, b) => {
      const order = typeof a.v === "number" && typeof b.v === "number" ? a.v - b.v : String(a.v ?? "").localeCompare(String(b.v ?? ""), undefined, { numeric: true });
      return order * direction || a.index - b.index;
    })
    .map((entry) => entry.row);
}

export function pageOf(rows, page, size) {
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const current = Math.min(Math.max(page, 0), pages - 1);
  return { current, pages, rows: rows.slice(current * size, (current + 1) * size), from: rows.length ? current * size + 1 : 0, to: Math.min(rows.length, (current + 1) * size) };
}

export function matches(text, query) {
  const haystack = text.toLowerCase();
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((t) => haystack.includes(t));
}
