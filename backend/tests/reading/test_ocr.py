import pymupdf
from builders import CALLS, chunk_page, picture_only_pdf

from app.llm.llm import Reply
from app.llm.llm_cache import CachedLLM
from app.reading.ocr import reader_for
from app.reading.pdf_reader import lines_from_text, read_pdf


def test_lines_from_text_keeps_order_and_starts_a_block_at_each_blank_line():
    lines = lines_from_text("Size Range: 40 to 500 mm\nPN 16\n\nTesting: API 598")
    assert [l.text for l in lines] == ["Size Range: 40 to 500 mm", "PN 16", "Testing: API 598"]
    assert [l.block for l in lines] == [0, 0, 1]
    assert lines[0].y1 <= lines[1].y0


def test_a_line_marked_as_a_heading_is_bold_and_loses_its_marker():
    heading, body = lines_from_text("# Series 50/52 Butterfly Valves\nSize Range: 40 to 500 mm")
    assert (heading.text, heading.bold, body.bold) == ("Series 50/52 Butterfly Valves", True, False)


def test_a_picture_only_page_stays_unread_without_a_reader(tmp_path):
    page = read_pdf(picture_only_pdf(tmp_path / "scan.pdf")).pages[0]
    assert page.needs_ocr and not page.ocr and page.lines == []


def test_a_picture_only_page_is_read_by_the_reader_and_marked(tmp_path):
    seen = []
    page = read_pdf(picture_only_pdf(tmp_path / "scan.pdf"), lambda png: seen.append(png) or "Size Range: 40 to 500 mm").pages[0]
    assert seen and seen[0].startswith(b"\x89PNG")
    assert page.ocr and page.needs_ocr and page.n_chars > 0
    chunks = chunk_page(page, "delval", "scan.pdf")
    assert chunks and all(c.ocr for c in chunks) and "40 to 500 mm" in chunks[0].text


def test_a_page_with_its_own_text_is_never_sent_to_the_reader(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "A page with plenty of its own text, so no reading is needed.", fontsize=11)
    doc.save(tmp_path / "text.pdf")
    page = read_pdf(tmp_path / "text.pdf", lambda png: 1 / 0).pages[0]
    assert not page.ocr


class CountingModel:
    model, settings = "m", "s"

    def __init__(self):
        self.calls = 0

    def transcribe(self, png, prompt):
        self.calls += 1
        return Reply(text="read")


def test_the_same_picture_is_transcribed_only_once(tmp_path):
    inner = CountingModel()
    read = reader_for(CachedLLM(inner, tmp_path, max_calls=CALLS))
    assert (read(b"picture"), read(b"picture"), inner.calls) == ("read", "read", 1)
    read(b"another picture")
    assert inner.calls == 2