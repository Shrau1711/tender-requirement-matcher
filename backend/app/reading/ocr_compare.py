"""How well one reading of a page agrees with another: used to judge a cheaper page reader against the model's saved transcriptions.

Numbers matter most in a catalogue (a rating, a size, a limit), so the main figure is how many of the reference's numbers the other reading also found.
"""
from __future__ import annotations

import re
from collections import Counter

NUMBER = re.compile(r"\d+(?:\.\d+)?")
WORD = re.compile(r"[a-z]{3,}")


def numbers_in(text: str) -> Counter[str]:
    """Every number in the text, counted. Thousands commas are dropped so 1,000 and 1000 agree."""
    return Counter(NUMBER.findall(text.replace(",", "")))


def number_hits(reference: str, other: str) -> tuple[int, int]:
    """(how many of the reference's numbers the other text also has, how many the reference has). A repeated number must be found as often."""
    wanted, got = numbers_in(reference), numbers_in(other)
    return sum(min(count, got[number]) for number, count in wanted.items()), sum(wanted.values())


def number_recall(reference: str, other: str) -> float | None:
    """The share of the reference's numbers that the other text also has (None when the reference has no numbers)."""
    found, total = number_hits(reference, other)
    return found / total if total else None


def pooled_recall(pages: list[tuple[int, int]]) -> float | None:
    """From (found, total) per page: numbers found over all pages together, so a page with fifty numbers counts fifty times as much as a page with one (a page number)."""
    total = sum(t for _, t in pages)
    return sum(f for f, _ in pages) / total if total else None


def word_recall(reference: str, other: str) -> float | None:
    """The share of the reference's distinct words (three letters or more) that the other text also has."""
    wanted = set(WORD.findall(reference.lower()))
    return len(wanted & set(WORD.findall(other.lower()))) / len(wanted) if wanted else None


def mean(values: list[float | None]) -> float | None:
    found = [v for v in values if v is not None]
    return sum(found) / len(found) if found else None


def confident_pages(pages: list[tuple[float, int, int]], threshold: float) -> tuple[int, float | None]:
    """From (reader's confidence, numbers found, numbers there) per page: how many pages the reader was at least this sure about, and how well it read their numbers.

    This answers whether the reader knows when it is wrong: if the sure pages are read well, only the unsure ones need the model.
    """
    sure = [(found, total) for confidence, found, total in pages if confidence >= threshold]
    return len(sure), pooled_recall(sure)
