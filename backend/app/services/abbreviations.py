from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ABBREVIATIONS_FILE = Path(__file__).resolve().parents[2] / "config" / "abbreviations.json"

Groups = dict[str, list[str]]  # short form -> the ways it is written out, e.g. "BW" -> ["butt weld", ...]


@lru_cache
def load_abbreviations(path: Path = ABBREVIATIONS_FILE) -> Groups:
    return json.loads(path.read_text(encoding="utf-8"))


def spelling(term: str) -> re.Pattern:
    """The term as a whole word: "SS" is found in "SS 304" but not in "SS304" or "glass"."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE)


def alternatives(text: str, groups: Groups | None = None) -> list[str]:
    """The text written the other ways: "end connection BW" -> "end connection butt weld", ... A catalogue may use either form."""
    groups = load_abbreviations() if groups is None else groups
    found = []
    for short, longer in groups.items():
        terms = [short, *longer]
        for term in terms:
            if spelling(term).search(text):
                found += [spelling(term).sub(lambda _, other=other: other, text) for other in terms if other != term]
    return list(dict.fromkeys(found))


def canonical(text: str, groups: Groups | None = None) -> str:
    """The text with every written-out form replaced by its short form, so "butt weld ends" and "BW" read the same.

    Each form is replaced as a whole, so "butt weld" and "socket weld" do not look alike just because both say "weld".
    """
    groups = load_abbreviations() if groups is None else groups
    text = re.sub(r"[-_]", " ", text.lower())
    for short, longer in groups.items():
        for term in sorted(longer, key=len, reverse=True):
            text = spelling(term).sub(short.lower(), text)
    return text
