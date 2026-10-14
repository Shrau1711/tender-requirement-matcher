from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
from pydantic import BaseModel

from app.services.ocr import ImageReader, render_page

MIN_TEXT_CHARS = 40
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
    needs_ocr: bool   # the page has pictures but no text of its own
    ocr: bool = False  # its text was read from the picture by the model, so it may contain misreadings
    lines: list[Line]
    tables: list[RawTable] = []


class ReadDocument(BaseModel):
    path: str
    sha256: str
    n_pages: int
    pages: list[PageRecord]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


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


def extract_tables(page: pymupdf.Page) -> list[RawTable]:
    found = page.find_tables().tables
    return [RawTable(bbox=tuple(t.bbox), rows=t.extract()) for t in found]


def read_pdf(path: str | Path, read_image: ImageReader | None = None) -> ReadDocument:
    """Every page as text, lines and tables. Pages that are only a picture are read by read_image, if one is given."""
    path = Path(path)
    pages: list[PageRecord] = []

    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError(f"{path.name} is password protected")

        for i, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True).strip()
            n_images = len(page.get_images(full=True))
            needs_ocr = len(text) < MIN_TEXT_CHARS and n_images > 0
            if needs_ocr and read_image:
                text = read_image(render_page(page)).strip()
            ocr = needs_ocr and read_image is not None
            pages.append(
                PageRecord(
                    pdf_page=i,
                    printed_label=page.get_label() or None,
                    text=text,
                    n_chars=len(text),
                    n_images=n_images,
                    needs_ocr=needs_ocr,
                    ocr=ocr,
                    lines=lines_from_text(text) if ocr else extract_lines(page),
                    tables=[] if ocr else extract_tables(page),
                )
            )
        n_pages = doc.page_count

    return ReadDocument(path=str(path), sha256=sha256_file(path), n_pages=n_pages, pages=pages)