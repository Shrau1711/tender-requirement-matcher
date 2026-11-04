"""What every embedder offers. A new embedder is a class with a name and an embed method, plus one line in EMBEDDERS."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np

EmbedFn = Callable[[list[str]], np.ndarray]  # texts in, one unit-length vector per text out (what search and chunking are given)


class Embedder(Protocol):
    name: str  # the model's own id; it is part of every saved vector's key, so two models never share a vector

    def embed(self, texts: list[str]) -> np.ndarray:
        """One unit-length vector per text, so a dot product is cosine similarity."""
        ...
