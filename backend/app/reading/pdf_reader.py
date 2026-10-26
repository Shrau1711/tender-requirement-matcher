from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
from pydantic import BaseModel

from app.llm.parallel import run_parallel
from app.reading.boxes import box_links, text_boxes
from app.reading.ocr import ImageReader, render_page

MIN_TEXT_CHARS = 40
MIN_DRAWINGS = 20     # a page with no text but this many vector shapes is text drawn as shapes, not a blank page
LINE_HEIGHT = 12      # pretend geometry for lines that were read from a picture
BOLD_FLAG = 16  # PyMuPDF span flag bit for bold


class Line(BaseModel):
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool
    block: int  # index of the text block this line came from


class RawTable(BaseModel):
    bbox: tuple[float, float, float, float]
    rows: list[list[str | None]]  # None marks a merged (continued) cell


class PageRecord(BaseModel):
    pdf_page: int
    printed_label: str | None = None
    text: str
    n_chars: int
    n_images: int
    needs_ocr: bool   # the page has pictures or drawn text but no text of its own
    ocr: bool = False  # its text was read from the picture by the model, so it may contain misreadings
    lines: list[Line]
    tables: list[RawTable] = []
    boxes: list[tuple[float, float, float, float]] = []  # the boxes of a flowchart, in reading order (see app.reading.boxes)
    links: list[tuple[int, int]] = []  # (from, to) positions in boxes, for each line drawn between two of them


class ReadDocument(BaseModel):
    path: str
    sha256: str
    n_pages: int
    pages: list[PageRecord]


# Fingerprint of a file's content.
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# Every text line of a page with its position, font size and bold flag.
def extract_lines(page: pymupdf.Page) -> list[Line]:
    lines: list[Line] = []
    for block_no, block in enumerate(page.get_text("dict", sort=True)["blocks"]):
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            first = line["spans"][0]  # style of a mixed-style line = its first span
            x0, y0, x1, y1 = line["bbox"]
            lines.append(
                Line(
                    text=text, x0=x0, y0=y0, x1=x1, y1=y1,
                    size=first["size"], bold=bool(first["flags"] & BOLD_FLAG), block=block_no,
                )
            )
    return lines


# Builds lines for text read from a picture, which has no layout. A blank line starts a new block and '# ' marks a
# heading.
def lines_from_text(text: str) -> list[Line]:
    """Lines for text that has no layout of its own (read from a picture). A blank line starts a new block,
    and a line that starts with '# ' is a heading (the reader was asked to mark them), so it counts as bold."""
    lines: list[Line] = []
    block = 0
    for row, raw in enumerate(text.splitlines()):
        if not raw.strip():
            block += 1
            continue
        heading = raw.strip().startswith("# ")
        text = raw.strip().removeprefix("# ").strip()
        lines.append(Line(text=text, x0=0, y0=row * LINE_HEIGHT, x1=len(text), y1=(row + 1) * LINE_HEIGHT,
                          size=10, bold=heading, block=block))
    return lines


# True for a page with almost no text but a picture or drawn text. It leans toward reading, because skipping a page
# loses it silently.
def needs_ocr(page: pymupdf.Page, text: str, n_images: int) -> bool:
    """A page with almost no text of its own but something to read: a picture, or text drawn as vector shapes.

    Wrongly reading a page costs one model call. Wrongly skipping one loses the page without a word, so we lean to reading.
    """
    return len(text) < MIN_TEXT_CHARS and (n_images > 0 or len(page.get_drawings()) >= MIN_DRAWINGS)


# The page with the text the reader found in its picture.
def with_text(record: PageRecord, text: str) -> PageRecord:
    """The page, with the text the reader found in its picture."""
    return record.model_copy(update={"text": text, "n_chars": len(text), "lines": lines_from_text(text)})


# Finds the tables on a page with PyMuPDF.
def extract_tables(page: pymupdf.Page) -> list[RawTable]:
    found = page.find_tables().tables
    return [RawTable(bbox=tuple(t.bbox), rows=t.extract()) for t in found]


# The page number printed on the page ('iv', '12'), or None if the PDF's labels are broken.
def printed_label(page) -> str | None:
    """The page number printed on the page ("iv", "12"). Some PDFs carry broken label tables, which only cost the label."""
    try:
        return page.get_label() or None
    except (IndexError, ValueError, RuntimeError):
        return None


# Reads a PDF into pages of text, lines and tables. Picture-only pages are read together by the model.
def read_pdf(path: str | Path, read_image: ImageReader | None = None) -> ReadDocument:
    """Every page as text, lines and tables. Pages that are only a picture or drawn text are read by read_image, if one is given.

    The pages that need reading are read all at once, since each is a slow call to the model.
    """
    path = Path(path)
    records: list[PageRecord] = []
    pictures: dict[int, bytes] = {}  # page number -> picture of each page to be read by read_image

    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError(f"{path.name} is password protected")

        for i, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True).strip()
            n_images = len(page.get_images(full=True))
            unreadable = needs_ocr(page, text, n_images)
            ocr = unreadable and read_image is not None
            boxes = [] if ocr else text_boxes(page)
            if ocr:
                pictures[i] = render_page(page)
            records.append(
                PageRecord(
                    pdf_page=i,
                    printed_label=printed_label(page),
                    text=text,
                    n_chars=len(text),
                    n_images=n_images,
                    needs_ocr=unreadable,
                    ocr=ocr,
                    lines=[] if ocr else extract_lines(page),
                    tables=[] if ocr else extract_tables(page),
                    boxes=boxes,
                    links=box_links(page, boxes) if boxes else [],
                )
            )
        n_pages = doc.page_count

    read = dict(zip(pictures, run_parallel(read_image, pictures.values()), strict=True)) if pictures else {}
    pages = [with_text(r, read[r.pdf_page].strip()) if r.ocr else r for r in records]
    return ReadDocument(path=str(path), sha256=sha256_file(path), n_pages=n_pages, pages=pages)
