"""A store kept on disk with Chroma, so a document is read, chunked and embedded once and found again at the next start.

Chroma stores and filters; it does not score. Its nearest-neighbour search (HNSW) is approximate and its arithmetic
differs from NumPy's in the last digits, which reordered near-equal passages. The search needs every chunk of a
manufacturer anyway, so the candidates are fetched by filter, and the index scores them exactly from the stored vectors
(see Index.meanings). Two collections are kept: one row per chunk (its vector, its fields to filter on, and the whole
chunk as JSON so it can be rebuilt without reading the PDF), and one row per document (its content hash and settings).

On Windows (only, so far), right after writes, Chroma 1.5.9 sometimes cannot open its index files ("Error creating hnsw
segment reader: Nothing found on disk"), also when only the stored vectors are read, and the client stays stuck: waiting
does not help, but a newly opened client reads the same store. So reading the vectors or the candidates closes a stuck
client, opens a new one and reads once more, with a warning (see `reading`). The cause inside Chroma is not known;
scripts/diagnose/chroma_repro.py reproduces it without this app.

Chroma kept in a folder like this is for one process at a time. The app is one process; two scripts run at once on the same
folder can break its index, and the fix is to delete the folder, which is only a cache.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import numpy as np

from app.chunking.base import Chunk
from app.vectorstore.base import StoredDoc, Where, check_where, chunk_ids, fields

BATCH = 1000  # rows sent to Chroma at a time; it refuses very large batches
STUCK = "Error creating hnsw segment reader"  # the one Chroma error a new client gets past; every other error is raised

log = logging.getLogger(__name__)
T = TypeVar("T")


def chroma_where(where: Where) -> dict | None:
    """Chroma's filter syntax: one field is {"field": value}; several must be joined with $and."""
    parts = [{k: v} for k, v in where.items()]
    return None if not parts else parts[0] if len(parts) == 1 else {"$and": parts}


class ChromaStore:
    name = "chroma"

    def __init__(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.folder = folder
        self.open()

    def open(self) -> None:
        import chromadb  # only needed when this store is chosen
        from chromadb.config import Settings

        self.client = chromadb.PersistentClient(path=str(self.folder), settings=Settings(anonymized_telemetry=False))
        # Inner product, not cosine: the vectors are already unit length, so the two are the same. In cosine mode Chroma
        # gives the vectors back with some last digits changed (measured), which would change the exact scores.
        self.chunk_rows = self.client.get_or_create_collection("chunks", configuration={"hnsw": {"space": "ip"}})
        self.doc_rows = self.client.get_or_create_collection("documents")

    def reading(self, read: Callable[[], T], what: str) -> T:
        """Runs a read. If the client is stuck unable to open its index, closes it, opens a new one and reads once more.

        Closing frees Chroma's state for this folder only when no other client has it open; the app keeps one client
        per folder (see ingest.chroma_store)."""
        from chromadb.errors import InternalError

        try:
            return read()
        except InternalError as error:
            if STUCK not in str(error):
                raise
            log.warning("Chroma could not read %s (%s). Opening a new client and reading once more.", what, error)
            self.client.close()
            self.open()
            return read()

    def stored(self, doc: StoredDoc) -> bool:
        found = self.doc_rows.get(ids=[doc.id], include=["metadatas"])["metadatas"]
        return bool(found) and found[0] == {"sha256": doc.sha256, "settings": doc.settings}

    def chunks(self, doc: StoredDoc) -> list[Chunk]:
        rows = self.chunk_rows.get(where={"doc": doc.id}, include=["metadatas"])["metadatas"]
        return [Chunk.model_validate_json(m["chunk"]) for m in sorted(rows, key=lambda m: m["n"])]

    def put(self, doc: StoredDoc, chunks: list[Chunk], vectors: np.ndarray) -> None:
        self.chunk_rows.delete(where={"doc": doc.id})
        ids = chunk_ids(doc.category, chunks)
        metadatas = [{**fields(doc.category, c), "doc": doc.id, "n": n, "chunk": c.model_dump_json()} for n, c in enumerate(chunks)]
        for start in range(0, len(chunks), BATCH):
            end = start + BATCH
            self.chunk_rows.add(ids=ids[start:end], embeddings=vectors[start:end], metadatas=metadatas[start:end])
        # the document row goes last, so a run stopped halfway leaves the file marked as not stored
        self.doc_rows.upsert(ids=[doc.id], metadatas=[{"sha256": doc.sha256, "settings": doc.settings}], embeddings=[[0.0]])

    def vectors(self, ids: list[str]) -> np.ndarray:
        rows = {}
        for start in range(0, len(ids), BATCH):
            batch = ids[start:start + BATCH]
            found = self.reading(lambda batch=batch: self.chunk_rows.get(ids=batch, include=["embeddings"]), "the stored vectors")
            rows.update(zip(found["ids"], found["embeddings"], strict=True))
        return np.stack([np.asarray(rows[i], dtype=np.float32) for i in ids])

    def candidates(self, where: Where) -> list[str]:
        check_where(where)
        return self.reading(lambda: self.chunk_rows.get(where=chroma_where(where), include=[]), "the matching chunks")["ids"]
