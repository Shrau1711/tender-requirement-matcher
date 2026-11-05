"""A store kept on disk with Chroma, so a document is read, chunked and embedded once and found again at the next start.
Chroma is the only place vectors are kept (see vector_cache.py).

Four collections:
- "chunks": one row per chunk: its vector, its fields to filter on, and the whole chunk as JSON so it can be rebuilt
  without reading the PDF;
- "documents": one row per document: its content hash and settings;
- "vectors": every text the embedder has seen (chunks and search queries), by key, so no text is embedded twice; looked
  up by key, never searched;
- "imports": which files were imported into "vectors" (the shipped seed, an older local cache), so each is imported once.

Two ways to rank by meaning (VECTOR_SEARCH, see retrieval/search.py). "exact", the default: the store filters and the
index scores the candidates itself from the stored vectors. "chroma": Chroma ranks them with its own nearest-neighbour
search (nearest), with HNSW settings chosen to be as exact as possible at these sizes (a few thousand chunks). Even so its
arithmetic differs from NumPy's in the last digits, which reorders near-equal passages (measured; see docs/CHANGES.md).

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
# HNSW for native search. A category holds about 2,000 chunks and a maker up to 1,600, so the search may look at every
# one (ef_search) and the graph is built densely (ef_construction, max_neighbors), as exact as HNSW gets at this size.
HNSW = {"space": "ip", "ef_construction": 512, "max_neighbors": 64, "ef_search": 10000}
FIXED = ("space", "ef_construction", "max_neighbors")  # set when a collection is made; the rest can be changed later
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
        self.chunk_rows = self.client.get_or_create_collection("chunks", configuration={"hnsw": HNSW})
        if any(self.chunk_rows.configuration.get("hnsw", {}).get(k) != HNSW[k] for k in FIXED):
            # made before these settings: rebuilt once (it is a cache; ingest reads the documents again)
            log.warning("The Chroma chunk store was made with other search settings; rebuilding it once.")
            for name in ("chunks", "documents"):
                self.client.delete_collection(name)
            self.chunk_rows = self.client.get_or_create_collection("chunks", configuration={"hnsw": HNSW})
        elif self.chunk_rows.configuration.get("hnsw", {}).get("ef_search") != HNSW["ef_search"]:
            self.chunk_rows.modify(configuration={"hnsw": {"ef_search": HNSW["ef_search"]}})
        self.doc_rows = self.client.get_or_create_collection("documents")
        self.vector_rows = self.client.get_or_create_collection("vectors", configuration={"hnsw": {"space": "ip"}})
        self.import_rows = self.client.get_or_create_collection("imports")

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

    def nearest(self, queries: np.ndarray, where: Where, n: int) -> list[list[tuple[str, float]]]:
        """Chroma's own ranking: for each query, up to n chunks matching `where`, nearest first, with their similarity
        (1 - Chroma's inner-product distance)."""
        check_where(where)
        if n == 0:
            return [[] for _ in queries]
        found = self.reading(lambda: self.chunk_rows.query(query_embeddings=queries, n_results=n, where=chroma_where(where),
                                                           include=["distances"]), "the nearest chunks")
        return [[(i, 1.0 - d) for i, d in zip(ids, distances, strict=True)] for ids, distances in zip(found["ids"], found["distances"], strict=True)]

    def cached_vectors(self, keys: list[str]) -> dict[str, np.ndarray]:
        """The stored vectors of these text keys, for those that have one."""
        rows: dict[str, np.ndarray] = {}
        for start in range(0, len(keys), BATCH):
            batch = keys[start:start + BATCH]
            found = self.reading(lambda batch=batch: self.vector_rows.get(ids=batch, include=["embeddings"]), "the cached vectors")
            rows.update((i, np.asarray(v, dtype=np.float32)) for i, v in zip(found["ids"], found["embeddings"], strict=True))
        return rows

    def keep_vectors(self, vectors: dict[str, np.ndarray]) -> None:
        keys = list(vectors)
        for start in range(0, len(keys), BATCH):
            batch = keys[start:start + BATCH]
            self.vector_rows.upsert(ids=batch, embeddings=np.stack([vectors[k] for k in batch]))

    def imported(self, name: str) -> str | None:
        """The fingerprint of the file last imported under this name, if any."""
        found = self.import_rows.get(ids=[name], include=["metadatas"])["metadatas"]
        return found[0]["sha256"] if found else None

    def mark_imported(self, name: str, sha256: str, rows: int) -> None:
        self.import_rows.upsert(ids=[name], metadatas=[{"sha256": sha256, "rows": rows}], embeddings=[[0.0]])
