"""Layout-based chunks: each table whole, and each heading with the lines under it.

Where the default cuts a table into rows, this keeps a table together (packed into pieces of up to 1000 characters,
each repeating the caption), so a question that needs two rows, or the header and a row, finds them in one chunk.
"""
from __future__ import annotations

from app.chunking.base import (
    MAX_CHARS,
    Chunk,
    MakeChunk,
    PageChunker,
    is_heading,
    pack,
    split_oversized,
)
from app.chunking.strategies.table_rows import caption_for, inside
from app.reading.pdf_reader import Line, PageRecord, RawTable
from app.reading.tables import is_real_table, table_rows


# A table as chunks: its rows packed together, each piece starting with the table's caption.
def whole_table(table: RawTable, lines: list[Line]) -> list[str]:
    caption = caption_for(table, lines)
    pieces = pack(table_rows(table), MAX_CHARS - len(caption or "") - 1)
    return [f"{caption}\n{p}" if caption else p for p in pieces]


# Groups lines under the heading above them. Lines before the first heading form a group with no heading.
def under_headings(lines: list[Line]) -> list[tuple[str | None, list[str]]]:
    groups: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in lines:
        text = " ".join(line.text.split())
        if is_heading(line):
            groups.append((text, [text]))
        else:
            groups[-1][1].append(text)
    return [(heading, texts) for heading, texts in groups if texts]


class Sections(PageChunker):
    name = "sections"

    def page(self, page: PageRecord, make: MakeChunk) -> list[Chunk]:
        tables = [t for t in page.tables if is_real_table(t)]
        chunks = [make(page, "table", None, text) for t in tables for text in whole_table(t, page.lines)]
        rest = [l for l in page.lines if not any(inside(l, t) for t in tables)]
        for heading, texts in under_headings(rest):
            body = "\n".join(texts)
            pieces = split_oversized(body, MAX_CHARS) if len(body) > MAX_CHARS else [body]
            # a long section is cut, and every piece after the first starts with the heading again
            chunks += [make(page, "section" if heading else "text", heading, p if i == 0 or not heading else f"{heading}\n{p}")
                       for i, p in enumerate(pieces)]
        return chunks
