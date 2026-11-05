import numpy as np

from app.chunking.base import maker
from app.chunking.router import CHUNKER, choose
from app.chunking.strategies.semantic import Semantic, likeness, pieces
from app.reading.pdf_reader import Line, PageRecord, ReadDocument

TOPICS = {"pressure": [1.0, 0.0, 0.0], "material": [0.0, 1.0, 0.0], "size": [0.6, 0.0, 0.8]}


def topic_embed(texts):
    """A fake embedder: a text's vector is its topic's, so two blocks on one topic are alike and two on different topics are not."""
    asked.extend(texts)
    return np.array([next(v for word, v in TOPICS.items() if word in t.lower()) for t in texts])


asked: list[str] = []


def line(text, block, y0):
    return Line(text=text, x0=0, y0=y0, x1=200, y1=y0 + 9, size=10, bold=False, block=block)


def page(texts, number=1) -> PageRecord:
    lines = [line(t, i, 20 * i) for i, t in enumerate(texts)]
    text = "\n".join(texts)
    return PageRecord(pdf_page=number, text=text, n_chars=len(text), n_images=0, needs_ocr=False, lines=lines)


def chunk(pages):
    return Semantic(topic_embed).chunk(pages, maker("ksb", "k.pdf"))


def test_blocks_on_one_topic_stay_together_and_a_change_of_topic_is_cut():
    texts = ["Pressure PN 16", "Max pressure 16 bar", "Test pressure 24 bar", "Material: body cast iron", "Material: disc bronze"]
    chunks = chunk([page(texts)])
    assert [c.text for c in chunks] == ["Pressure PN 16\nMax pressure 16 bar\nTest pressure 24 bar", "Material: body cast iron\nMaterial: disc bronze"]
    assert all(c.kind == "text" and c.pdf_page == 1 and c.manufacturer == "ksb" for c in chunks)


def test_a_chunk_never_spans_two_pages():
    chunks = chunk([page(["Pressure PN 16", "Material: cast iron"], 1), page(["Max pressure 16 bar", "Size DN 50"], 2)])
    assert {c.pdf_page for c in chunks} == {1, 2}
    assert all(len({c.pdf_page}) == 1 for c in chunks)


def test_the_cut_is_judged_against_the_document_itself():
    # Pressure then size is a smaller change (0.6 alike) than size then material (0 alike): with few changes in the document,
    # only the least alike neighbours are cut.
    texts = ["Pressure PN 16", "Pressure PN 25", "Size DN 50", "Size DN 80", "Material: cast iron", "Material: bronze"]
    alike = likeness([texts], topic_embed(texts))
    assert alike[0] is None and alike[1] == 1.0 and alike[2] == 0.6
    assert len(chunk([page(texts)])) >= 2


def test_a_chunk_is_cut_before_it_grows_too_big():
    texts = [f"Pressure row {i} " + "x" * 300 for i in range(6)]
    chunks = chunk([page(texts)])
    assert len(chunks) > 1 and all(len(c.text) <= 1000 for c in chunks)


def test_a_page_read_from_a_picture_is_split_into_its_paragraphs():
    picture = PageRecord(pdf_page=3, text="Pressure PN 16\n\nMaterial: cast iron", n_chars=34, n_images=1, needs_ocr=True, lines=[])
    assert pieces(picture) == ["Pressure PN 16", "Material: cast iron"]


def test_every_block_of_a_document_is_embedded_in_one_go():
    asked.clear()
    chunk([page(["Pressure PN 16", "Material: cast iron"], 1), page(["Size DN 50"], 2)])
    assert asked == ["Pressure PN 16", "Material: cast iron", "Size DN 50"]


def test_an_empty_document_has_no_chunks():
    assert chunk([page([])]) == []


def test_semantic_is_never_the_default_nor_picked_by_the_router():
    assert CHUNKER == "table_rows"
    text = ["Pressure PN 16 and some running text about the valve body here"] * 12
    doc = ReadDocument(path="x/k.pdf", sha256="", n_pages=1, pages=[page(text)])
    assert choose(doc)[0] != "semantic"
