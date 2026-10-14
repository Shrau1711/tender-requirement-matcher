export const STATUSES = ["fully matched", "partially matched", "missing capability", "unsupported requirement"];

export const STATUS_CLASS = {
  "fully matched": "full",
  "partially matched": "partial",
  "missing capability": "missing",
  "unsupported requirement": "unsupported",
};

export const FLAG_HELP = {
  "units": "The units are missing or cannot be converted, so the numbers could not be compared safely.",
  "unit read the other way": "It matches only if a unit such as PN is read the other way.",
  "unclear tender value": "The tender's value is not a plain number.",
  "reference only": "The document names a standard or reference, not the thing the tender asks for.",
  "equivalent grade": "The tender accepts an equivalent; whether this is one needs a person.",
  "grade not stated": "The document gives the kind of material or type, not the exact grade or number asked for.",
  "only under a condition": "The statement applies only under a condition, such as a size range.",
  "product not named": "The passage does not say which product it is about.",
  "scanned page": "The page is a picture; the text was read by OCR and may contain mistakes.",
};

/** What the person should actually do for each reason, in the same words everywhere it is shown. */
export const FLAG_ACTION = {
  "units": "Find the value on the page and its unit. Convert it, and decide whether it meets the tender's value.",
  "unit read the other way": "Check which unit the page really uses (for example PN or bar). The score assumes one reading; the other would change the result.",
  "unclear tender value": "The tender's value is not a plain number. Read the tender line and decide whether the page meets it.",
  "reference only": "The page names a standard, not the property the tender asks for. Check that the product itself meets what is asked.",
  "equivalent grade": "The tender accepts an equivalent. Decide whether the grade or standard on the page is one.",
  "grade not stated": "The page names the kind of material or type, not the exact grade or number asked for. Look for the exact one.",
  "only under a condition": "The value holds only under the condition quoted (often a size or a range). Check that this condition fits what is being offered.",
  "product not named": "The passage does not say which product it is about. Check that it is the right product.",
  "scanned page": "This page is a picture read by OCR. Compare the quote with the page and look for misread characters.",
};

export function callsSummary(text) {
  const match = /model calls (\d+), from cache (\d+)/.exec(text ?? "");
  return match ? `${match[1]} new · ${match[2]} cached` : text ?? "–";
}

export function percent(value) {
  return value === null || value === undefined ? "not assessed" : `${value.toFixed(1)}%`;
}

export function shortDate(iso) {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function fileSize(bytes) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function countsOf(rows) {
  const counts = Object.fromEntries(STATUSES.map((s) => [s, 0]));
  rows.forEach((row) => { counts[row.status] += 1; });
  return counts;
}

export function flagCounts(rows) {
  const counts = {};
  rows.forEach((row) => row.flags.forEach((f) => { counts[f] = (counts[f] ?? 0) + 1; }));
  return counts;
}
