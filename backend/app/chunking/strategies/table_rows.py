"""The original strategy and the default: one chunk per table row, then one per section, else packed text blocks.

Built for catalogues, where most facts sit in tables and in label/value pairs.
"""
from __future__ import annotations

from app.chunking.base import Chunk, MakeChunk, PageChunker, block_texts, pack
from app.reading.layout import build_sections
from app.reading.ocr import is_table_row
from app.reading.pdf_reader import Line, PageRecord, RawTable
from app.reading.tables import is_real_table, table_rows

MIN_COVERAGE = 0.8    # use sections only if they cover this share of the page's lines
ROW_GAP = 100         # a value that starts with ':' belongs to the label this close to its left
CAPTION_GAP = 30      # a line this close above a table is its caption
CAPTION_LENGTH = 80   # a longer line is a paragraph, not a caption


# The vertical middle of a line.
def middle(line: Line) -> float:
    return (line.y0 + line.y1) / 2


# Left to right, joins a value that starts with ':' to the label before it.
def join_row(row: list[Line]) -> list[Line]:
    """Left to right, a value that starts with ':' is joined to the label before it. Plain neighbours are other columns."""
    merged: list[Line] = []
    for line in sorted(row, key=lambda l: l.x0):
        if merged and line.text.startswith(":") and 0 <= line.x0 - merged[-1].x1 <= ROW_GAP:
            merged[-1] = merged[-1].model_copy(update={"text": f"{merged[-1].text} {line.text}", "x1": line.x1})
        else:
            merged.append(line)
    return merged


# Puts 'Face to Face' and ': API 609' back together when the file stored them as separate blocks.
def join_rows(lines: list[Line]) -> list[Line]:
    """Put 'Face to Face' and ': API 609 ...' back together when the file stores them as separate blocks."""
    if not any(line.text.startswith(":") for line in lines):
        return lines  # nothing to join, so the file's own reading order is kept
    rows: list[list[Line]] = []
    for line in sorted(lines, key=middle):
        if rows and abs(middle(line) - middle(rows[-1][0])) <= (line.y1 - line.y0) / 2:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [line for row in rows for line in join_row(row)]


# The short line just above a table, such as 'Pressure Rating'.
def caption_for(table: RawTable, lines: list[Line]) -> str | None:
    """The short line just above a table, such as 'Pressure Rating', which says what its rows are."""
    x0, y0, x1, _ = table.bbox
    above = [l for l in lines if 0 <= y0 - l.y1 <= CAPTION_GAP and l.x0 <= x1 and l.x1 >= x0 and len(l.text) <= CAPTION_LENGTH]
    return max(above, key=lambda l: l.y1).text if above else None


# True when a line sits inside a table's box, so it is not chunked twice.
def inside(line: Line, table: RawTable) -> bool:
    x0, y0, x1, y1 = table.bbox
    return x0 <= (line.x0 + line.x1) / 2 <= x1 and y0 <= (line.y0 + line.y1) / 2 <= y1


# Table rows of a scanned page, each with the heading above it as its caption.
def ocr_rows(lines: list[Line]) -> list[str]:
    """The table rows of a page read from a picture, each with the heading above it as its caption."""
    rows, caption = [], None
    for line in lines:
        if is_table_row(line.text):
            rows.append(f"{caption}\n{line.text}" if caption else line.text)
        elif line.bold:
            caption = line.text
    return rows


# One chunk per table row (with its caption), for typed tables and for rows read from a picture.
def table_chunks(page: PageRecord, make: MakeChunk) -> tuple[list[Chunk], list[Line]]:
    """The page's table rows as chunks, and the lines that are left over once the tables are taken out."""
    tables = [t for t in page.tables if is_real_table(t)]
    chunks = [make(page, "table", None, f"{caption}\n{text}" if caption else text)
              for t in tables for caption in [caption_for(t, page.lines)] for text in table_rows(t)]
    chunks += [make(page, "table", None, row) for row in ocr_rows(page.lines)] if page.ocr else []
    rest = [l for l in page.lines if not any(inside(l, t) for t in tables) and not (page.ocr and is_table_row(l.text))]
    return chunks, rest


class TableRows(PageChunker):
    name = "table_rows"

    # Cuts one page: one chunk per table row, then one per section if sections cover 80% of the text, otherwise
    # packed blocks of up to 1000 characters.
    def page(self, page: PageRecord, make: MakeChunk) -> list[Chunk]:
        chunks, lines = table_chunks(page, make)
        sections = build_sections(lines)
        covered = sum(len(s.lines) for s in sections)
        if lines and covered / len(lines) >= MIN_COVERAGE:
            return chunks + [make(page, "section", s.heading, "\n".join(s.lines)) for s in sections]
        return chunks + [make(page, "text", None, t) for t in pack(block_texts(join_rows(lines)))]
