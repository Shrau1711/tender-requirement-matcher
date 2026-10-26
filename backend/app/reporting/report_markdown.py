from __future__ import annotations

from app.reporting.report import STATUSES, ItemResult, MakerResult, Report, Row

QUOTE_LENGTH = 160


def cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "/")


def percent(value: float | None) -> str:
    return "not assessed" if value is None else f"{value:.1f}%"


def evidence_cell(row: Row) -> str:
    if row.document is None:
        return ""
    quote = " ".join((row.quote or "").split())
    quote = quote if len(quote) <= QUOTE_LENGTH else quote[: QUOTE_LENGTH - 1] + "…"
    return f"{row.document} p{row.page}: “{quote}”"


def ranking(report: Report) -> list[str]:
    lines = ["| Rank | Manufacturer | Compatibility | Coverage | Fully | Partially | Missing | Unsupported | Need review |", "|---|---|---|---|---|---|---|---|---|"]
    for m in report.makers:
        c = m.counts
        lines.append(
            f"| {m.rank or '-'} | {m.manufacturer} | {percent(m.compatibility)} | {percent(m.coverage)} | {c['fully matched']} | "
            f"{c['partially matched']} | {c['missing capability']} | {c['unsupported requirement']} | {m.review_needed} |"
        )
    return lines


def item_section(r: ItemResult) -> list[str]:
    qty = f" x{r.quantity}" if r.quantity is not None else ""
    head = f"#### {cell(r.item)}{qty}: {percent(r.compatibility) if r.scored else 'not scored'}"
    lines = [head, ""]
    if r.product:
        lines.append(f"Judged against: {cell(r.product)}")
    if r.note:
        lines.append(f"Note: {r.note}")
    lines += ["", "| Requirement | Status | Score | Evidence | Why |", "|---|---|---|---|---|"]
    for row in r.rows:
        flag = f" (check: {', '.join(row.flags)})" if row.flags else " (check)" if row.review else ""
        lines.append(f"| {cell(row.attribute)}: {cell(row.wanted)} | {row.status}{flag} | {row.score} | {cell(evidence_cell(row))} | {cell(row.reason)} |")
    return lines + [""]


def maker_section(m: MakerResult) -> list[str]:
    lines = [f"### {m.manufacturer}: {percent(m.compatibility)}", ""]
    for r in m.items:
        lines += item_section(r)
    return lines


def to_markdown(report: Report) -> str:
    lines = [f"# Tender {report.tender}: manufacturer compatibility", "", *ranking(report), "", "## How the compatibility is calculated", "", report.method, ""]
    lines += ["## What the statuses mean", ""] + [f"- **{s}**: {report.definitions[s]}" for s in STATUSES] + [""]
    if report.notes:
        lines += ["## Notes on this tender", ""] + [f"- {cell(n)}" for n in report.notes] + [""]
    if report.unsupported:
        lines += ["## To confirm with the manufacturer", "", "| Item | Requirement | Tender page | Why it is not scored |", "|---|---|---|---|"]
        lines += [f"| {cell(u.item)} | {cell(u.wanted)} | {cell(u.tender_file)} p{u.tender_page} | {cell(u.why)} |" for u in report.unsupported] + [""]
    lines += ["## Requirement by requirement", ""]
    for m in report.makers:
        lines += maker_section(m)
    return "\n".join(lines)
