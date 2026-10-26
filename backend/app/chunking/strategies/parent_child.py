"""Small chunks to search, big chunks to read.

The parents are the default strategy's chunks. A parent longer than CHILD_CHARS is cut into children of whole lines,
which overlap by one line. Search ranks the children, because a short passage that is about one thing matches a
query more sharply; the model is then given the parent (Chunk.for_model), so it still sees the context. Table rows
are already short and stay as they are.
"""
from __future__ import annotations

from app.chunking.base import Chunk, Chunker, MakeChunk
from app.chunking.strategies.table_rows import TableRows
from app.reading.pdf_reader import PageRecord

CHILD_CHARS = 300  # longest child, in characters


# Whole lines grouped into pieces of up to `size` characters. Each piece starts with the last line of the one before.
def children(text: str, size: int = CHILD_CHARS) -> list[str]:
    lines = text.splitlines()
    pieces: list[list[str]] = [[]]
    for line in lines:
        current = pieces[-1]
        if current and len("\n".join([*current, line])) > size:
            pieces.append([current[-1], line] if len(current) > 1 else [line])
        else:
            current.append(line)
    return ["\n".join(p) for p in pieces if p]


class ParentChild:
    name = "parent_child"

    def __init__(self, parents: Chunker | None = None) -> None:
        self.parents = parents or TableRows()

    def chunk(self, pages: list[PageRecord], make: MakeChunk) -> list[Chunk]:
        out: list[Chunk] = []
        for parent in self.parents.chunk(pages, make):
            if len(parent.text) <= CHILD_CHARS:
                out.append(parent)
                continue
            for child in children(parent.text):
                # a child of a section keeps the section's heading, so it can still be found by it
                text = child if not parent.section or child.startswith(parent.section) else f"{parent.section}\n{child}"
                out.append(parent.model_copy(update={"text": text, "parent": parent.text}))
        return out
