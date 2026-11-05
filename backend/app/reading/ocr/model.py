"""The default page reader: the language model, asked to transcribe a picture of the page. Each page is a paid call
(answers are cached by picture and prompt)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import pymupdf

from app.llm.llm import Reply

OCR_DPI = 200  # sharp enough for the small print of a catalogue table

PROMPT = (
    "Transcribe all the text on this page exactly as printed, from top to bottom. "
    "Keep each printed line on its own line and leave a blank line between separate blocks of text. "
    "Write each table row on one line as 'Column heading: value; Column heading: value', repeating the printed column headings (with their units) in every row. "
    "Start each heading or title line (large or bold text that names a product, a product range or a section) with '# '. "
    "Do not summarise, correct, convert or interpret anything. Leave out what you cannot read instead of guessing. "
    "Reply with the transcribed text only."
)

MIN_ROW_CELLS = 3  # a line with this many "Heading: value" cells, separated by "; ", is a table row

ImageReader = Callable[[bytes], str]  # a page picture (PNG) in, the text printed on it out


class Transcriber(Protocol):
    def transcribe(self, png: bytes, prompt: str) -> Reply: ...


def is_table_row(text: str) -> bool:
    """A line the reader wrote as a table row (see PROMPT): "Valve Size DN: 125; B: 56; Weight: 6.3"."""
    return text.count("; ") >= MIN_ROW_CELLS - 1


def render_page(page: pymupdf.Page) -> bytes:
    return page.get_pixmap(dpi=OCR_DPI).tobytes("png")


def prompt_for(names: list[str]) -> str:
    """PROMPT, unchanged for English, so every saved transcription still matches. Other languages add one sentence."""
    others = [n for n in names if n != "English"]
    return PROMPT if not others else f"{PROMPT} The page may be printed in {' or '.join(others)}: write that text in its own script."


def model_reader(llm: Transcriber, names: list[str] | None = None) -> ImageReader:
    """The model, asked to transcribe. names are the languages to expect, e.g. ["English", "Hindi"]."""
    prompt = prompt_for(names or ["English"])
    return lambda png: llm.transcribe(png, prompt).text