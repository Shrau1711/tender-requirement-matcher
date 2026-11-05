"""What every retriever offers: the passages of a category that best answer a query, for one manufacturer or all."""
from __future__ import annotations

from typing import Literal, Protocol

import numpy as np
from pydantic import BaseModel

from app.chunking.base import Chunk

Mode = Literal["keyword", "meaning", "hybrid"]


class Hit(BaseModel):
    score: float      # fused rank score, only good for ordering
    keyword: float    # raw BM25 score, 0 means no query word appears
    meaning: float    # raw cosine similarity
    chunk: Chunk


class Retriever(Protocol):
    name: str
    chunks: list[Chunk]           # every passage it searches, in order
    vectors: np.ndarray | None    # their vectors, in the same order (routing compares a title with them)

    def search(self, query: str, manufacturer: str | None = None, top_k: int = 5, mode: Mode | None = None) -> list[Hit]:
        """The best passages for one query. A retriever that has one way of searching may ignore mode."""
        ...

    def search_many(self, queries: list[str], manufacturer: str | None = None, top_k: int = 5, mode: Mode | None = None) -> list[Hit]:
        """The best passages for several phrasings of one need."""
        ...
