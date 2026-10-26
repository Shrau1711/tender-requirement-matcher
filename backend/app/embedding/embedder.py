from __future__ import annotations

from functools import cache

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"


@cache
def model() -> TextEmbedding:
    return TextEmbedding(MODEL_NAME)  # downloads once, then loads from local cache


def embed_texts(texts: list[str]) -> np.ndarray:
    """One unit-length vector per text, so a dot product is cosine similarity."""
    vectors = np.array(list(model().embed(texts)))
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)