"""Chunks that follow a document's own structure: numbered clauses, and the boxes of a flowchart.

Numbered clauses ("3. Pumps", "3.2 Casing", "3.2.1 Material") form a tree. Each clause becomes a chunk that starts
with the path of clauses above it ("3. Pumps > 3.2 Casing"), so a line such as "Material: SS 316" can still be found by
the product it belongs to. A clause that runs onto the next page starts a new chunk there, with the same path.

A flowchart page (short texts in drawn boxes joined by lines, and no table) has its meaning in the lines between the
boxes, so each chunk is a box with the boxes joined to it. Text outside the boxes is packed as usual, and table rows are
chunked as in the default.
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
FLOW_MIN_BOXES = 6    # a flowchart has at least this many boxes with text on the page
FLOW_SHORT_WORDS = 6  # a box says at most this many words
FLOW_SHORT_SHARE = 0.7  # and at least this share of a page's boxes are that short
FLOW_LINKED_SHARE = 0.5  # and at least this share of them are joined to another box by a drawn line


# (number, depth) of a numbered clause heading, or None.
def clause_of(text: str) -> tuple[str, int] | None:
    match = CLAUSE.match(" ".join(text.split()))
    if not match:
        return None
    number = match.group(1).rstrip(".)")
    return number, number.count(".") + 1


def in_box(line: Line, box: tuple[float, float, float, float]) -> bool:
    x, y = (line.x0 + line.x1) / 2, (line.y0 + line.y1) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


# The text of each drawn box, in the order of page.boxes ("" for a box whose text was not read). Lines are matched to
# boxes by position, not by text block, because PDF readers often merge a row of boxes into one block.
def box_texts(page: PageRecord, lines: list[Line]) -> list[str]:
    return [" ".join(" ".join(l.text.split()) for l in lines if in_box(l, box)) for box in page.boxes]


# True for a page with no table where several short texts sit in drawn boxes joined by lines.
# Each test alone lets tables through: a datasheet has short labels, and an ordering-code grid has boxes standing apart.
# Only a flowchart draws lines between its boxes.
def is_flowchart(page: PageRecord, lines: list[Line]) -> bool:
    texts = [t for t in box_texts(page, lines) if t]
    if page.tables or len(texts) < FLOW_MIN_BOXES:
        return False
    linked = {i for link in page.links for i in link}
    short = sum(len(t.split()) <= FLOW_SHORT_WORDS for t in texts) / len(texts)
    return short >= FLOW_SHORT_SHARE and len(linked) / len(page.boxes) >= FLOW_LINKED_SHARE


# One chunk per box: the boxes with a line into it, the box, and the boxes it leads to ("Slurry" comes with the
# question above it and the valve below it).
def flow_chunks(texts: list[str], links: list[tuple[int, int]]) -> list[str]:
    out = []
    for i, text in enumerate(texts):
        before = [f"{texts[a]} ->" for a, b in links if b == i and texts[a]]
        after = [f"-> {texts[b]}" for a, b in links if a == i and texts[b]]
        if text:
            out.append("\n".join([*before, text, *after]))
    return out


class Structure:
    name = "structure"

    def chunk(self, pages: list[PageRecord], make: MakeChunk) -> list[Chunk]:
        path: list[tuple[str, int]] = []  # the open clauses, outermost first: (heading, depth)
        out: list[Chunk] = []
        for page in pages:
            tables, lines = table_chunks(page, make)
            if is_flowchart(page, lines):
                section = " > ".join(h for h, _ in path) or None
                loose = [l for l in lines if not any(in_box(l, b) for b in page.boxes)]
                out += tables + [make(page, "text", section, t) for t in pack(block_texts(loose)) + flow_chunks(box_texts(page, lines), page.links)]
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
