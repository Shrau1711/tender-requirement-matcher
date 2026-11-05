import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.demo import KEPT, REPLAY_ONLY, create_demo_app
from app.main import create_app


def demo(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    page = tmp_path / "frontend"
    page.mkdir()
    (page / "index.html").write_text("<h1>Tender matcher</h1>", encoding="utf-8")
    return TestClient(create_demo_app(page))


def test_an_upload_is_refused_with_the_plain_message(tmp_path, monkeypatch):
    client = demo(tmp_path, monkeypatch)
    answer = client.post("/runs", files={"files": ("bid.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert answer.status_code == 403
    assert answer.json() == {"detail": REPLAY_ONLY}
    assert client.get("/runs").json() == []  # no run was started


def test_adding_a_manufacturer_document_is_refused_with_the_same_message(tmp_path, monkeypatch):
    client = demo(tmp_path, monkeypatch)
    answer = client.post("/categories/valves/documents", data={"manufacturer": "ksb"},
                         files={"file": ("demo-visitor.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert (answer.status_code, answer.json()) == (403, {"detail": REPLAY_ONLY})
    assert not list(client.app.state.categories_dir.rglob("demo-visitor.pdf"))  # nothing was saved


def test_the_page_and_the_api_share_one_port(tmp_path, monkeypatch):
    client = demo(tmp_path, monkeypatch)
    assert "Tender matcher" in client.get("/").text
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/runs").status_code == 200  # API routes are matched before the page


def test_the_demo_image_lets_in_exactly_the_sample_tenders():
    root = Path(__file__).resolve().parents[3]
    lines = (root / "Dockerfile.demo.dockerignore").read_text(encoding="utf-8").splitlines()
    let_in = {line[1:].removeprefix("data/tenders/") for line in lines if line.startswith("!data/tenders/")}
    samples = json.loads((root / "data" / "demo_runs" / "runs.json").read_text(encoding="utf-8"))
    assert let_in == {s["folder"] for s in samples}
    assert "data/tenders/*/*" in lines


def test_a_sample_run_cannot_be_deleted_or_renamed(tmp_path, monkeypatch):
    client = demo(tmp_path, monkeypatch)
    run = client.app.state.store.create("GeM-Bidding-1", "valves")
    for answer in (client.delete(f"/runs/{run.id}"), client.patch(f"/runs/{run.id}", json={"name": "mine now"})):
        assert answer.status_code == 403
        assert answer.json() == {"detail": KEPT}
    assert client.get(f"/runs/{run.id}").json()["tender"] == "GeM-Bidding-1"  # still there, under its own name
    assert client.put(f"/runs/{run.id}/reviews", json={"items": []}).status_code == 200  # decisions can still be saved


def test_the_normal_app_still_deletes_and_renames(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    client = TestClient(create_app())
    run = client.app.state.store.create("GeM-Bidding-1", "valves")
    assert client.patch(f"/runs/{run.id}", json={"name": "renamed"}).json()["tender"] == "renamed"
    assert client.delete(f"/runs/{run.id}").status_code == 204
    assert client.get(f"/runs/{run.id}").status_code == 404
