"""A store kept on disk with Chroma, so a document is read, chunked and embedded once and found again at the next start.

Chroma finds the nearest vectors with an approximate index (HNSW), so on large collections its order can differ slightly
from the exact NumPy store. Two collections are kept: one row per chunk (its vector, its fields to filter on, and the
whole chunk as JSON so it can be rebuilt without reading the PDF), and one row per document (its content hash and settings).

Chroma kept in a folder like this is for one process at a time. The app is one process; two scripts run at once on the same
folder can break its index, and the fix is to delete the folder, which is only a cache.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.chunking.base import Chunk
from app.vectorstore.base import StoredDoc, Where, check_where, chunk_ids, fields

BATCH = 1000  # rows sent to Chroma at a time; it refuses very large batches


def chroma_where(where: Where) -> dict | None:
    """Chroma's filter syntax: one field is {"field": value}; several must be joined with $and."""
    parts = [{k: v} for k, v in where.items()]
    return None if not parts else parts[0] if len(parts) == 1 else {"$and": parts}


class ChromaStore:
    name = "chroma"

    def __init__(self, folder: Path) -> None:
        import chromadb  # only needed when this store is chosen
        from chromadb.config import Settings

        folder.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(folder), settings=Settings(anonymized_telemetry=False))
        self.chunk_rows = client.get_or_create_collection("chunks", configuration={"hnsw": {"space": "cosine"}})
        self.doc_rows = client.get_or_create_collection("documents")

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

    def nearest(self, queries: np.ndarray, n: int, where: Where) -> list[dict[str, float]]:
        check_where(where)
        if n <= 0:
            return [{} for _ in queries]
        found = self.chunk_rows.query(query_embeddings=queries, n_results=n, where=chroma_where(where), include=["distances"])
        return [{i: 1.0 - d for i, d in zip(ids, distances, strict=True)} for ids, distances in zip(found["ids"], found["distances"], strict=True)]
