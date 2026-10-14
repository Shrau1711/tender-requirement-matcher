import { STATUSES } from "./format";

/** The identity of one row for one manufacturer. The backend builds the same text, so Excel can show the decisions. */
export const reviewKey = (maker, item, row) => JSON.stringify([maker, item, row.attribute, row.wanted, row.tender_page]);

/** Every scored row of a manufacturer as one flat list, each knowing its item, its maker and its key. */
export function rowsOf(maker) {
  return maker.items
    .filter((item) => item.scored)
    .flatMap((item) => item.rows.map((row) => ({ ...row, flags: row.flags ?? [], item: item.item, maker: maker.manufacturer, key: reviewKey(maker.manufacturer, item.item, row) })));
}

export function progressOf(rows, decisions) {
  const flagged = rows.filter((r) => r.review);
  return { flagged: flagged.length, reviewed: flagged.filter((r) => decisions.has(r.key)).length };
}

export const isPending = (row, decisions) => row.review && !decisions.has(row.key);

export function decisionLabel(decision) {
  if (!decision) return null;
  return decision.decision === "changed" ? `Changed to ${decision.status}` : "Confirmed";
}

export const DECISION_STATUSES = STATUSES;

/** Rows the person can see, after the filters in the toolbar. */
export function filterRows(rows, { status = null, flag = null, onlyCheck = false, hideReviewed = false, query = "" }, decisions) {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  return rows.filter((row) => {
    if (status && row.status !== status) return false;
    if (flag && !row.flags.includes(flag)) return false;
    if (onlyCheck && !row.review) return false;
    if (hideReviewed && decisions.has(row.key)) return false;
    const text = `${row.item} ${row.attribute} ${row.wanted} ${row.reason} ${row.quote ?? ""} ${row.document ?? ""}`.toLowerCase();
    return terms.every((t) => text.includes(t));
  });
}

/** The pages a person has to open: every page a flagged row rests on, with what to look for there. */
export function pagesToCheck(rows, decisions) {
  const pages = new Map();
  rows.filter((r) => r.review && r.document).forEach((row) => {
    const key = `${row.document}#${row.page}`;
    const entry = pages.get(key) ?? { document: row.document, page: row.page, flags: new Set(), rows: [] };
    row.flags.forEach((f) => entry.flags.add(f));
    entry.rows.push(row);
    pages.set(key, entry);
  });
  return [...pages.values()]
    .map((e) => ({ ...e, flags: [...e.flags], pending: e.rows.filter((r) => !decisions.has(r.key)) }))
    .sort((a, b) => a.document.localeCompare(b.document) || a.page - b.page);
}
