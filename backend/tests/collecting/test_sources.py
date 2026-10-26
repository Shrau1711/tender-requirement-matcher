from datetime import date

from app.categories.config import CATEGORIES_DIR
from app.collecting.download import save_pdf
from app.collecting.sources import known_hashes, record_source, unrecorded

PDF = b"%PDF-1.4 catalogue"


def maker_folder(root, category="pumps", maker="acme"):
    folder = root / category / "manufacturers" / maker
    folder.mkdir(parents=True)
    return folder


def test_a_saved_file_is_recorded_with_where_it_came_from_and_its_hash(tmp_path):
    folder = maker_folder(tmp_path)
    saved = save_pdf("https://m.com/a.pdf", "https://m.com/downloads", PDF, folder, known_hashes(folder), date(2026, 10, 19))
    record_source(folder, saved)
    lines = (folder / "crawl_sources.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "url,file,sha256,bytes,date_downloaded,found_on"
    assert lines[1].startswith("https://m.com/a.pdf,a.pdf,") and lines[1].endswith(",2026-10-19,https://m.com/downloads")
    assert known_hashes(folder) == {saved.sha256}  # so the next crawl does not save it again


def test_a_pdf_with_no_record_anywhere_is_listed(tmp_path):
    folder = maker_folder(tmp_path)
    for name in ("by_hand.pdf", "crawled.pdf", "unknown.pdf"):
        (folder / name).write_bytes(PDF)
    (tmp_path / "sources.csv").write_text("category,manufacturer,file\npumps,acme,by_hand.pdf\n", encoding="utf-8")
    record_source(folder, save_pdf("https://m.com/crawled.pdf", "x", PDF + b"2", tmp_path / "elsewhere", set()))
    assert [p.name for p in unrecorded(tmp_path)] == ["unknown.pdf"]


def test_every_shipped_manufacturer_document_has_its_source_recorded():
    assert unrecorded(CATEGORIES_DIR) == []
