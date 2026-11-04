"""A free page reader that runs on this computer: EasyOCR, which reads English, Hindi, Marathi and many other languages.

Optional, so the app and its Docker image do not need it: pip install easyocr. That brings PyTorch (about 1 GB), and each
language's model is downloaded once, on first use. EasyOCR writes Devanagari digits (१६) as printed; they are turned into
0-9 so a number reads the same in every script.
"""
from __future__ import annotations

import threading
from functools import cache

from app.reading.ocr.model import ImageReader

DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
ONE_PAGE = threading.Lock()  # pages are read in parallel threads; one EasyOCR model reads one page at a time


def plain_digits(text: str) -> str:
    return text.translate(DIGITS)


@cache
def engine(langs: tuple[str, ...]):
    try:
        import easyocr  # imported here so the rest of the app never needs it
    except ImportError as missing:
        raise RuntimeError("OCR=easyocr needs EasyOCR: pip install easyocr") from missing
    return easyocr.Reader(list(langs), gpu=False, verbose=False)


def easyocr_reader(langs: list[str]) -> ImageReader:
    """Reads a page picture into blocks of text, with a blank line between blocks (as the model is asked to).
    The model is loaded on the first page, not before."""
    def read(png: bytes) -> str:
        with ONE_PAGE:
            blocks = engine(tuple(langs)).readtext(png, detail=0, paragraph=True)
        return "\n\n".join(plain_digits(block) for block in blocks)

    return read
