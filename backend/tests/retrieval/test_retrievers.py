import numpy as np
import pytest

from app.chunking.base import Chunk
from app.retrieval.base import Hit
from app.retrieval.retrievers import RETRIEVER, RETRIEVERS, retriever
from app.retrieval.search import Index


def chunk(maker: str, text: str) -> Chunk:
    return Chunk(manufacturer=maker, file=f"{maker}.pdf", pdf_page=len(text), kind="text", section=None, text=text)


def fake_embed(texts):
    return np.array([[1.0, 0.0] if "valve" in t else [0.0, 1.0] for t in texts])


CHUNKS = [chunk("a", "gate valve body"), chunk("a", "wafer seat"), chunk("a", "valve wafer"), chunk("a", "other text")]


def ranked(hits: list[Hit]) -> list[tuple[str, float]]:
    return [(h.chunk.text, h.score) for h in hits]


def test_the_default_retriever_is_the_hybrid_search_every_saved_question_was_made_with():
    assert RETRIEVER == "hybrid"
    found = retriever(CHUNKS, embed=fake_embed)
    assert isinstance(found, Index) and found.name == "hybrid"
    assert ranked(found.search_many(["wafer valve"], "a", 3)) == ranked(Index(CHUNKS, fake_embed).search_many(["wafer valve"], "a", 3, "hybrid"))


@pytest.mark.parametrize("name", ["keyword", "meaning"])
def test_a_one_ranking_retriever_searches_that_way_unless_asked_otherwise(name):
    found = retriever(CHUNKS, name=name, embed=fake_embed)
    plain = Index(CHUNKS, fake_embed)
    assert ranked(found.search("wafer", "a", 3)) == ranked(plain.search("wafer", "a", 3, name))
    assert ranked(found.search("wafer", "a", 3, "hybrid")) == ranked(plain.search("wafer", "a", 3, "hybrid"))


def test_an_unknown_retriever_is_refused():
    with pytest.raises(ValueError, match="Unknown retriever"):
        retriever(CHUNKS, name="no-such-search", embed=fake_embed)


def test_a_new_retriever_is_one_line(monkeypatch):
    class FirstChunks:
        name = "first"

        def __init__(self, chunks, embed, store, category, scoring):
            self.chunks, self.vectors = chunks, None

        def search(self, query, manufacturer=None, top_k=5, mode=None):
            return self.search_many([query], manufacturer, top_k, mode)

        def search_many(self, queries, manufacturer=None, top_k=5, mode=None):
            return [Hit(score=0.0, keyword=0.0, meaning=0.0, chunk=c) for c in self.chunks[:top_k]]

    monkeypatch.setitem(RETRIEVERS, "first", FirstChunks)
    found = retriever(CHUNKS, name="first", embed=fake_embed)
    assert [h.chunk.text for h in found.search("anything", top_k=2)] == ["gate valve body", "wafer seat"]
