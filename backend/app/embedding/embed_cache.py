"""Embedding with a cache, so the model only embeds text it has not seen. The vectors are kept in Chroma
(app/vectorstore/vector_cache.py), the only place vectors are kept; this module only says how a text is keyed."""
from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from app.embedding.base import Embedder
from app.embedding.embedder import embedder as chosen

BATCH = 32  # texts embedded and saved at a time: memory stays small and an interrupted run keeps its progress


class VectorCache(Protocol):
    def get(self, keys: list[str]) -> dict[str, np.ndarray]: ...

    def put(self, vectors: dict[str, np.ndarray]) -> None: ...


# The model's name is part of the key, so two embedders never share a vector. For the default model the key is what it always was.
def key_for(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()


def default_cache() -> VectorCache:
    # imported here, not at the top: the vector store package uses this module
    from app.vectorstore.vector_cache import shared_vectors
    return shared_vectors()


def embed_cached(texts: list[str], cache: VectorCache | None = None, embedder: Embedder | None = None) -> np.ndarray:
    """Like embedder.embed, but a text seen before is read from the cache (Chroma unless another is given), so the model
    is only used for new text. The embedder is the one the EMBEDDER setting chooses unless one is given."""
    embedder = embedder or chosen()
    cache = cache if cache is not None else default_cache()
    keys = {text: key_for(text, embedder.name) for text in dict.fromkeys(texts)}
    stored = cache.get(list(keys.values()))
    found = {text: stored[key] for text, key in keys.items() if key in stored}
    missing = [text for text in keys if text not in found]
    for start in range(0, len(missing), BATCH):
        batch = missing[start:start + BATCH]
        new = {text: vector.astype(np.float32) for text, vector in zip(batch, embedder.embed(batch), strict=True)}
        cache.put({keys[text]: vector for text, vector in new.items()})
        found.update(new)
    return np.stack([found[t] for t in texts])
