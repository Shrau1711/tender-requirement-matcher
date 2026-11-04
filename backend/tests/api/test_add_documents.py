"""POST /categories/{category}/documents: add a manufacturer's PDF, uploaded or fetched, from the web app."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.collecting.crawl import Page
from app.main import create_app

PDF = b"%PDF-1.4 catalogue"
HEADER = "category,manufacturer,file,document_type,source_url,document_year,date_downloaded,products_covered,notes\n"


@pytest.fixture
def root(tmp_path):
    (tmp_path / "categories" / "valves" / "manufacturers" / "ksb").mkdir(parents=True)
    (tmp_path / "categories" / "sources.csv").write_text(HEADER, encoding="utf-8")
    return tmp_path


def app_with(root, ingest=None, fetch=None):
    """The app with a recording ingest (no reading or model) and a fetcher that never touches the network."""
    calls = []
    fake = ingest or (lambda folder, maker, file: calls.append((folder.name, maker, file)) or 7)
    app = create_app(root / "categories", root / "runs", ingest=fake, fetch=fetch or (lambda url: None))
    return TestClient(app), calls


def rows(root):
    with (root / "categories" / "sources.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def upload(client, name="boax.pdf", data=PDF, **form):
    return client.post("/categories/valves/documents", data={"manufacturer": "ksb", **form},
                       files=[("file", (name, io.BytesIO(data), "application/pdf"))])


def test_an_uploaded_pdf_is_saved_recorded_and_made_searchable(root):
    client, calls = app_with(root)
    answer = upload(client, source="https://ksb.com/boax.pdf")
    assert answer.status_code == 201
    body = answer.json()
    assert (body["file"], body["source_url"], body["chunks"], body["problem"]) == ("boax.pdf", "https://ksb.com/boax.pdf", 7, None)
    assert (root / "categories/valves/manufacturers/ksb/boax.pdf").read_bytes() == PDF
    assert rows(root)[0]["date_downloaded"] == body["date_downloaded"] and calls == [("valves", "ksb", "boax.pdf")]
    assert client.get("/categories").json()[0]["documents"] == 1


def test_an_address_is_fetched_by_the_collector_and_recorded_as_the_source(root):
    asked = []
    client, _ = app_with(root, fetch=lambda url: asked.append(url) or Page(url, "application/pdf", PDF))
    answer = client.post("/categories/valves/documents", data={"manufacturer": "New-Maker", "url": " https://m.com/files/sheet.pdf "})
    assert answer.status_code == 201 and asked == ["https://m.com/files/sheet.pdf"]
    assert (root / "categories/valves/manufacturers/new-maker/sheet.pdf").exists()
    assert rows(root)[0]["source_url"] == "https://m.com/files/sheet.pdf"
    assert client.get("/categories").json()[0]["manufacturers"] == ["ksb", "new-maker"]


@pytest.mark.parametrize(("form", "files", "status", "says"), [
    ({"manufacturer": "ksb"}, None, 400, "one or the other"),
    ({"manufacturer": "ksb", "url": "https://m.com/a.pdf"}, ("a.pdf", PDF), 400, "one or the other"),
    ({"manufacturer": "../etc"}, ("a.pdf", PDF), 400, "lower-case letters"),
    ({"manufacturer": "ksb"}, ("a.pdf", b"not a pdf"), 400, "not a PDF"),
    ({"manufacturer": "ksb", "source": "a friend"}, ("a.pdf", PDF), 400, "web address"),
    ({"manufacturer": "ksb", "url": "https://m.com/a.pdf"}, None, 502, "did not answer"),
])
def test_what_is_refused_saves_and_records_nothing(root, form, files, status, says):
    client, calls = app_with(root)
    answer = client.post("/categories/valves/documents", data=form, files=[("file", (files[0], io.BytesIO(files[1]), "application/pdf"))] if files else None)
    assert answer.status_code == status and says in answer.json()["detail"]
    assert rows(root) == [] and calls == [] and not list(root.rglob("a.pdf"))


def test_an_unknown_category_and_a_second_copy_are_refused(root):
    client, _ = app_with(root)
    assert client.post("/categories/pipes/documents", data={"manufacturer": "ksb"}, files=[("file", ("a.pdf", io.BytesIO(PDF), "application/pdf"))]).status_code == 404
    assert upload(client).status_code == 201
    again = upload(client, name="copy.pdf")
    assert again.status_code == 409 and "already" in again.json()["detail"] and len(rows(root)) == 1


def test_when_reading_fails_the_file_stays_saved_and_the_person_is_told(root):
    def broken(folder, maker, file):
        raise RuntimeError("Stopped after 0 real model calls (limit 0).")

    client, _ = app_with(root, ingest=broken)
    body = upload(client).json()
    assert body["chunks"] is None and "limit 0" in body["problem"] and len(rows(root)) == 1
