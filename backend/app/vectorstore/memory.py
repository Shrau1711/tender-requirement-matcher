"""The original store: every vector in one NumPy matrix, compared with every query exactly. Nothing is kept on disk."""
from __future__ import annotations

import numpy as np

from app.chunking.base import Chunk
from app.vectorstore.base import StoredDoc, Where, check_where, chunk_ids, fields


class MemoryStore:
    name = "memory"

    def __init__(self) -> None:
        self.docs: dict[str, StoredDoc] = {}
        self.stored_chunks: dict[str, list[Chunk]] = {}
        self.ids: list[str] = []
        self.doc_of: list[str] = []
        self.fields: list[dict[str, str | int]] = []
        self.rows: list[np.ndarray] = []
        self.matrix: np.ndarray | None = None  # self.rows stacked, made again after a put

    def stored(self, doc: StoredDoc) -> bool:
        return self.docs.get(doc.id) == doc

    def chunks(self, doc: StoredDoc) -> list[Chunk]:
        return self.stored_chunks[doc.id]

    def put(self, doc: StoredDoc, chunks: list[Chunk], vectors: np.ndarray) -> None:
        keep = [i for i, d in enumerate(self.doc_of) if d != doc.id]
        self.ids, self.doc_of, self.fields, self.rows = ([xs[i] for i in keep] for xs in (self.ids, self.doc_of, self.fields, self.rows))
        self.ids += chunk_ids(doc.category, chunks)
        self.doc_of += [doc.id] * len(chunks)
        self.fields += [fields(doc.category, c) for c in chunks]
        self.rows += list(vectors)
        self.docs[doc.id], self.stored_chunks[doc.id] = doc, chunks
        self.matrix = None

    def vectors(self, ids: list[str]) -> np.ndarray:
        row = {chunk_id: i for i, chunk_id in enumerate(self.ids)}
        return np.stack([self.rows[row[i]] for i in ids])

    def nearest(self, queries: np.ndarray, n: int, where: Where) -> list[dict[str, float]]:
        check_where(where)
        if not self.rows:
            return [{} for _ in queries]
        if self.matrix is None:
            self.matrix = np.stack(self.rows)
        scores = self.matrix @ queries.T  # one column per query; vectors are unit length, so this is cosine similarity
        allowed = [i for i, f in enumerate(self.fields) if all(f[k] == v for k, v in where.items())]
        out = []
        for q in range(len(queries)):
            best = sorted(allowed, key=lambda i: -scores[i, q])[:n]
            out.append({self.ids[i]: float(scores[i, q]) for i in best})
        return out
