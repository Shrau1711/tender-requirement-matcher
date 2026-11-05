"""The OCR and OCR_LANGS settings: the model stays the default with its prompt unchanged, and EasyOCR is one line beside it."""
import sys

import pytest

from app.llm.llm import Reply
from app.reading.ocr import PROMPT, local, reader_for, reader_setting
from app.reading.ocr.readers import READERS, languages
from app.vectorstore.ingest import settings_for


class Model:
    def __init__(self):
        self.prompts = []

    def transcribe(self, png, prompt):
        self.prompts.append(prompt)
        return Reply(text="read")


def test_the_default_reader_is_the_model_with_the_prompt_unchanged():
    model = Model()
    assert reader_for(model)(b"page") == "read"
    assert model.prompts == [PROMPT]  # the cache key of every saved transcription


def test_other_languages_add_one_sentence_to_the_model_prompt():
    model = Model()
    reader_for(model, "model", "en,hi,mr")(b"page")
    assert model.prompts[0].startswith(PROMPT) and model.prompts[0].endswith("printed in Hindi or Marathi: write that text in its own script.")


def test_unknown_readers_and_languages_are_refused():
    with pytest.raises(ValueError, match="Unknown page reader"):
        reader_for(Model(), "magic")
    with pytest.raises(ValueError, match="Unknown OCR language xx"):
        languages("en,xx")
    assert languages(" EN , hi ") == ["en", "hi"] and languages("") == ["en"]


def test_easyocr_loads_nothing_until_a_page_is_read_and_writes_plain_digits(monkeypatch):
    seen = []

    class Engine:
        def readtext(self, png, detail, paragraph):
            return ["दबाव रेटिंग १६ बार", "PN 1६"]

    monkeypatch.setattr(local, "engine", lambda langs: seen.append(langs) or Engine())
    read = reader_for(None, "easyocr", "en,hi,mr")
    assert seen == []
    assert read(b"page") == "दबाव रेटिंग 16 बार\n\nPN 16"
    assert seen == [("en", "hi", "mr")]


def test_easyocr_missing_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "easyocr", None)  # import fails as if it were not installed
    local.engine.cache_clear()
    with pytest.raises(RuntimeError, match="pip install easyocr"):
        reader_for(None, "easyocr")(b"page")
    local.engine.cache_clear()


def test_the_store_settings_name_the_reader_only_when_it_is_not_the_default():
    assert reader_setting() == "" and reader_setting("model", "en") == ""
    assert ";ocr=" not in settings_for("table_rows", True)  # files stored before still match
    assert reader_setting("easyocr", "en,hi") == "easyocr:en,hi" and reader_setting("model", "hi") == "model:hi"


def test_a_new_reader_is_one_line(monkeypatch):
    monkeypatch.setitem(READERS, "upper", lambda llm, codes: lambda png: png.decode().upper())
    assert reader_for(None, "upper")(b"pn 16") == "PN 16"
