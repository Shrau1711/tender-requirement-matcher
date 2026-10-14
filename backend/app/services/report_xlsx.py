from __future__ import annotations

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.db.reviews import Review
from app.services.report import Report
from app.services.review_key import row_key

HEAD = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="B94830")
DECISION_TEXT = {"confirmed": "Confirmed", "changed": "Changed"}


def percent(value: float | None) -> str | float:
    return "not assessed" if value is None else round(value, 1)


def write_header(sheet: Worksheet, titles: list[str]) -> None:
    sheet.append(titles)
    for cell in sheet[1]:
        cell.font, cell.fill, cell.alignment = HEAD, HEAD_FILL, Alignment(vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"


def widen(sheet: Worksheet, widths: list[int]) -> None:
    for i, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(i)].width = width


def sheet_name(name: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "", name).strip()[:28] or "Manufacturer"
    unique, n = base, 2
    while unique.lower() in used:
        unique, n = f"{base} {n}", n + 1
    used.add(unique.lower())
    return unique


def summary_sheet(wb: Workbook, report: Report) -> None:
    sheet = wb.active
    sheet.title = "Summary"
    sheet.append([report.tender])
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([])
    write_header(sheet, ["Rank", "Manufacturer", "Compatibility %", "Coverage %", "Fully matched", "Partially matched", "Missing capability", "Unsupported requirement", "Rows to check"])
    sheet.freeze_panes = None
    for m in report.makers:
        sheet.append([m.rank or "", m.manufacturer, percent(m.compatibility), percent(m.coverage), *(m.counts[s] for s in m.counts), m.review_needed])
    sheet.append([])
    sheet.append(["How the compatibility is calculated"])
    sheet.append([report.method])
    sheet.cell(sheet.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
    sheet.merge_cells(start_row=sheet.max_row, start_column=1, end_row=sheet.max_row, end_column=9)
    sheet.row_dimensions[sheet.max_row].height = 150
    widen(sheet, [8, 26, 16, 12, 14, 18, 18, 22, 14])


def maker_sheet(wb: Workbook, maker, decisions: dict[str, Review], used: set[str]) -> None:
    sheet = wb.create_sheet(sheet_name(maker.manufacturer, used))
    write_header(sheet, ["Item", "Requirement", "Wanted", "Status", "Score", "Check because", "Why", "Product", "Page", "Quote", "Document", "Tender page", "Decision", "Note"])
    for item in maker.items:
        for r in item.rows:
            d = decisions.get(row_key(maker.manufacturer, item.item, r.attribute, r.wanted, r.tender_page))
            decision = "" if d is None else DECISION_TEXT[d.decision] + (f": {d.status}" if d.status else "")
            sheet.append([item.item, r.attribute.replace("_", " "), r.wanted, r.status, r.score, ", ".join(r.flags), r.reason, r.product or "", r.page or "", r.quote or "", r.document or "", r.tender_page, decision, d.note if d else ""])
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    widen(sheet, [26, 22, 22, 18, 8, 24, 50, 28, 7, 60, 26, 11, 20, 40])


def confirm_sheet(wb: Workbook, report: Report) -> None:
    sheet = wb.create_sheet("To confirm")
    write_header(sheet, ["Item", "Requirement", "Tender file", "Tender page", "Why it is not scored"])
    for u in report.unsupported:
        sheet.append([u.item, u.wanted, u.tender_file, u.tender_page, u.why])
    widen(sheet, [30, 50, 26, 12, 70])


def build_workbook(report: Report, decisions: dict[str, Review]) -> bytes:
    """The report as an Excel file: a summary, one sheet of requirements per manufacturer, and the list to confirm. Plain code, no model calls."""
    wb = Workbook()
    summary_sheet(wb, report)
    used = {"summary", "to confirm"}
    for maker in report.makers:
        maker_sheet(wb, maker, decisions, used)
    confirm_sheet(wb, report)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
