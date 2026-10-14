from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.config import cache_dir
from app.services.embedder import MODEL_NAME, embed_texts

CACHE_FILE = cache_dir() / "embeddings.sqlite"


def key_for(text: str) -> str:
    return hashlib.sha256(f"{MODEL_NAME}\x00{text}".encode()).hexdigest()


def embed_cached(
    texts: list[str],
    cache_file: Path = CACHE_FILE,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> np.ndarray:
    """Like embed_texts, but a text seen before is read from disk, so the model is only used for new text."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(cache_file) as db:
        db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB)")
        found = {}
        for text in set(texts):
            row = db.execute("SELECT vector FROM vectors WHERE key = ?", (key_for(text),)).fetchone()
            if row:
                found[text] = np.frombuffer(row[0], dtype=np.float32)
        missing = [t for t in dict.fromkeys(texts) if t not in found]
        if missing:
            for text, vector in zip(missing, embed(missing), strict=True):
                found[text] = vector.astype(np.float32)
                db.execute("INSERT INTO vectors VALUES (?, ?)", (key_for(text), found[text].tobytes()))
    return np.stack([found[t] for t in texts])
