"""Rerankers: after the search, a cross-encoder reads the query together with each of the top passages and scores them
again, and those passages are put in its order. The RERANKER setting chooses one:
- none (the default): the search's own order, which every saved question was made with;
- minilm: fastembed's Xenova/ms-marco-MiniLM-L-6-v2 cross-encoder (about 80 MB, Apache-2.0), run on this machine.

fastembed is already installed for the embedder, so nothing new is installed; the model file is downloaded on first
use only, and is in no requirements file or image. RERANK_TOP passages are rescored (40 by default, within the 30 to 50
a cross-encoder is usually given), the rest keep their place after them. A new reranker is a class with a name and
score(query, passages), plus one line in RERANKERS.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import cache, cached_property

from app.config import number_setting, text_setting
from app.retrieval.base import Reranker

RERANKER = text_setting("RERANKER", "none")
RERANK_TOP = number_setting("RERANK_TOP", 40)


class FastEmbedReranker:
    def __init__(self, model_name: str) -> None:
        self.name = model_name

    @cached_property
    def model(self):
        # imported, and the model downloaded, on first use only
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        return TextCrossEncoder(model_name=self.name)

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self.model.rerank(query, passages)]


RERANKERS: dict[str, Callable[[], Reranker]] = {
    "minilm": lambda: FastEmbedReranker("Xenova/ms-marco-MiniLM-L-6-v2"),
}


@cache
def reranker(name: str = RERANKER) -> Reranker | None:
    """The reranker by name, made once; None for "none"."""
    if name == "none":
        return None
    if name not in RERANKERS:
        raise ValueError(f"Unknown reranker {name!r}. Choose one of: none, {', '.join(RERANKERS)}")
    return RERANKERS[name]()


def rerank(model: Reranker, queries: list[str], ranked: list[tuple[int, float]], text: Callable[[int], str],
           top: int = RERANK_TOP) -> list[tuple[int, float]]:
    """The first `top` of a ranking put in the reranker's order (each passage scored against every phrasing, the best
    score kept); a tie keeps the search's order. The rest follow unchanged."""
    head, tail = ranked[:top], ranked[top:]
    if not head:
        return ranked
    passages = [text(i) for i, _ in head]
    best = [max(scores) for scores in zip(*(model.score(q, passages) for q in queries), strict=True)]
    order = sorted(range(len(head)), key=lambda n: -best[n])  # stable: a tie keeps the search's order
    return [(head[n][0], best[n]) for n in order] + tail
