"""The RERANKER stage (off by default) and the tie-break both VECTOR_SEARCH paths share."""
from pathlib import Path

import numpy as np
import pytest

from app.chunking.base import Chunk
from app.retrieval import rerankers
from app.retrieval.rerankers import RERANKER, FastEmbedReranker, rerank, reranker
from app.retrieval.search import Index, by_score
from app.vectorstore.base import StoredDoc
from app.vectorstore.memory import MemoryStore

BACKEND = Path(__file__).resolve().parents[2]


def chunk(text, page=1, maker="a"):
    return Chunk(manufacturer=maker, file=f"{maker}.pdf", pdf_page=page, kind="text", section=None, text=text)


CHUNKS = [chunk("gate valve body cast steel", 1), chunk("gate valve stem packing", 2), chunk("wafer butterfly valve disc", 3),
          chunk("gate valve handwheel", 4)]


def embed(texts):
    return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)  # every text alike: meaning cannot tell them apart


class ByLength:
    """Scores longer passages higher, so its order is easy to predict."""
    name = "by-length"

    def __init__(self):
        self.calls = []

    def score(self, query, passages):
        self.calls.append((query, len(passages)))
        return [float(len(p)) for p in passages]


def test_the_default_is_no_reranker_and_an_unknown_one_is_refused():
    assert RERANKER == "none" and reranker("none") is None
    with pytest.raises(ValueError, match="Unknown reranker"):
        reranker("no-such-model")


def test_choosing_the_cross_encoder_does_not_load_or_download_it():
    assert "model" not in vars(FastEmbedReranker("Xenova/ms-marco-MiniLM-L-6-v2"))


def test_only_the_top_passages_are_rescored_with_the_best_phrasing_and_ties_keep_the_search_order():
    ranked = [(0, 0.9), (1, 0.8), (2, 0.7), (3, 0.6)]
    texts = {0: "aa", 1: "aaaa", 2: "aa", 3: "aaaaaaaa"}
    model = ByLength()
    out = rerank(model, ["q1", "q2"], ranked, texts.__getitem__, top=3)
    assert [i for i, _ in out] == [1, 0, 2, 3]  # 0 and 2 tie at length 2 and keep their order; 3 was not rescored
    assert model.calls == [("q1", 3), ("q2", 3)]


def test_the_index_puts_the_top_passages_in_the_rerankers_order(monkeypatch):
    model = ByLength()
    monkeypatch.setitem(rerankers.RERANKERS, "by-length", lambda: model)
    reranker.cache_clear()
    plain = Index(CHUNKS, embed, mode="keyword")
    ranked = Index(CHUNKS, embed, mode="keyword", rerank_with="by-length")
    searched = [h.chunk.text for h in plain.search("gate valve", top_k=4)]  # the search's own order, all four
    expected = sorted(searched, key=len, reverse=True)[:3]  # longest first; sorted is stable, so ties keep that order
    assert [h.chunk.text for h in ranked.search("gate valve", top_k=3)] == expected != searched[:3]
    reranker.cache_clear()


def test_exact_ties_are_ordered_by_the_chunks_original_order_in_both_paths():
    assert by_score({5: 0.5, 2: 0.7, 3: 0.5, 9: 0.7}) == [2, 9, 3, 5]
    store = MemoryStore()
    twins = [chunk("PN 25 / DN 150 row", 79), chunk("PN 25 / DN 150 row", 75)]  # one row printed on two pages
    store.put(StoredDoc(category="pumps", manufacturer="", file="all"), twins, np.array([[0.6, 0.8], [0.6, 0.8]], dtype=np.float32))
    for scoring in ("exact", "chroma"):
        index = Index(twins, embed, store, "pumps", "meaning", scoring)
        assert [h.chunk.pdf_page for h in index.search("row", "a", 2)] == [79, 75]  # the first stored chunk first


def test_the_cross_encoder_is_not_in_the_requirements_or_the_images():
    root = BACKEND.parent
    texts = [(BACKEND / "requirements.txt").read_text(encoding="utf-8"), (BACKEND / "Dockerfile").read_text(encoding="utf-8"),
             (root / "Dockerfile.demo").read_text(encoding="utf-8")]
    assert all("ms-marco" not in t and "RERANKER" not in t for t in texts)
