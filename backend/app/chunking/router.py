"""Choosing a chunking strategy for a document from what it looks like.

The CHUNKER setting decides: a strategy's name uses that strategy for every document; "auto" lets choose() pick one
per document. The default is table_rows, the original strategy, so the saved model answers keep matching.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.chunking.base import Chunker, is_heading
from app.chunking.strategies import strategy
from app.chunking.strategies.structure import clause_of, is_flowchart
from app.config import text_setting
from app.reading.pdf_reader import ReadDocument
from app.reading.tables import is_real_table

CHUNKER = text_setting("CHUNKER", "table_rows")
MIN_CLAUSES = 8          # a document needs at least this many numbered clause headings to be chunked by its clauses
CLAUSE_SHARE = 0.05      # and they must be at least this share of its lines
FLOW_SHARE = 0.3         # share of pages that look like flowcharts
TABLE_SHARE = 0.2        # share of pages with a table
PROSE_WORDS = 10         # average words per line of running text


@dataclass
class Looks:
    """What a document looks like, in the few numbers the choice is made from."""

    lines: int
    clauses: int
    flow_pages: float
    table_pages: float
    headings: int
    words_per_line: float


def looks(doc: ReadDocument) -> Looks:
    pages = [p for p in doc.pages if p.lines]
    lines = [l for p in pages for l in p.lines]
    n = max(1, len(pages))
    return Looks(
        lines=len(lines),
        clauses=sum(clause_of(l.text) is not None for l in lines),
        flow_pages=sum(is_flowchart(p, p.lines) for p in pages) / n,
        table_pages=sum(any(is_real_table(t) for t in p.tables) or p.ocr for p in pages) / n,
        headings=sum(is_heading(l) for l in lines),
        words_per_line=sum(len(l.text.split()) for l in lines) / max(1, len(lines)),
    )


def choose(doc: ReadDocument) -> tuple[str, str]:
    """(strategy name, the reason in words). The first rule that fits wins."""
    seen = looks(doc)
    if seen.clauses >= MIN_CLAUSES and seen.clauses / max(1, seen.lines) >= CLAUSE_SHARE:
        return "structure", f"{seen.clauses} numbered clauses"
    if seen.flow_pages >= FLOW_SHARE:
        return "structure", f"{seen.flow_pages:.0%} of pages look like flowcharts"
    if seen.table_pages >= TABLE_SHARE:
        return "table_rows", f"{seen.table_pages:.0%} of pages have tables"
    if not seen.headings:
        return "recursive", "no headings or tables to follow"
    if seen.words_per_line >= PROSE_WORDS:
        return "parent_child", f"running text, {seen.words_per_line:.0f} words a line"
    return "sections", f"{seen.headings} headings and few tables"


def chunker_for(doc: ReadDocument, setting: str = CHUNKER) -> Chunker:
    return strategy(choose(doc)[0] if setting == "auto" else setting)
