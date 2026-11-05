"""The text -> vector cache, kept in Chroma ("vectors" collection, see chroma.py): Chroma is the only place vectors are kept.

Every text the embedder has seen, a chunk or a search query, is stored once under key_for(text, model), so the model only
embeds new text. Two SQLite files are imported once; after that no vector is read from them, only their fingerprint is
checked once per start:
- the shipped seed (data/seed_embeddings.sqlite): vectors computed where the saved answers were made. Another machine
  computes slightly different vectors, which can reorder passages and so miss a saved answer;
- this machine's older cache (backend/.cache/embeddings.sqlite), if it exists, so vectors computed here earlier are kept.
Each import is recorded with the file's SHA-256: the same file is not imported twice, a changed seed is imported again.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
import threading
from functools import cache
from pathlib import Path

import numpy as np

from app.config import cache_dir, path_setting
from app.vectorstore.chroma import ChromaStore

SEED_FILE = path_setting("SEED_EMBEDDINGS", Path(__file__).resolve().parents[3] / "data" / "seed_embeddings.sqlite")
OLD_CACHE = cache_dir() / "embeddings.sqlite"  # where vectors were kept before; imported once if it exists
WRITING = threading.Lock()


def sha256_of(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def import_once(store: ChromaStore, name: str, file: Path | None) -> int:
    """Copy every vector of a SQLite cache file (table vectors: key, vector) into Chroma, unless this very file was
    imported before. Returns how many vectors were copied."""
    if file is None or not file.exists():
        return 0
    fingerprint = sha256_of(file)
    if store.imported(name) == fingerprint:
        return 0
    with sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True) as db:
        rows = {key: np.frombuffer(blob, dtype=np.float32) for key, blob in db.execute("SELECT key, vector FROM vectors")}
    store.keep_vectors(rows)
    store.mark_imported(name, fingerprint, len(rows))
    print(f"[vectors] imported {len(rows)} vectors from {file.name} into Chroma (once)", file=sys.stderr)
    return len(rows)


class ChromaVectors:
    """The cache embed_cached uses: get and put by key, in the store's "vectors" collection."""

    def __init__(self, store: ChromaStore, seed: Path | None = SEED_FILE, old_cache: Path | None = OLD_CACHE) -> None:
        self.store = store
        with WRITING:
            import_once(store, "seed", seed)          # first the shipped seed,
            import_once(store, "old_cache", old_cache)  # then this machine's own, which held the seed's vectors too

    def get(self, keys: list[str]) -> dict[str, np.ndarray]:
        return self.store.cached_vectors(keys)

    def put(self, vectors: dict[str, np.ndarray]) -> None:
        with WRITING:
            self.store.keep_vectors(vectors)


@cache
def shared_vectors() -> ChromaVectors:
    """The cache in the store's own Chroma folder, opened (and its imports done) once per process."""
    from app.vectorstore.ingest import (  # ingest uses embed_cached, which uses this
        chroma_folder,
        chroma_store,
    )
    return ChromaVectors(chroma_store(chroma_folder()))
