from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.abbreviations import canonical
from app.services.search import tokenize

FILLER = {"valve", "type", "body", "end", "ends", "connection"}  # words that say nothing about which kind it is
LINKING = {"a", "an", "and", "as", "by", "for", "in", "is", "of", "on", "or", "per", "the", "to", "with", "equivalent"}  # words that never say which kind it is


def singular(word: str) -> str:
    return word[:-1] if word.endswith("s") and len(word) > 3 else word


def kind_words(text: str) -> set[str]:
    return {singular(w) for w in tokenize(canonical(text))} - FILLER - LINKING


def is_stated(word: str, have: set[str]) -> bool:
    """True when the word is among the stated ones, or is part of a longer stated word ("line" in "inline", "seal" in "sealing")."""
    return word in have or (len(word) >= 4 and any(h.startswith(word) or h.endswith(word) for h in have))


NUMBER_WORDS_FILE = Path(__file__).resolve().parents[2] / "config" / "number_words.json"
CEILING = re.compile(r"\bmax(?:imum)?\b|\bup\s*to\b|\bupto\b", re.IGNORECASE)
FLOOR = re.compile(r"\bmin(?:imum)?\b", re.IGNORECASE)


@lru_cache
def number_words(path: Path = NUMBER_WORDS_FILE) -> dict[str, int]:
    """Numbers written as words ("Three Phase", "Single phase"), as data."""
    return json.loads(path.read_text(encoding="utf-8"))


def spoken_numbers(text: str) -> list[float]:
    """The numbers a statement gives in words, in the order they appear."""
    words = number_words()
    return [float(words[w]) for w in re.findall(r"[a-z]+", text.lower()) if w in words]


def shape_of(shape: str, text: str) -> str:
    """A lone figure printed after "Max." or "Min." is a limit, not an exact value."""
    if shape != "single":
        return shape
    top, bottom = bool(CEILING.search(text)), bool(FLOOR.search(text))
    return "up_to" if top and not bottom else "at_least" if bottom and not top else shape
