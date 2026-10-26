import numpy as np

from app.chunking.chunker import Chunk
from app.retrieval.fusion import rrf
from app.retrieval.search import Index, tokenize


def fake_embed(texts: list[str]) -> np.ndarray:
    """Offline stand-in: one dimension per word, so texts sharing words are similar."""
    vocab = ["wafer", "lug", "valve", "gate", "other", "text", "more"]
    vectors = np.array([[float(w in t.lower()) for w in vocab] for t in texts]) + 1e-6
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def chunk(manufacturer: str, text: str, kind: str = "text", file: str = "f.pdf") -> Chunk:
    return Chunk(manufacturer=manufacturer, file=file, pdf_page=1, kind=kind, section=None, text=text)


def test_tokenize_splits_letters_from_numbers():
    assert tokenize("DN125 PN-16") == ["dn", "125", "pn", "16"]


def test_standard_numbers_are_not_confused():
    index = Index([chunk("a", "Designed to IS 3095"), chunk("b", "Designed to IS 13095"), chunk("c", "other")], fake_embed)
    assert index.search("IS 13095")[0].chunk.manufacturer == "b"


def test_manufacturer_filter():
    index = Index([chunk("a", "wafer valve"), chunk("b", "wafer valve"), chunk("c", "other")], fake_embed)
    assert {h.chunk.manufacturer for h in index.search("wafer", manufacturer="a")} == {"a"}


def test_rrf_rewards_agreement_between_lists():
    assert rrf([[1, 2, 3], [3, 1, 4]])[0][0] == 1


def test_hit_carries_both_raw_scores():
    index = Index([chunk("a", "gate valve"), chunk("b", "wafer"), chunk("c", "other")], fake_embed)
    hit = index.search("gate")[0]
    assert hit.chunk.text == "gate valve" and hit.keyword > 0


def test_keyword_mode_ignores_meaning():
    index = Index([chunk("a", "gate valve"), chunk("b", "wafer"), chunk("c", "other")], fake_embed)
    assert [h.chunk.text for h in index.search("gate", mode="keyword")] == ["gate valve"]


def test_search_many_merges_every_phrasing():
    index = Index([chunk("a", "gate valve"), chunk("a", "wafer valve"), chunk("a", "other"), chunk("a", "text"), chunk("a", "more")], fake_embed)
    found = {h.chunk.text for h in index.search_many(["gate", "wafer"], mode="keyword")}
    assert found == {"gate valve", "wafer valve"}


def test_one_big_table_cannot_fill_every_result():
    rows = [chunk("a", f"wafer valve row {n}", kind="table") for n in range(4)]
    elsewhere = Chunk(manufacturer="a", file="f.pdf", pdf_page=2, kind="text", section=None, text="wafer lug")
    found = Index([*rows, elsewhere], fake_embed).search("wafer", top_k=4, mode="keyword")
    assert sorted(h.chunk.pdf_page for h in found) == [1, 1, 2]


def test_text_chunks_on_one_page_are_never_held_back():
    sections = [chunk("a", f"wafer valve {n}") for n in range(4)] + [chunk("a", "other"), chunk("a", "text"), chunk("a", "more")]
    assert len(Index(sections, fake_embed).search("wafer", top_k=4, mode="keyword")) == 4


def test_rows_past_the_page_limit_do_not_take_up_places_in_a_ranking():
    rows = [chunk("a", f"row {n}", kind="table") for n in range(4)]
    index = Index([*rows, chunk("a", "wafer")], fake_embed)
    assert index.spread([0, 1, 2, 3, 4]) == [0, 1, 4]


def test_one_booklet_cannot_fill_every_place_of_a_maker_with_several():
    chunks = [chunk("a", f"gate valve materials {i}", file="check.pdf") for i in range(4)] + [chunk("a", "gate valve", file="gate.pdf")]
    files = [h.chunk.file for h in Index(chunks, fake_embed).search_many(["gate valve materials"], "a", top_k=4)]
    assert files.count("check.pdf") == 2 and "gate.pdf" in files
