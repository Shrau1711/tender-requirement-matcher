import numpy as np
import pytest

from app.chunking.base import Chunk
from app.vectorstore.base import StoredDoc, chunk_ids
from app.vectorstore.chroma import ChromaStore
from app.vectorstore.memory import MemoryStore


def chunk(maker, file, page, text):
    return Chunk(manufacturer=maker, file=file, pdf_page=page, kind="text", section=None, text=text)


def unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


KSB = StoredDoc(category="valves", manufacturer="ksb", file="k.pdf", sha256="s1", settings="x")
L_T = StoredDoc(category="valves", manufacturer="l_and_t", file="l.pdf", sha256="s2", settings="x")
PUMP = StoredDoc(category="pumps", manufacturer="ksb", file="p.pdf", sha256="s3", settings="x")


@pytest.fixture(params=["memory", "chroma"])
def store(request, tmp_path):
    s = MemoryStore() if request.param == "memory" else ChromaStore(tmp_path / "chroma")
    s.put(KSB, [chunk("ksb", "k.pdf", 1, "gate valve"), chunk("ksb", "k.pdf", 2, "globe valve")], np.stack([unit(1, 0, 0), unit(1, 1, 0)]))
    s.put(L_T, [chunk("l_and_t", "l.pdf", 1, "ball valve")], np.stack([unit(1, 0.1, 0)]))
    s.put(PUMP, [chunk("ksb", "p.pdf", 1, "pump")], np.stack([unit(1, 0, 0.01)]))
    return s


def test_with_no_filter_every_chunk_is_a_candidate(store):
    # in no particular order: the index orders them by its own exact scores
    assert set(store.candidates({})) == {"valves/ksb/k.pdf#0", "valves/ksb/k.pdf#1", "valves/l_and_t/l.pdf#0", "pumps/ksb/p.pdf#0"}


@pytest.mark.parametrize(("where", "expected"), [
    ({"category": "valves"}, {"valves/ksb/k.pdf#0", "valves/ksb/k.pdf#1", "valves/l_and_t/l.pdf#0"}),
    ({"category": "valves", "manufacturer": "ksb"}, {"valves/ksb/k.pdf#0", "valves/ksb/k.pdf#1"}),
    ({"file": "p.pdf"}, {"pumps/ksb/p.pdf#0"}),
    ({"manufacturer": "ksb", "page": 2}, {"valves/ksb/k.pdf#1"}),
])
def test_candidates_can_be_narrowed_to_a_category_maker_file_or_page(store, where, expected):
    assert set(store.candidates(where)) == expected


def test_a_filter_on_an_unknown_field_is_refused(store):
    with pytest.raises(ValueError, match="Cannot filter"):
        store.candidates({"colour": "red"})


def test_a_file_is_stored_until_its_content_or_settings_change(store):
    assert store.stored(KSB)
    assert not store.stored(KSB.model_copy(update={"sha256": "changed"}))
    assert not store.stored(KSB.model_copy(update={"settings": "other chunker"}))
    assert [c.text for c in store.chunks(KSB)] == ["gate valve", "globe valve"]


def test_storing_a_file_again_replaces_its_old_chunks(store):
    store.put(KSB, [chunk("ksb", "k.pdf", 5, "new text")], np.stack([unit(0, 1, 0)]))
    assert [c.pdf_page for c in store.chunks(KSB)] == [5]
    assert store.candidates({"manufacturer": "ksb", "category": "valves"}) == ["valves/ksb/k.pdf#0"]


def test_a_chunk_comes_back_from_the_store_exactly_as_it_went_in(store):
    original = chunk("ksb", "k.pdf", 3, "x").model_copy(update={"section": "Body", "page_headings": ["KSB BOA"], "parent": "long text"})
    store.put(KSB, [original], np.stack([unit(1, 0, 0)]))
    assert store.chunks(KSB) == [original]


def test_chunk_names_count_within_each_file():
    chunks = [chunk("a", "1.pdf", 1, "x"), chunk("b", "2.pdf", 1, "y"), chunk("a", "1.pdf", 2, "z")]
    assert chunk_ids("valves", chunks) == ["valves/a/1.pdf#0", "valves/b/2.pdf#0", "valves/a/1.pdf#1"]


def test_the_chroma_store_is_still_there_after_a_restart(tmp_path):
    ChromaStore(tmp_path / "chroma").put(KSB, [chunk("ksb", "k.pdf", 1, "gate valve")], np.stack([unit(1, 0, 0)]))
    again = ChromaStore(tmp_path / "chroma")
    assert again.stored(KSB) and [c.text for c in again.chunks(KSB)] == ["gate valve"]


def test_vectors_come_back_exactly_in_the_order_asked(store):
    rng = np.random.default_rng(0)
    vectors = rng.standard_normal((40, 3)).astype(np.float32)  # enough values that a changed last digit would show
    store.put(KSB, [chunk("ksb", "k.pdf", p, "x") for p in range(40)], vectors)
    order = list(rng.permutation(40))
    assert np.array_equal(store.vectors([f"valves/ksb/k.pdf#{i}" for i in order]), vectors[order])


class Stuck:
    """Stands in for a Chroma collection whose reads fail with `message`."""

    def __init__(self, message):
        self.message = message

    def get(self, **_):
        from chromadb.errors import InternalError

        raise InternalError(self.message)


STUCK_MESSAGE = "Error executing plan: Internal error: Error creating hnsw segment reader: Nothing found on disk"


def test_a_stuck_client_is_closed_and_a_new_one_reads_the_store(tmp_path, caplog):
    store = ChromaStore(tmp_path / "chroma")
    store.put(KSB, [chunk("ksb", "k.pdf", 1, "gate valve")], np.stack([unit(1, 0, 0)]))
    stuck_client = store.client
    store.chunk_rows = Stuck(STUCK_MESSAGE)
    assert store.candidates({"manufacturer": "ksb"}) == ["valves/ksb/k.pdf#0"]
    assert store.client is not stuck_client and "Opening a new client" in caplog.text
    assert np.array_equal(store.vectors(["valves/ksb/k.pdf#0"]), np.stack([unit(1, 0, 0)]))


def test_any_other_chroma_error_is_raised_without_reopening(tmp_path):
    from chromadb.errors import InternalError

    store = ChromaStore(tmp_path / "chroma")
    client = store.client
    store.chunk_rows = Stuck("Error executing plan: something else")
    with pytest.raises(InternalError, match="something else"):
        store.candidates({})
    assert store.client is client


def test_a_store_still_stuck_after_reopening_raises(tmp_path, monkeypatch):
    from chromadb.errors import InternalError

    store = ChromaStore(tmp_path / "chroma")
    opened = []

    def open_stuck():
        opened.append(1)
        store.chunk_rows = Stuck(STUCK_MESSAGE)

    store.chunk_rows = Stuck(STUCK_MESSAGE)
    monkeypatch.setattr(store, "open", open_stuck)
    with pytest.raises(InternalError, match="hnsw segment reader"):
        store.vectors(["valves/ksb/k.pdf#0"])
    assert opened == [1]  # one reopen, one more read, then the error
