import hashlib

import numpy as np
import pytest

from app.chunking.corpus import load_chunks
from app.retrieval.search import Index
from app.vectorstore import ingest as ingest_module
from app.vectorstore.chroma import ChromaStore
from app.vectorstore.ingest import ingest, open_store
from app.vectorstore.memory import MemoryStore
from scripts.eval.make_samples import guide_pdf, specification_pdf


def fake_embed(texts):
    """A fixed vector per text, with no model: the bytes of its hash."""
    rows = [np.frombuffer(hashlib.sha256(t.encode()).digest(), dtype=np.uint8).astype(np.float32) - 127.5 for t in texts]
    vectors = np.stack(rows) if rows else np.zeros((0, 32), dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@pytest.fixture
def category(tmp_path):
    folder = tmp_path / "pumps"
    for maker, write in [("clausemaker", specification_pdf), ("flowmaker", guide_pdf)]:
        (folder / "manufacturers" / maker).mkdir(parents=True)
        write(folder / "manufacturers" / maker / f"{maker}.pdf")
    return folder


@pytest.fixture
def reads(monkeypatch):
    """The files read from disk, in order."""
    seen = []
    real = ingest_module.chunk_file

    def counting(pdf, *args):
        seen.append(pdf.name)
        return real(pdf, *args)

    monkeypatch.setattr(ingest_module, "chunk_file", counting)
    return seen


@pytest.fixture(params=["memory", "chroma"])
def store(request, tmp_path):
    return MemoryStore() if request.param == "memory" else ChromaStore(tmp_path / "chroma")


def test_ingest_gives_the_same_chunks_as_reading_the_files(category, store):
    assert ingest(category, store, embed=fake_embed) == load_chunks(category)


def test_a_file_is_read_once_and_again_only_after_it_changes(category, store, reads):
    ingest(category, store, embed=fake_embed)
    ingest(category, store, embed=fake_embed)
    assert reads == ["clausemaker.pdf", "flowmaker.pdf"]
    guide_pdf(category / "manufacturers" / "clausemaker" / "clausemaker.pdf")  # new content under the same name
    ingest(category, store, embed=fake_embed)
    assert reads[2:] == ["clausemaker.pdf"]


def test_another_chunker_reads_the_files_again(category, store, reads):
    ingest(category, store, embed=fake_embed)
    ingest(category, store, chunker="structure", embed=fake_embed)
    assert reads == ["clausemaker.pdf", "flowmaker.pdf"] * 2


def test_the_index_over_a_store_finds_what_the_index_over_the_chunks_finds(category, store):
    chunks = ingest(category, store, embed=fake_embed)
    over_store = Index(chunks, fake_embed, store=store, category="pumps")
    alone = Index(load_chunks(category), fake_embed)
    for query, maker in [("booster pump impeller", "clausemaker"), ("slurry valve", "flowmaker"), ("motor", None)]:
        expected = [(h.chunk.file, h.chunk.pdf_page, h.chunk.text) for h in alone.search(query, maker, 5)]
        assert [(h.chunk.file, h.chunk.pdf_page, h.chunk.text) for h in over_store.search(query, maker, 5)] == expected


def test_an_unknown_store_is_refused():
    with pytest.raises(ValueError, match="memory or chroma"):
        open_store("faiss")
