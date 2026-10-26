from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.reading.layout import build_sections
from app.reading.ocr import is_table_row
from app.reading.pdf_reader import Line, PageRecord, RawTable, ReadDocument
from app.reading.tables import is_real_table, table_rows

MAX_CHARS = 1000      # size of a fallback chunk, in characters
MIN_COVERAGE = 0.8    # use sections only if they cover this share of the page's lines
MIN_LETTERS = 4       # a heading has at least this many letters (a page number or "12345" is not one)
MAX_HEADINGS = 8      # how many bold lines of a page are kept as its headings
HEADING_LENGTH = (6, 80)  # shortest and longest bold line that reads as a heading
ROW_GAP = 100         # a value that starts with ':' belongs to the label this close to its left
CAPTION_GAP = 30      # a line this close above a table is its caption
CAPTION_LENGTH = 80   # a longer line is a paragraph, not a caption


class Chunk(BaseModel):
    manufacturer: str
    file: str
    pdf_page: int
    kind: str  # "section", "table" or "text"
    section: str | None
    text: str
    ocr: bool = False  # read from a picture of the page, so it may contain misreadings
    page_headings: list[str] = []  # the page's bold lines, top to bottom: they say which product the page is about
    document_headings: list[str] = []  # the same for the document's first page (its cover), for pages that do not name the product


# One string per text block, so a label stays with its value.
def block_texts(lines: list[Line]) -> list[str]:
    """One string per text block, in block order. A block keeps its label and value together."""
    blocks: dict[int, list[str]] = {}
    for line in lines:
        blocks.setdefault(line.block, []).append(" ".join(line.text.split()))
    return ["\n".join(texts) for texts in blocks.values()]


# Cuts a block that is too big for one chunk at line breaks, never in the middle of a line.
def split_oversized(text: str, max_chars: int) -> list[str]:
    """Cut a block that is too big for one chunk into pieces of whole lines."""
    parts: list[str] = []
    current = ""
    for line in text.splitlines():
        if current and len(current) + len(line) + 1 > max_chars:
            parts.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    return [*parts, current] if current else parts


# Joins whole blocks into chunks of up to 1000 characters, never cutting inside a block.
def pack(pieces: list[str], max_chars: int = MAX_CHARS) -> list[str]:
    """Join whole blocks into chunks of up to max_chars, never cutting inside a block."""
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        for part in split_oversized(piece, max_chars) if len(piece) > max_chars else [piece]:
            if current and len(current) + len(part) + 1 > max_chars:
                chunks.append(current)
                current = ""
            current = f"{current}\n{part}" if current else part
    return [*chunks, current] if current else chunks


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


# The page's bold lines, top to bottom, which say what product the page is about.
def page_headings(lines: list[Line]) -> list[str]:
    """The page's bold lines, top to bottom, without repeats (field labels ending in a colon are left out)."""
    low, high = HEADING_LENGTH
    texts = (" ".join(l.text.split()) for l in sorted(lines, key=lambda l: (l.y0, l.x0)) if l.bold)
    return list(dict.fromkeys(t for t in texts if low <= len(t) <= high and not t.endswith(":") and sum(c.isalpha() for c in t) >= MIN_LETTERS))[:MAX_HEADINGS]


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


# Cuts one page into chunks: one per table row, then one per section if sections cover 80% of the text, otherwise
# packed blocks of up to 1000 characters.
def chunk_page(page: PageRecord, manufacturer: str, file: str, document_headings: list[str] | None = None) -> list[Chunk]:
    headings = page_headings(page.lines)

    def make(kind: str, section: str | None, text: str) -> Chunk:
        return Chunk(manufacturer=manufacturer, file=file, pdf_page=page.pdf_page,
                     kind=kind, section=section, text=text, ocr=page.ocr, page_headings=headings,
                     document_headings=document_headings or [])

    tables = [t for t in page.tables if is_real_table(t)]
    chunks = [make("table", None, f"{caption}\n{text}" if caption else text)
              for t in tables for caption in [caption_for(t, page.lines)] for text in table_rows(t)]
    chunks += [make("table", None, row) for row in ocr_rows(page.lines)] if page.ocr else []
    lines = [l for l in page.lines if not any(inside(l, t) for t in tables) and not (page.ocr and is_table_row(l.text))]

    sections = build_sections(lines)
    covered = sum(len(s.lines) for s in sections)
    if lines and covered / len(lines) >= MIN_COVERAGE:
        return chunks + [make("section", s.heading, "\n".join(s.lines)) for s in sections]
    return chunks + [make("text", None, t) for t in pack(block_texts(join_rows(lines)))]


# Chunks every page of a document. The folder name is the manufacturer and the first page's headings are the cover
# headings.
def chunk_document(doc: ReadDocument) -> list[Chunk]:
    path = Path(doc.path)
    manufacturer = path.parent.name  # the folder name says whose document it is
    cover = page_headings(doc.pages[0].lines) if doc.pages else []
    return [c for page in doc.pages for c in chunk_page(page, manufacturer, path.name, cover)]