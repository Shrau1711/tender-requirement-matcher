"""The retrievers, by name, and the one the RETRIEVER setting chooses. A new retriever is a class that follows
Retriever (app/retrieval/base.py) and one line in RETRIEVERS.

The default, hybrid, is the search every saved question was made with: keyword (BM25) and meaning rankings merged by
rank. keyword and meaning use one ranking alone; they find other passages, so the questions to the model change.
"""
from __future__ import annotations

from collections.abc import Callable

from app.chunking.base import Chunk
from app.config import text_setting
from app.embedding.base import EmbedFn
from app.embedding.embed_cache import embed_cached
from app.retrieval.base import Retriever
from app.retrieval.rerankers import RERANKER
from app.retrieval.search import VECTOR_SEARCH, Index
from app.vectorstore.base import VectorStore

RETRIEVER = text_setting("RETRIEVER", "hybrid")

# (chunks, embed, store, category, scoring=..., rerank_with=...) -> a retriever over them. scoring is VECTOR_SEARCH
# ("exact" or "chroma"), rerank_with is RERANKER ("none" or a name in rerankers.RERANKERS).
Make = Callable[..., Retriever]

RETRIEVERS: dict[str, Make] = {
    mode: (lambda chunks, embed, store, category, mode=mode, **options: Index(chunks, embed, store, category, mode, **options))
    for mode in ("hybrid", "keyword", "meaning")
}


def retriever(chunks: list[Chunk], store: VectorStore | None = None, category: str = "", name: str = RETRIEVER,
              embed: EmbedFn = embed_cached, scoring: str = VECTOR_SEARCH, rerank_with: str = RERANKER) -> Retriever:
    if name not in RETRIEVERS:
        raise ValueError(f"Unknown retriever {name!r}. Choose one of: {', '.join(RETRIEVERS)}")
    return RETRIEVERS[name](chunks, embed, store, category, scoring=scoring, rerank_with=rerank_with)
