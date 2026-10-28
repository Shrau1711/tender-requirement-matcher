"""What every vector store offers, and the names it gives to documents and chunks."""
from __future__ import annotations

from collections import Counter
from typing import Protocol

import numpy as np
from pydantic import BaseModel

from app.chunking.base import Chunk

FIELDS = ("category", "manufacturer", "file", "page")  # what a search can be narrowed to


class StoredDoc(BaseModel):
    """One manufacturer document as the store knows it. If the file's content or the settings change, it is read again."""

    category: str
    manufacturer: str
    file: str
    sha256: str = ""    # fingerprint of the file's content
    settings: str = ""  # how it was read and chunked (see ingest.settings_for)

    @property
    def id(self) -> str:
        return f"{self.category}/{self.manufacturer}/{self.file}"


# Narrows a search: only chunks whose fields equal these values, e.g. {"category": "valves", "manufacturer": "ksb"}.
Where = dict[str, str | int]


class VectorStore(Protocol):
    name: str

    def stored(self, doc: StoredDoc) -> bool:
        """True if this file, with this content and these settings, is already in the store."""
        ...

    def chunks(self, doc: StoredDoc) -> list[Chunk]:
        """The chunks of a stored file, in their original order."""
        ...

    def put(self, doc: StoredDoc, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Store a file's chunks with one vector each, replacing what was stored for that file before."""
        ...

    def candidates(self, where: Where) -> list[str]:
        """The ids of every stored chunk whose fields match `where`. The store filters; it does not score: similarity is
        worked out exactly by the index from the stored vectors (see Index.meanings)."""
        ...

    def vectors(self, ids: list[str]) -> np.ndarray:
        """The stored vectors of these chunks, one row each, in the order asked."""
        ...


# A name for every chunk that stays the same from run to run: its category, maker, file and place in the file.
def chunk_ids(category: str, chunks: list[Chunk]) -> list[str]:
    seen: Counter[tuple[str, str]] = Counter()
    ids = []
    for c in chunks:
        ids.append(f"{category}/{c.manufacturer}/{c.file}#{seen[c.manufacturer, c.file]}")
        seen[c.manufacturer, c.file] += 1
    return ids


def fields(category: str, chunk: Chunk) -> dict[str, str | int]:
    return {"category": category, "manufacturer": chunk.manufacturer, "file": chunk.file, "page": chunk.pdf_page}


def check_where(where: Where) -> None:
    unknown = set(where) - set(FIELDS)
    if unknown:
        raise ValueError(f"Cannot filter on {sorted(unknown)}; the fields are {list(FIELDS)}")
