"""Chunks that follow a document's own structure: numbered clauses, and the boxes of a flowchart.

Numbered clauses ("3. Pumps", "3.2 Casing", "3.2.1 Material") form a tree. Each clause becomes a chunk that starts
with the path of clauses above it ("3. Pumps > 3.2 Casing"), so a line such as "Material: SS 316" can still be found by
the product it belongs to. A clause that runs onto the next page starts a new chunk there, with the same path.

A flowchart-like page (many short texts, each inside a drawn box, and no table) has its meaning in which boxes sit next to
each other, so each chunk is a box with its neighbours in reading order. Table rows are chunked as in the default.
"""
from __future__ import annotations

import re

from app.chunking.base import (
    MAX_CHARS,
    Chunk,
    MakeChunk,
    block_texts,
    pack,
    split_oversized,
)
from app.chunking.strategies.table_rows import table_chunks
from app.reading.pdf_reader import Line, PageRecord

# "3.", "3)", "3.2", "3.2.1." followed by a title that starts with a letter. A bare "16 bar" is not a clause.
CLAUSE = re.compile(r"^((?:\d{1,2}\.)+\d{0,2}|\d{1,2}\))\s+([A-Za-z].{0,118})$")
FLOW_MIN_BOXES = 6    # a flowchart has at least this many boxed texts on the page
FLOW_SHORT_WORDS = 6  # a box says at most this many words
FLOW_SHORT_SHARE = 0.7  # and at least this share of a page's boxes are that short
NEIGHBOURS = 3        # boxes per flowchart chunk


# (number, depth) of a numbered clause heading, or None.
def clause_of(text: str) -> tuple[str, int] | None:
    match = CLAUSE.match(" ".join(text.split()))
    if not match:
        return None
    number = match.group(1).rstrip(".)")
    return number, number.count(".") + 1


# The first line of every text block, in block order: one per box.
def boxes(lines: list[Line]) -> list[tuple[Line, str]]:
    first: dict[int, Line] = {}
    for line in lines:
        first.setdefault(line.block, line)
    return list(zip(first.values(), block_texts(lines), strict=True))


# True for a page with no table where several texts sit in drawn boxes and most texts are short.
# Short texts alone are not enough: a datasheet page of labels looks the same until you see the boxes.
def is_flowchart(page: PageRecord, lines: list[Line]) -> bool:
    found = boxes(lines)
    if page.tables or page.n_boxes < FLOW_MIN_BOXES or not found:
        return False
    return sum(len(text.split()) <= FLOW_SHORT_WORDS for _, text in found) / len(found) >= FLOW_SHORT_SHARE


# Each box with the boxes after it, top to bottom and left to right.
def flow_windows(lines: list[Line]) -> list[str]:
    ordered = [text.replace("\n", " ") for _, text in sorted(boxes(lines), key=lambda b: (round(b[0].y0), b[0].x0))]
    if len(ordered) <= NEIGHBOURS:
        return ["\n".join(ordered)]
    return ["\n".join(ordered[i:i + NEIGHBOURS]) for i in range(len(ordered) - NEIGHBOURS + 1)]


class Structure:
    name = "structure"

    def chunk(self, pages: list[PageRecord], make: MakeChunk) -> list[Chunk]:
        path: list[tuple[str, int]] = []  # the open clauses, outermost first: (heading, depth)
        out: list[Chunk] = []
        for page in pages:
            tables, lines = table_chunks(page, make)
            if is_flowchart(page, lines):
                section = " > ".join(h for h, _ in path) or None
                out += tables + [make(page, "text", section, text) for text in flow_windows(lines)]
                continue
            out += [t.model_copy(update={"section": " > ".join(h for h, _ in path) or None}) for t in tables]
            out += self.clauses(page, lines, path, make)
        return out

    # The page's clause chunks. `path` is carried from page to page, so a clause continued on this page keeps its place.
    def clauses(self, page: PageRecord, lines: list[Line], path: list[tuple[str, int]], make: MakeChunk) -> list[Chunk]:
        out: list[Chunk] = []
        loose: list[Line] = []   # lines before the first clause of a document that has none open
        body: list[str] = []

        def flush() -> None:
            if not body:
                return
            section = " > ".join(h for h, _ in path)
            # a chunk that starts with its own heading needs only the path above it; a continued one needs the whole path
            prefix = " > ".join(h for h, _ in path[:-1]) if body[0] == path[-1][0] else section
            text = "\n".join([prefix, *body] if prefix else body)
            pieces = split_oversized(text, MAX_CHARS) if len(text) > MAX_CHARS else [text]
            out.extend(make(page, "section", section, p if i == 0 else f"{section}\n{p}") for i, p in enumerate(pieces))
            body.clear()

        for line in lines:
            text = " ".join(line.text.split())
            found = clause_of(text)
            if found:
                flush()
                _, depth = found
                while path and path[-1][1] >= depth:
                    path.pop()
                path.append((text, depth))
                body.append(text)
            elif path:
                body.append(text)
            else:
                loose.append(line)
        flush()
        return [make(page, "text", None, t) for t in pack(block_texts(loose))] + out
