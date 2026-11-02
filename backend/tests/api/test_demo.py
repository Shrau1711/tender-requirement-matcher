import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.demo import REPLAY_ONLY, create_demo_app


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
