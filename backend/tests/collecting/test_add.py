"""Adding one manufacturer document: the collector's code saves and records it, and the one ingest function makes it searchable."""
import csv
import hashlib
from datetime import date

import numpy as np
import pymupdf
import pytest
from builders import picture_only_pdf

from app.collecting.add import Refused, add_document, download, pdf_name
from app.collecting.crawl import Page
from app.collecting.sources import unrecorded
from app.pipeline import runner
from app.retrieval.retrievers import retriever
from app.vectorstore.ingest import ingest
from app.vectorstore.memory import MemoryStore

HEADER = "category,manufacturer,file,document_type,source_url,document_year,date_downloaded,products_covered,notes\n"


def text_pdf(words="Wafer butterfly valve, nominal pressure PN 16, sizes DN 50 to DN 600") -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), words, fontsize=11)
    return doc.tobytes()


VALVE, PUMP = text_pdf(), text_pdf("Centrifugal pump for clean water, head 50 m, flow 120 m3/h")  # made once: each save differs


@pytest.fixture
def root(tmp_path):
    (tmp_path / "valves" / "manufacturers" / "ksb").mkdir(parents=True)
    (tmp_path / "sources.csv").write_text(HEADER, encoding="utf-8")
    return tmp_path


def rows(root):
    with (root / "sources.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_an_upload_is_saved_and_recorded_with_its_source_and_date(root):
    row = add_document(root, "valves", "ksb", VALVE, "Boax B catalogue.pdf", "https://ksb.com/boax.pdf", date(2026, 11, 4))
    assert (root / "valves/manufacturers/ksb/Boax_B_catalogue.pdf").exists()
    assert rows(root) == [row] and (row["source_url"], row["date_downloaded"], row["notes"]) == ("https://ksb.com/boax.pdf", "2026-11-04", "")
    assert unrecorded(root) == []  # the test every shipped document passes


def test_without_a_source_the_line_says_so_and_a_new_manufacturer_gets_a_folder(root):
    row = add_document(root, "valves", "new-maker", VALVE, "sheet", "")
    assert (root / "valves/manufacturers/new-maker/sheet.pdf").exists() and row["notes"] == "uploaded in the web app; source not given"


def test_the_same_content_is_not_added_twice_even_under_another_name(root):
    (root / "valves/manufacturers/ksb/old.pdf").write_bytes(VALVE)  # collected by hand before
    with pytest.raises(Refused, match="already in ksb's folder") as refused:
        add_document(root, "valves", "ksb", VALVE, "copy.pdf")
    assert refused.value.status == 409 and rows(root) == []


@pytest.mark.parametrize(("category", "maker", "body", "status"), [
    ("pipes", "ksb", b"%PDF-1.4", 404), ("valves", "../ksb", b"%PDF-1.4", 400), ("valves", "KSB AG", b"%PDF-1.4", 400),
    ("valves", "ksb", b"<html>", 400),
])
def test_what_is_refused(root, category, maker, body, status):
    with pytest.raises(Refused) as refused:
        add_document(root, category, maker, body, "a.pdf")
    assert refused.value.status == status and not list(root.rglob("a.pdf"))


def test_a_download_goes_through_the_fetcher_and_must_be_a_pdf():
    asked = []
    fetch = lambda url: asked.append(url) or Page(url, "application/pdf", b"%PDF-1.4 x")
    assert download("https://m.com/a.pdf", fetch) == b"%PDF-1.4 x" and asked == ["https://m.com/a.pdf"]
    for url, fetcher, status in [("file:///etc/passwd", fetch, 400), ("https://m.com/a.pdf", lambda url: None, 502),
                                 ("https://m.com/page", lambda url: Page(url, "text/html", b"<html>"), 400)]:
        with pytest.raises(Refused) as refused:
            download(url, fetcher)
        assert refused.value.status == status


def test_a_name_always_ends_in_pdf():
    assert (pdf_name("https://m.com/download?id=3"), pdf_name("Data sheet.PDF")) == ("download.pdf", "Data_sheet.PDF")


def fake_embed(texts):
    rows = [np.frombuffer(hashlib.sha256(t.encode()).digest(), dtype=np.uint8).astype(np.float32) - 127.5 for t in texts]
    vectors = np.stack(rows) if rows else np.zeros((0, 32), dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@pytest.fixture
def store(monkeypatch):
    """add_to_search with a memory store and vectors made without a model."""
    memory = MemoryStore()
    monkeypatch.setattr(runner, "open_store", lambda: memory)
    monkeypatch.setattr(runner, "ingest", lambda folder, store, read: ingest(folder, store, read, embed=fake_embed))
    return memory


def test_an_added_document_is_searchable_through_the_one_ingest_function(root, store, monkeypatch):
    monkeypatch.setattr(runner, "make_llm", lambda: pytest.fail("a document with its own text needs no model"))
    add_document(root, "valves", "ksb", PUMP, "pump.pdf")
    add_document(root, "valves", "ksb", text_pdf("Gate valve with a cast iron body and a rising stem"), "gate.pdf")
    row = add_document(root, "valves", "ksb", VALVE, "boax.pdf")
    assert runner.add_to_search(root / "valves", "ksb", row["file"]) >= 1
    search = retriever(ingest(root / "valves", store, lambda png: "", embed=fake_embed), store, "valves", "keyword", fake_embed)
    assert search.search("nominal pressure PN 16", top_k=1)[0].chunk.file == "boax.pdf"


def test_a_scanned_page_is_read_by_the_same_page_reader_as_a_run(root, store, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(runner, "reader_for", lambda llm: lambda png: seen.append(llm) or "Size Range: 40 to 500 mm")
    monkeypatch.setattr(runner, "make_llm", lambda: "the model")
    row = add_document(root, "valves", "ksb", picture_only_pdf(tmp_path / "scan.pdf").read_bytes(), "scan.pdf")
    assert runner.add_to_search(root / "valves", "ksb", row["file"]) >= 1 and seen == ["the model"]
