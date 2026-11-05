"""EasyOCR on small pictures made here, with text in Hindi, Marathi and English. Skipped unless EasyOCR and its English and
Devanagari models are on this computer (pip install easyocr; the models download on first use)."""
from pathlib import Path

import pymupdf
import pytest

from app.reading.ocr import reader_for
from app.reading.pdf_reader import read_pdf

MODELS = Path.home() / ".EasyOCR" / "model"
pytest.importorskip("easyocr")
pytestmark = pytest.mark.skipif(not (MODELS / "devanagari.pth").exists(), reason="EasyOCR's Devanagari model is not downloaded")

LINES = {"hi": "दबाव रेटिंग 16 बार", "mr": "पाण्याचा पंप 50 मिमी", "en": "Pressure rating PN 16"}


def picture(lines: list[str], width=400) -> bytes:
    """A PNG of the lines, typeset with proper Devanagari shaping (MuPDF's HTML layout and its own Noto fonts)."""
    page = pymupdf.open().new_page(width=width, height=40 + 50 * len(lines))
    page.insert_htmlbox(page.rect + (10, 10, -10, -10), "".join(f"<p style='font-size:22px'>{line}</p>" for line in lines))
    return page.get_pixmap(dpi=150).tobytes("png")


@pytest.fixture(scope="module")
def read():
    return reader_for(None, "easyocr", "en,hi,mr")


@pytest.mark.parametrize("language", list(LINES))
def test_each_language_is_read_word_for_word(read, language):
    assert read(picture([LINES[language]])).split() == LINES[language].split()


def test_a_scanned_page_in_three_languages_is_read_into_the_document(read, tmp_path):
    scan = pymupdf.open()
    scan.new_page(width=400, height=200).insert_image(pymupdf.Rect(0, 0, 400, 200), stream=picture(list(LINES.values())))
    scan.save(tmp_path / "scan.pdf")
    page = read_pdf(tmp_path / "scan.pdf", read).pages[0]
    assert page.ocr and page.text.split("\n\n") == list(LINES.values())
