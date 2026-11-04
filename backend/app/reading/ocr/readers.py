"""Which page reader reads the pictures of pages (scans and drawn text), chosen by the OCR setting, and in which
languages, chosen by OCR_LANGS (codes separated by commas, e.g. en,hi,mr).

- model (the default): the language model transcribes each page. A paid call per page, cached.
- easyocr: EasyOCR on this computer. Free, no key, but its readings have not been checked against real catalogues.
Adding a reader is one line in READERS: a function from (model, language codes) to an ImageReader.
"""
from __future__ import annotations

from collections.abc import Callable

from app.config import text_setting
from app.reading.ocr.local import easyocr_reader
from app.reading.ocr.model import ImageReader, Transcriber, model_reader

OCR = text_setting("OCR", "model")
OCR_LANGS = text_setting("OCR_LANGS", "en")
DEFAULT = ("model", "en")
LANGUAGES = {"en": "English", "hi": "Hindi", "mr": "Marathi"}  # codes as EasyOCR names them; both readers accept these

READERS: dict[str, Callable[[Transcriber, list[str]], ImageReader]] = {
    "model": lambda llm, codes: model_reader(llm, [LANGUAGES[c] for c in codes]),
    "easyocr": lambda llm, codes: easyocr_reader(codes),
}


def languages(setting: str = OCR_LANGS) -> list[str]:
    codes = [c.strip().lower() for c in setting.split(",") if c.strip()] or ["en"]
    unknown = [c for c in codes if c not in LANGUAGES]
    if unknown:
        raise ValueError(f"Unknown OCR language {', '.join(unknown)}. Choose from {', '.join(LANGUAGES)}")
    return codes


def reader_for(llm: Transcriber, name: str = OCR, langs: str = OCR_LANGS) -> ImageReader:
    """The page reader that scripts and jobs hand to the PDF reader."""
    if name not in READERS:
        raise ValueError(f"Unknown page reader {name!r}. Choose from {', '.join(READERS)}")
    return READERS[name](llm, languages(langs))


def reader_setting(name: str = OCR, langs: str = OCR_LANGS) -> str:
    """Empty for the default reader; otherwise its name and languages, so a store never mixes two readers' chunks."""
    return "" if (name, langs) == DEFAULT else f"{name}:{','.join(languages(langs))}"
