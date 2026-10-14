import pymupdf

from app.services.ocr import render_page
from app.services.pdf_reader import MIN_DRAWINGS, read_pdf

DRAWN = "Size range 40 to 500 mm, pressure PN 16, body cast steel"


def pdf_with(path, shapes: int, text: str = ""):
    doc = pymupdf.open()
    page = doc.new_page()
    for n in range(shapes):
        page.draw_rect(pymupdf.Rect(10, 10 + n * 20, 100, 20 + n * 20))
    if text:
        page.insert_text((200, 100), text)
    doc.save(path)
    return path


def test_text_drawn_as_shapes_is_read_like_a_picture(tmp_path):
    page = read_pdf(pdf_with(tmp_path / "drawn.pdf", MIN_DRAWINGS + 5), lambda png: DRAWN).pages[0]
    assert page.needs_ocr and page.ocr and page.text == DRAWN


def test_a_blank_page_is_not_sent_to_the_reader(tmp_path):
    def fail(png):
        raise AssertionError("a blank page should not be read")

    page = read_pdf(pdf_with(tmp_path / "blank.pdf", 0), fail).pages[0]
    assert not page.needs_ocr and not page.ocr


def test_a_page_with_real_text_is_never_read_as_a_picture(tmp_path):
    def fail(png):
        raise AssertionError("a page with text should not be read")

    page = read_pdf(pdf_with(tmp_path / "text.pdf", MIN_DRAWINGS + 5, DRAWN), fail).pages[0]
    assert not page.needs_ocr and DRAWN in page.text


def test_pages_that_need_reading_keep_their_order_when_read_together(tmp_path):
    doc = pymupdf.open()
    for n in range(4):
        page = doc.new_page()
        for k in range(MIN_DRAWINGS + n + 1):  # a different number of shapes on each page tells the pictures apart
            page.draw_rect(pymupdf.Rect(10, 10 + k * 5, 100, 14 + k * 5))
    doc.save(tmp_path / "many.pdf")
    own_sizes = [len(render_page(page)) for page in pymupdf.open(tmp_path / "many.pdf")]
    pages = read_pdf(tmp_path / "many.pdf", lambda png: f"picture of {len(png)} bytes " * 3).pages
    assert [p.pdf_page for p in pages] == [1, 2, 3, 4]
    assert all(f"picture of {size} bytes" in p.text for p, size in zip(pages, own_sizes, strict=True))
