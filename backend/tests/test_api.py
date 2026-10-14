import io

import pytest
from fastapi.testclient import TestClient
from test_report import ALIASES, BIG, SIZE, run  # noqa: F401

from app.main import create_app

PDF = b"%PDF-1.4 fake"


def fake_runner(run_id, tender_dir, category_dir, name, progress):
    assert [p.name for p in tender_dir.glob("*.pdf")] == ["bid.pdf"]
    return run([SIZE], {(0, "a"): [BIG]}).model_dump_json(), "model calls 0"


def failing_runner(run_id, tender_dir, category_dir, name, progress):
    raise RuntimeError("the model is down")


@pytest.fixture
def folders(tmp_path):
    (tmp_path / "categories" / "pumps" / "manufacturers" / "acme").mkdir(parents=True)
    (tmp_path / "categories" / "pumps" / "manufacturers" / "acme" / "a.pdf").write_bytes(PDF)
    return tmp_path / "categories", tmp_path / "runs"


def client(folders, runner=fake_runner):
    return TestClient(create_app(folders[0], folders[1], runner))


def upload(c, name="bid.pdf", data=PDF, category="pumps"):
    return c.post("/runs", data={"category": category}, files=[("files", (name, io.BytesIO(data), "application/pdf"))])


def test_categories_are_the_folders_that_hold_manufacturers(folders):
    assert client(folders).get("/categories").json() == [{"name": "pumps", "manufacturers": ["acme"], "documents": 1}]


def test_a_run_is_started_finished_and_its_report_can_be_read_both_ways(folders):
    c = client(folders)
    started = upload(c)
    assert started.status_code == 202 and started.json()["tender"] == "bid"
    run_id = started.json()["id"]
    assert c.get(f"/runs/{run_id}").json()["status"] == "done"
    assert c.get(f"/runs/{run_id}/report").json()["makers"][0]["compatibility"] == 100
    assert "How the compatibility is calculated" in c.get(f"/runs/{run_id}/report.md").text
    assert [r["id"] for r in c.get("/runs").json()] == [run_id]


def test_a_failed_run_says_why(folders):
    c = client(folders, failing_runner)
    run_id = upload(c).json()["id"]
    info = c.get(f"/runs/{run_id}").json()
    assert info["status"] == "failed" and "the model is down" in info["error"]
    assert c.get(f"/runs/{run_id}/report").status_code == 409


def test_only_pdfs_of_a_known_category_are_accepted(folders):
    c = client(folders)
    assert upload(c, "notes.txt", b"hello").status_code == 400
    assert upload(c, "fake.pdf", b"not a pdf").status_code == 400
    assert upload(c, category="valves").status_code == 404
    assert c.get("/runs").json() == []


def test_unknown_runs_are_not_found_and_deleting_removes_the_run(folders):
    c = client(folders)
    assert c.get("/runs/nope").status_code == 404
    run_id = upload(c).json()["id"]
    assert c.delete(f"/runs/{run_id}").status_code == 204 and c.get(f"/runs/{run_id}").status_code == 404


def test_runs_interrupted_by_a_restart_are_marked_failed(folders):
    c = client(folders)
    c.app.state.store.create("t", "pumps")
    restarted = TestClient(create_app(folders[0], folders[1], fake_runner))
    assert restarted.get("/runs").json()[0]["status"] == "failed"


def test_the_docs_page_describes_uploads_as_files(folders):
    schema = client(folders).get("/openapi.json").json()["components"]["schemas"]["Body_create_run_runs_post"]
    assert schema["properties"]["files"]["items"] == {"type": "string", "format": "binary"}


def test_a_manufacturers_document_can_be_opened_but_nothing_outside_the_documents(folders):
    c = client(folders)
    got = c.get("/categories/pumps/manufacturers/acme/documents/a.pdf")
    assert got.status_code == 200 and got.content == PDF and got.headers["content-type"] == "application/pdf"
    assert "inline" in got.headers["content-disposition"]
    for path in ("/categories/pumps/manufacturers/acme/documents/missing.pdf", "/categories/pumps/manufacturers/nobody/documents/a.pdf",
                 "/categories/other/manufacturers/acme/documents/a.pdf", "/categories/pumps/manufacturers/acme/documents/..%2F..%2Fsecret.pdf"):
        assert c.get(path).status_code == 404


def test_an_uploaded_tender_file_can_be_opened_by_its_run(folders):
    c = client(folders)
    run_id = upload(c).json()["id"]
    assert c.get(f"/runs/{run_id}/tender/bid.pdf").content == PDF
    assert c.get(f"/runs/{run_id}/tender/other.pdf").status_code == 404
    assert c.get("/runs/nope/tender/bid.pdf").status_code == 404
