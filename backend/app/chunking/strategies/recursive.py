"""Fixed-size chunks that overlap, cut at the largest natural break that fits: paragraph, then line, then sentence, then word.

Knows nothing about layout, so it works on any text, including text read from a picture. It is the baseline the
layout-aware strategies have to beat.
"""
from __future__ import annotations

from itertools import pairwise

from app.chunking.base import Chunk, MakeChunk, PageChunker
from app.reading.pdf_reader import PageRecord

SIZE = 800           # longest chunk before the overlap is added, in characters
OVERLAP = 150        # characters of the previous chunk repeated at the start of the next, so a fact cut in two is whole in one of them
SEPARATORS = ("\n\n", "\n", ". ", " ")  # tried in this order: the biggest break that keeps pieces small enough wins


# Cuts text into pieces of at most `size` characters, trying the biggest separator first.
def split(text: str, size: int = SIZE, separators: tuple[str, ...] = SEPARATORS) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    if not separators:
        return [text[i:i + size] for i in range(0, len(text), size)]  # no break left: cut anywhere
    sep, rest = separators[0], separators[1:]
    pieces: list[str] = []
    current = ""
    for part in text.split(sep):
        for small in split(part, size, rest) if len(part) > size else [part]:
            if current and len(current) + len(sep) + len(small) > size:
                pieces.append(current)
                current = ""
            current = f"{current}{sep}{small}" if current else small
    return [p for p in [*pieces, current] if p.strip()]


# The end of the previous piece, started at a word, put in front of each piece.
def overlap(pieces: list[str], chars: int = OVERLAP) -> list[str]:
    out = pieces[:1]
    for before, piece in pairwise(pieces):
        tail = before[-chars:]
        tail = tail[tail.find(" ") + 1:] if " " in tail else tail
        out.append(f"{tail} {piece}" if tail else piece)
    return out


class Recursive(PageChunker):
    name = "recursive"

    def page(self, page: PageRecord, make: MakeChunk) -> list[Chunk]:
        return [make(page, "text", None, piece) for piece in overlap(split(page.text))]
