from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.config import cache_dir, path_setting
from app.services.embedder import MODEL_NAME, embed_texts

CACHE_FILE = cache_dir() / "embeddings.sqlite"
# A copy of the vectors computed where the shipped model answers were saved (read only). Another machine computes slightly different vectors, which can change
# the order of the passages in a question and so the question itself, and a changed question does not find its saved answer.
SEED_FILE = path_setting("SEED_EMBEDDINGS", Path(__file__).resolve().parents[3] / "data" / "seed_embeddings.sqlite")
BATCH = 32  # texts embedded and saved at a time: memory stays small and an interrupted run keeps its progress


def key_for(text: str) -> str:
    return hashlib.sha256(f"{MODEL_NAME}\x00{text}".encode()).hexdigest()


def read_vector(db: sqlite3.Connection, text: str) -> np.ndarray | None:
    row = db.execute("SELECT vector FROM vectors WHERE key = ?", (key_for(text),)).fetchone()
    return np.frombuffer(row[0], dtype=np.float32) if row else None


def open_seed(seed_file: Path | None) -> sqlite3.Connection | None:
    return sqlite3.connect(f"{seed_file.resolve().as_uri()}?mode=ro", uri=True) if seed_file and seed_file.exists() else None


def embed_cached(
    texts: list[str],
    cache_file: Path = CACHE_FILE,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
    seed_file: Path | None = SEED_FILE,
) -> np.ndarray:
    """Like embed_texts, but a text seen before is read from disk (this machine's cache, then the shipped seed), so the model is only used for new text."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    seed = open_seed(seed_file)
    with sqlite3.connect(cache_file) as db:
        db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB)")
        found = {}
        for text in set(texts):
            vector = read_vector(db, text)
            if vector is None and seed:
                vector = read_vector(seed, text)
            if vector is not None:
                found[text] = vector
        missing = [t for t in dict.fromkeys(texts) if t not in found]
        for start in range(0, len(missing), BATCH):
            batch = missing[start:start + BATCH]
            for text, vector in zip(batch, embed(batch), strict=True):
                found[text] = vector.astype(np.float32)
                db.execute("INSERT INTO vectors VALUES (?, ?)", (key_for(text), found[text].tobytes()))
            db.commit()
    if seed:
        seed.close()
    return np.stack([found[t] for t in texts])
