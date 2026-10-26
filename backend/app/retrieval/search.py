from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from typing import Literal

import numpy as np
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from app.chunking.base import Chunk
from app.embedding.embed_cache import embed_cached
from app.retrieval.fusion import rrf
from app.vectorstore.base import StoredDoc, VectorStore, chunk_ids
from app.vectorstore.memory import MemoryStore

TABLE_ROWS_PER_PAGE = 2  # one big table must not fill every result slot

# Letters and numbers are split apart so "DN125", "DN 125" and "dn-125" all
# become the same two tokens. A number stays whole, so 13095 never matches 3095.
TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)?")

Embedder = Callable[[list[str]], np.ndarray]
Mode = Literal["keyword", "meaning", "hybrid"]


class Hit(BaseModel):
    score: float      # fused rank score, only good for ordering
    keyword: float    # raw BM25 score, 0 means no query word appears
    meaning: float    # raw cosine similarity
    chunk: Chunk


# Splits text into letters and numbers so 'DN125', 'DN 125' and 'dn-125' match, and 13095 never matches 3095.
def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class Index:
    """Keyword search (BM25) over the chunks, and meaning search through a vector store, merged by rank.

    With no store given, the chunks are embedded into a new in-memory store, as in the first version. A given store must
    already hold these chunks under `category` (see app.vectorstore.ingest)."""

    def __init__(self, chunks: list[Chunk], embed: Embedder = embed_cached, store: VectorStore | None = None, category: str = "") -> None:
        self.chunks = chunks
        self.embed = embed
        self.bm25 = BM25Okapi([tokenize(c.text) for c in chunks])
        self.category = category
        self.position = {chunk_id: i for i, chunk_id in enumerate(chunk_ids(category, chunks))}
        if store is None:
            store = MemoryStore()
            store.put(StoredDoc(category=category, manufacturer="", file=""), chunks, embed([c.text for c in chunks]))
        self.store = store

    # Cosine similarity of every allowed chunk to each query, by chunk position. The store may leave some out.
    def meanings(self, queries: list[str], allowed: list[int], manufacturer: str | None) -> list[dict[int, float]]:
        where = {"category": self.category} | ({"manufacturer": manufacturer} if manufacturer else {})
        found = self.store.nearest(self.embed(queries), len(allowed), where)
        return [{self.position[chunk_id]: score for chunk_id, score in scores.items()} for scores in found]

    # Finds the best passages for one query.
    def search(
        self, query: str, manufacturer: str | None = None, top_k: int = 5, mode: Mode = "hybrid"
    ) -> list[Hit]:
        return self.search_many([query], manufacturer, top_k, mode)

    # Finds the best passages for several phrasings. The keyword and meaning rankings are merged by rank (RRF).
    def search_many(
        self, queries: list[str], manufacturer: str | None = None, top_k: int = 5, mode: Mode = "hybrid"
    ) -> list[Hit]:
        """Best chunks for several phrasings of one need: every phrasing's rankings are merged."""
        allowed = [
            i for i, c in enumerate(self.chunks)
            if manufacturer is None or c.manufacturer == manufacturer
        ]
        meanings = self.meanings(queries, allowed, manufacturer) if queries else []
        keyword = np.zeros(len(self.chunks))
        rankings: list[list[int]] = []
        for q, query in enumerate(queries):
            scores = self.bm25.get_scores(tokenize(query))
            keyword = np.maximum(keyword, scores)
            by_keyword = [i for i in sorted(allowed, key=lambda i: -scores[i]) if scores[i] > 0]
            by_meaning = sorted(meanings[q], key=lambda i: (-meanings[q][i], i))  # ties keep the chunks' order
            rankings += {"keyword": [by_keyword], "meaning": [by_meaning], "hybrid": [by_keyword, by_meaning]}[mode]
        rankings = [self.spread(ranking) for ranking in rankings]
        files = {self.chunks[i].file for i in allowed}
        return [
            Hit(score=score, keyword=float(keyword[i]), meaning=max((m.get(i, 0.0) for m in meanings), default=0.0), chunk=self.chunks[i])
            for i, score in self.share_between_files(rrf(rankings), top_k, max(1, len(files)) if manufacturer else 1)
        ]

    # Stops one file taking all the places in the results.
    def share_between_files(self, ranked: list[tuple[int, float]], top_k: int, n_files: int) -> list[tuple[int, float]]:
        """The first top_k of the ranking, but no file takes more than its share of the places.

        A maker with six booklets that all say much the same must not have one booklet fill every place.
        Two children of one parent (parent-child chunking) take one place, since the model would read the same parent twice.
        """
        share = -(-top_k // n_files)  # rounded up
        taken: Counter[str] = Counter()
        parents: set[tuple[str, int, str]] = set()
        kept = []
        for i, score in ranked:
            chunk = self.chunks[i]
            file = chunk.file
            if chunk.parent:
                if (file, chunk.pdf_page, chunk.parent) in parents:
                    continue
                parents.add((file, chunk.pdf_page, chunk.parent))
            if taken[file] < share:
                taken[file] += 1
                kept.append((i, score))
        return kept[:top_k]

    # Allows only a couple of table rows per page in a ranking, so one big table cannot fill the results.
    def spread(self, ranking: list[int]) -> list[int]:
        """Keep the order but allow only a few table rows from any one page, so near-identical rows
        of one big table do not take up the top places of a ranking. Other chunks are never held back."""
        taken: Counter[tuple[str, int]] = Counter()
        kept = []
        for i in ranking:
            chunk = self.chunks[i]
            if chunk.kind == "table":
                page = (chunk.file, chunk.pdf_page)
                if taken[page] >= TABLE_ROWS_PER_PAGE:
                    continue
                taken[page] += 1
            kept.append(i)
        return kept
