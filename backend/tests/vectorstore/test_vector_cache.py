"""Chroma as the only store of vectors: the text -> vector cache, the one-time imports, and Chroma's own ranking."""
import sqlite3

import numpy as np
import pytest

from app.chunking.base import Chunk
from app.embedding.embed_cache import embed_cached, key_for
from app.retrieval.search import Index
from app.vectorstore.base import StoredDoc
from app.vectorstore.chroma import HNSW, ChromaStore
from app.vectorstore.memory import MemoryStore
from app.vectorstore.vector_cache import ChromaVectors, import_once


class Counting:
    name = "fake-model"

    def __init__(self):
        self.asked = []

    def embed(self, texts):
        self.asked += texts
        return np.array([[float(len(t)), 1.0, 0.5] for t in texts])


def sqlite_cache(file, rows):
    """A cache file in the old SQLite form: table vectors (key, vector bytes)."""
    with sqlite3.connect(file) as db:
        db.execute("CREATE TABLE vectors (key TEXT PRIMARY KEY, vector BLOB)")
        db.executemany("INSERT INTO vectors VALUES (?, ?)", [(k, np.asarray(v, dtype=np.float32).tobytes()) for k, v in rows.items()])
    return file


@pytest.fixture
def store(tmp_path):
    return ChromaStore(tmp_path / "chroma")


def test_the_seed_and_the_old_cache_are_imported_once_and_read_back_exactly(store, tmp_path):
    awkward = np.array([0.1, 1 / 3, -2e-8], dtype=np.float32)  # last digits that must survive the trip
    seed = sqlite_cache(tmp_path / "seed.sqlite", {key_for("wafer", "fake-model"): awkward})
    old = sqlite_cache(tmp_path / "old.sqlite", {key_for("lug", "fake-model"): [1, 2, 3]})
    cache = ChromaVectors(store, seed, old)
    model = Counting()
    vectors = embed_cached(["wafer", "lug"], cache, model)
    assert model.asked == [] and vectors[0].tobytes() == awkward.tobytes() and vectors[1].tolist() == [1, 2, 3]
    assert import_once(store, "seed", seed) == 0 and import_once(store, "old_cache", old) == 0  # already imported


def test_a_changed_seed_is_imported_again(store, tmp_path):
    seed = sqlite_cache(tmp_path / "seed.sqlite", {"a": [1, 1, 1]})
    assert import_once(store, "seed", seed) == 1
    with sqlite3.connect(seed) as db:
        db.execute("INSERT INTO vectors VALUES (?, ?)", ("b", np.ones(3, dtype=np.float32).tobytes()))
    assert import_once(store, "seed", seed) == 2 and set(store.cached_vectors(["a", "b"])) == {"a", "b"}


def test_new_text_is_kept_in_chroma_and_no_sqlite_file_is_written(store, tmp_path):
    cache = ChromaVectors(store, None, None)
    model = Counting()
    embed_cached(["gate valve"], cache, model)
    embed_cached(["gate valve"], ChromaVectors(ChromaStore(tmp_path / "chroma"), None, None), model)  # a new client, same folder
    assert model.asked == ["gate valve"]
    assert not list(tmp_path.rglob("embeddings.sqlite"))


CHUNKS = [Chunk(manufacturer=m, file=f"{m}.pdf", pdf_page=1, kind="text", section=None, text=t)
          for m, t in [("a", "gate valve body"), ("a", "wafer seat"), ("a", "pump impeller"), ("b", "gate valve stem")]]
VECTORS = np.array([[1, 0, 0], [0.6, 0.8, 0], [0, 0, 1], [0.8, 0.6, 0]], dtype=np.float32)


def test_both_stores_rank_by_meaning_for_the_index(store):
    memory = MemoryStore()
    for s in (store, memory):
        s.put(StoredDoc(category="valves", manufacturer="", file="all"), CHUNKS, VECTORS)
    query = np.array([[1, 0.1, 0]], dtype=np.float32)
    for s in (store, memory):
        ranked = s.nearest(query, {"category": "valves", "manufacturer": "a"}, 3)[0]
        assert [i for i, _ in ranked] == ["valves/a/a.pdf#0", "valves/a/a.pdf#1", "valves/a/a.pdf#2"]
        assert ranked[0][1] == pytest.approx(1.0, abs=1e-6)


def test_native_scoring_takes_the_stores_order_and_keeps_bm25_and_fusion(store):
    store.put(StoredDoc(category="valves", manufacturer="", file="all"), CHUNKS, VECTORS)
    embed = lambda texts: np.array([[1, 0.1, 0]] * len(texts), dtype=np.float32)
    exact = Index(CHUNKS, embed, store, "valves", "hybrid", "exact")
    native = Index(CHUNKS, embed, store, "valves", "hybrid", "chroma")
    for mode in ("keyword", "meaning", "hybrid"):
        assert [h.chunk.text for h in native.search("gate valve", "a", 3, mode)] == [h.chunk.text for h in exact.search("gate valve", "a", 3, mode)]
    with pytest.raises(ValueError, match="Unknown VECTOR_SEARCH"):
        Index(CHUNKS, embed, store, "valves", "hybrid", "approximate")


def test_the_chunk_collection_is_built_for_near_exact_search_and_an_older_one_is_rebuilt(tmp_path):
    import chromadb
    from chromadb.config import Settings

    old = chromadb.PersistentClient(path=str(tmp_path / "old"), settings=Settings(anonymized_telemetry=False))
    old.get_or_create_collection("chunks", configuration={"hnsw": {"space": "ip"}}).add(ids=["x"], embeddings=[[1.0, 0.0]])
    old.get_or_create_collection("documents").add(ids=["valves/a/a.pdf"], embeddings=[[0.0]], metadatas=[{"sha256": "s", "settings": "t"}])
    del old
    rebuilt = ChromaStore(tmp_path / "old")
    hnsw = rebuilt.chunk_rows.configuration["hnsw"]
    assert {k: hnsw[k] for k in HNSW} == HNSW
    assert rebuilt.chunk_rows.count() == 0  # rebuilt empty, so every document is read again once
    assert not rebuilt.stored(StoredDoc(category="valves", manufacturer="a", file="a.pdf", sha256="s", settings="t"))
