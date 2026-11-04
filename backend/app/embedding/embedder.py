"""The embedders, by name, and the one the EMBEDDER setting chooses.

The default, bge-small, is the model every saved vector and every saved question was made with. Another embedder gives
other vectors, so other passages are found and the questions to the model change: its answers are not saved.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import cache, cached_property

import numpy as np
from fastembed import TextEmbedding

from app.config import text_setting
from app.embedding.base import Embedder

DEFAULT = "bge-small"
EMBEDDER = text_setting("EMBEDDER", DEFAULT)


class FastEmbed:
    """A model run on this machine by fastembed. Downloaded once, then loaded from the local cache."""

    def __init__(self, name: str) -> None:
        self.name = name

    @cached_property
    def model(self) -> TextEmbedding:
        return TextEmbedding(self.name)  # loaded on first use, so choosing an embedder costs nothing

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.array(list(self.model.embed(texts)))
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


EMBEDDERS: dict[str, Callable[[], Embedder]] = {
    DEFAULT: lambda: FastEmbed("BAAI/bge-small-en-v1.5"),
}


@cache
def embedder(name: str = EMBEDDER) -> Embedder:
    if name not in EMBEDDERS:
        raise ValueError(f"Unknown embedder {name!r}. Choose one of: {', '.join(EMBEDDERS)}")
    return EMBEDDERS[name]()
