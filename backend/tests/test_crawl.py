import threading
from datetime import date
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

from app.services.crawl import (
    Page,
    allowed_by,
    crawl,
    is_pdf,
    links_on,
    same_site,
    wanted,
)
from app.services.download import file_name, polite_fetcher, save_pdf

PDF = b"%PDF-1.4 fake catalogue"


def site(pages: dict[str, str]):
    def fetch(url: str) -> Page | None:
        return Page(url, "text/html", pages[url].encode()) if url in pages else None
    return fetch


def test_links_are_absolute_and_lose_fragments():
    html = '<a href="/a.pdf#page=2">x</a><a href="b.html">y</a><a href="mailto:me@x.com">z</a>'
    assert links_on(html, "https://m.com/dir/index.html") == ["https://m.com/a.pdf", "https://m.com/dir/b.html"]


def test_pdf_site_and_keyword_rules():
    assert is_pdf("https://m.com/x/Cat.PDF?v=2") and not is_pdf("https://m.com/x.html")
    assert same_site("https://www.m.com/a", "https://m.com/b") and not same_site("https://other.com", "https://m.com")
    assert wanted("https://m.com/databooklet.pdf", ["databooklet"], ["price"])
    assert not wanted("https://m.com/price-list.pdf", [], ["price"])
    assert not wanted("https://m.com/other.pdf", ["databooklet"], [])


def test_robots_rules_are_obeyed_and_a_missing_file_allows_everything():
    robots = "User-agent: *\nDisallow: /private/"
    assert not allowed_by(robots, "https://m.com/private/a.pdf", "bot")
    assert allowed_by(robots, "https://m.com/public/a.pdf", "bot")
    assert allowed_by(None, "https://m.com/private/a.pdf", "bot")


def test_crawl_follows_pages_on_the_site_to_the_depth_and_finds_each_pdf_once():
    pages = {
        "https://m.com/": '<a href="/pumps">p</a><a href="https://other.com/x">o</a><a href="/one.pdf">1</a>',
        "https://m.com/pumps": '<a href="/one.pdf">again</a><a href="/two.pdf">2</a><a href="/deep">d</a>',
        "https://m.com/deep": '<a href="/three.pdf">3</a>',
        "https://other.com/x": '<a href="/leak.pdf">no</a>',
    }
    found = list(crawl(["https://m.com/"], site(pages), [], [], depth=1, max_pdfs=10))
    assert [f.pdf for f in found] == ["https://m.com/one.pdf", "https://m.com/two.pdf"]
    assert found[1].found_on == "https://m.com/pumps"


def test_crawl_stops_at_the_pdf_limit():
    pages = {"https://m.com/": "".join(f'<a href="/{n}.pdf">x</a>' for n in range(5))}
    assert len(list(crawl(["https://m.com/"], site(pages), [], [], depth=1, max_pdfs=3))) == 3


def test_file_names_are_safe():
    assert file_name("https://m.com/a/CR%20databooklet 50Hz.pdf") == "CR_databooklet_50Hz.pdf"
    assert file_name("https://m.com/") == "catalogue.pdf"


def test_save_writes_a_pdf_once_and_records_its_source(tmp_path):
    known: set[str] = set()
    saved = save_pdf("https://m.com/a.pdf", "https://m.com/", PDF, tmp_path, known, date(2026, 10, 19))
    assert saved.file == "a.pdf" and saved.date_downloaded == "2026-10-19" and (tmp_path / "a.pdf").read_bytes() == PDF
    assert save_pdf("https://m.com/copy.pdf", "https://m.com/", PDF, tmp_path, known) is None  # same content
    assert save_pdf("https://m.com/page.pdf", "https://m.com/", b"<html>not a pdf", tmp_path, known) is None


def test_same_name_with_new_content_keeps_both(tmp_path):
    known: set[str] = set()
    save_pdf("https://m.com/a.pdf", "x", PDF, tmp_path, known)
    second = save_pdf("https://m.com/a.pdf", "x", PDF + b"v2", tmp_path, known)
    assert second.file != "a.pdf" and len(list(tmp_path.glob("*.pdf"))) == 2


def test_polite_fetcher_reads_a_real_local_server_and_waits_between_requests(tmp_path):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    (tmp_path / "index.html").write_text('<a href="cat.pdf">c</a>')
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "secret.html").write_text("no")
    server = HTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    waits: list[float] = []
    fetch = polite_fetcher(delay=0.5, sleep=waits.append)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page = fetch(f"{base}/index.html")
        assert page and "html" in page.content_type and b"cat.pdf" in page.body
        assert fetch(f"{base}/private/secret.html") is None  # robots.txt says no
        assert fetch(f"{base}/missing.html") is None
    finally:
        server.shutdown()
    assert waits == [0.5, 0.5]  # the refused address cost no request
