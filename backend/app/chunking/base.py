from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from app.reading.pdf_reader import Line, PageRecord, ReadDocument

MAX_CHARS = 1000      # size of a packed chunk, in characters
MIN_LETTERS = 4       # a heading has at least this many letters (a page number or "12345" is not one)
MAX_HEADINGS = 8      # how many bold lines of a page are kept as its headings
HEADING_LENGTH = (6, 80)  # shortest and longest bold line that reads as a heading


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
    parent: str | None = None  # parent-child chunking: the larger passage this one was cut from, which the model reads instead

    def for_model(self) -> str:
        """The text the model reads: the parent passage when there is one, so a small chunk that was easy to find still comes with its context."""
        return self.parent or self.text


# Makes a chunk of one page: (page, kind, section, text, parent) -> Chunk. Who wrote the document and its headings are filled in.
MakeChunk = Callable[..., Chunk]


class Chunker(Protocol):
    """Cuts the pages of one document into chunks. Every strategy in app.chunking.strategies is one."""

    name: str

    def chunk(self, pages: list[PageRecord], make: MakeChunk) -> list[Chunk]: ...


class PageChunker:
    """A strategy that looks at one page at a time: it only needs to say how to cut a page."""

    name = ""

    def chunk(self, pages: list[PageRecord], make: MakeChunk) -> list[Chunk]:
        return [c for page in pages for c in self.page(page, make)]

    def page(self, page: PageRecord, make: MakeChunk) -> list[Chunk]:
        raise NotImplementedError


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


# True for bold text that reads as a heading: not too short or long, has letters, and is not a field label ending in ':'.
def is_heading(line: Line) -> bool:
    low, high = HEADING_LENGTH
    text = " ".join(line.text.split())
    return line.bold and low <= len(text) <= high and not text.endswith(":") and sum(c.isalpha() for c in text) >= MIN_LETTERS


# The page's bold lines, top to bottom, which say what product the page is about.
def page_headings(lines: list[Line]) -> list[str]:
    """The page's heading lines, top to bottom, without repeats."""
    texts = (" ".join(l.text.split()) for l in sorted(lines, key=lambda l: (l.y0, l.x0)) if is_heading(l))
    return list(dict.fromkeys(texts))[:MAX_HEADINGS]


# The function a strategy calls to make a chunk, so no strategy repeats who wrote the document or what its headings are.
def maker(manufacturer: str, file: str, document_headings: list[str] | None = None) -> MakeChunk:
    headings: dict[int, list[str]] = {}  # each page's headings, worked out once

    def make(page: PageRecord, kind: str, section: str | None, text: str, parent: str | None = None) -> Chunk:
        if page.pdf_page not in headings:
            headings[page.pdf_page] = page_headings(page.lines)
        return Chunk(manufacturer=manufacturer, file=file, pdf_page=page.pdf_page, kind=kind, section=section, text=text,
                     ocr=page.ocr, page_headings=headings[page.pdf_page], document_headings=document_headings or [], parent=parent)

    return make


# Chunks every page of a document with one strategy. The folder name is the manufacturer and the first page's
# headings are the cover headings.
def chunk_document(doc: ReadDocument, chunker: Chunker) -> list[Chunk]:
    path = Path(doc.path)
    cover = page_headings(doc.pages[0].lines) if doc.pages else []
    return chunker.chunk(doc.pages, maker(path.parent.name, path.name, cover))
