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
from app.retrieval.search import VECTOR_SEARCH, Index
from app.vectorstore.base import VectorStore

RETRIEVER = text_setting("RETRIEVER", "hybrid")

# (chunks, embed, store, category, scoring) -> a retriever over them; scoring is VECTOR_SEARCH ("exact" or "chroma")
Make = Callable[[list[Chunk], EmbedFn, VectorStore | None, str, str], Retriever]

RETRIEVERS: dict[str, Make] = {
    mode: (lambda chunks, embed, store, category, scoring, mode=mode: Index(chunks, embed, store, category, mode, scoring))
    for mode in ("hybrid", "keyword", "meaning")
}


def retriever(chunks: list[Chunk], store: VectorStore | None = None, category: str = "", name: str = RETRIEVER,
              embed: EmbedFn = embed_cached, scoring: str = VECTOR_SEARCH) -> Retriever:
    if name not in RETRIEVERS:
        raise ValueError(f"Unknown retriever {name!r}. Choose one of: {', '.join(RETRIEVERS)}")
    return RETRIEVERS[name](chunks, embed, store, category, scoring)
