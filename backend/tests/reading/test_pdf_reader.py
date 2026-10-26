import pymupdf

from app.reading.pdf_reader import read_pdf


def test_reads_pages_in_order(tmp_path):
    pdf = tmp_path / "t.pdf"
    doc = pymupdf.open()
    for text in ["first page text " * 5, "second page text " * 5]:
        doc.new_page().insert_text((72, 72), text)
    doc.save(pdf)

    result = read_pdf(pdf)

    assert result.n_pages == 2
    assert result.pages[0].pdf_page == 1
    assert "second" in result.pages[1].text
    assert not result.pages[0].needs_ocr