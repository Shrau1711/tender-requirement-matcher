from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from typing import Literal

import numpy as np
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from app.services.chunker import Chunk
from app.services.embed_cache import embed_cached
from app.services.fusion import rrf

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


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class Index:
    def __init__(self, chunks: list[Chunk], embed: Embedder = embed_cached) -> None:
        self.chunks = chunks
        self.embed = embed
        self.bm25 = BM25Okapi([tokenize(c.text) for c in chunks])
        self.vectors = embed([c.text for c in chunks])

    def search(
        self, query: str, manufacturer: str | None = None, top_k: int = 5, mode: Mode = "hybrid"
    ) -> list[Hit]:
        return self.search_many([query], manufacturer, top_k, mode)

    def search_many(
        self, queries: list[str], manufacturer: str | None = None, top_k: int = 5, mode: Mode = "hybrid"
    ) -> list[Hit]:
        """Best chunks for several phrasings of one need: every phrasing's rankings are merged."""
        allowed = [
            i for i, c in enumerate(self.chunks)
            if manufacturer is None or c.manufacturer == manufacturer
        ]
        meanings = self.vectors @ self.embed(queries).T  # one column per query
        keyword = np.zeros(len(self.chunks))
        rankings: list[list[int]] = []
        for q, query in enumerate(queries):
            scores = self.bm25.get_scores(tokenize(query))
            keyword = np.maximum(keyword, scores)
            by_keyword = [i for i in sorted(allowed, key=lambda i: -scores[i]) if scores[i] > 0]
            by_meaning = sorted(allowed, key=lambda i: -meanings[i, q])
            rankings += {"keyword": [by_keyword], "meaning": [by_meaning], "hybrid": [by_keyword, by_meaning]}[mode]
        rankings = [self.spread(ranking) for ranking in rankings]
        files = {self.chunks[i].file for i in allowed}
        return [
            Hit(score=score, keyword=float(keyword[i]), meaning=float(meanings[i].max()), chunk=self.chunks[i])
            for i, score in self.share_between_files(rrf(rankings), top_k, max(1, len(files)) if manufacturer else 1)
        ]

    def share_between_files(self, ranked: list[tuple[int, float]], top_k: int, n_files: int) -> list[tuple[int, float]]:
        """The first top_k of the ranking, but no file takes more than its share of the places.

        A maker with six booklets that all say much the same must not have one booklet fill every place.
        """
        share = -(-top_k // n_files)  # rounded up
        taken: Counter[str] = Counter()
        kept = []
        for i, score in ranked:
            file = self.chunks[i].file
            if taken[file] < share:
                taken[file] += 1
                kept.append((i, score))
        return kept[:top_k]

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
