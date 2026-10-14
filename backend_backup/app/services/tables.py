from __future__ import annotations

import re

from app.services.pdf_reader import RawTable

MIN_COLS = 3          # fewer columns than this is not a real table
MAX_CELL_CHARS = 200  # a cell longer than this is a whole page mistaken for a table
VALUE = re.compile(r"^[-–—]$|^[\d.,/]+$")  # "-", "125", "37.0.", "102/125"


def clean(cell: str | None) -> str:
    return " ".join((cell or "").split())


def is_real_table(table: RawTable) -> bool:
    cells = [clean(c) for row in table.rows for c in row]
    wide = max(len(row) for row in table.rows) >= MIN_COLS
    return wide and all(len(c) <= MAX_CELL_CHARS for c in cells) and header_size(table.rows) > 0


def is_data_row(row: list[str | None]) -> bool:
    cells = [clean(c) for c in row if clean(c)]
    return bool(cells) and sum(bool(VALUE.match(c)) for c in cells) / len(cells) >= 0.5


def header_size(rows: list[list[str | None]]) -> int:
    """Number of header rows: everything above the first row of values."""
    return next((i for i, row in enumerate(rows) if is_data_row(row)), 0)


def fill_merged(rows: list[list[str | None]]) -> list[list[str]]:
    """Give a merged group header (None cells to its right) to the columns it spans,
    but only where the column has its own heading below. A None under a heading
    is a vertical merge, and stays empty."""
    filled: list[list[str]] = []
    for r, row in enumerate(rows):
        last, out = "", []
        for j, cell in enumerate(row):
            text = clean(cell)
            below = any(clean(rows[k][j]) for k in range(r + 1, len(rows)))
            if text:
                last = text
            elif not (last and below):
                last = ""
            out.append(text or last)
        filled.append(out)
    return filled


def column_headers(header_rows: list[list[str | None]]) -> list[str]:
    filled = fill_merged(header_rows)
    headers = []
    for j in range(len(header_rows[0])):
        parts: list[str] = []
        for row in filled:
            if row[j] and row[j] not in parts:
                parts.append(row[j])
        headers.append(" > ".join(parts))
    return headers


def table_rows(table: RawTable) -> list[str]:
    """One text per data row: the row read against its column headers, then the row
    exactly as printed (the printed line is the evidence a quote must come from)."""
    n = header_size(table.rows)
    headers = column_headers(table.rows[:n])
    texts = []
    for row in table.rows[n:]:
        cells = [clean(c) for c in row]
        if not any(cells):
            continue
        pairs = [f"{h}: {c}" for h, c in zip(headers, cells) if c and c != "-"]
        texts.append("; ".join(pairs) + "\nRow as printed: " + " ".join(c for c in cells if c))
    return texts