"""How well one reading of a page agrees with another: used to judge a cheaper page reader against the model's saved transcriptions.

Numbers matter most in a catalogue (a rating, a size, a limit), so the main figure is how many of the reference's numbers the other reading also found.
"""
from __future__ import annotations

import re
from collections import Counter

NUMBER = re.compile(r"\d+(?:\.\d+)?")
WORD = re.compile(r"[a-z]{3,}")
GOOD_ENOUGH = 0.95  # a page whose numbers are read at least this well counts as read well


def numbers_in(text: str) -> Counter[str]:
    """Every number in the text, counted. Thousands commas are dropped so 1,000 and 1000 agree."""
    return Counter(NUMBER.findall(text.replace(",", "")))


def number_recall(reference: str, other: str) -> float | None:
    """The share of the reference's numbers that the other text also has (None when the reference has no numbers)."""
    wanted = numbers_in(reference)
    total = sum(wanted.values())
    if not total:
        return None
    return sum(min(count, numbers_in(other)[number]) for number, count in wanted.items()) / total


def word_recall(reference: str, other: str) -> float | None:
    """The share of the reference's distinct words (three letters or more) that the other text also has."""
    wanted = set(WORD.findall(reference.lower()))
    return len(wanted & set(WORD.findall(other.lower()))) / len(wanted) if wanted else None


def mean(values: list[float | None]) -> float | None:
    found = [v for v in values if v is not None]
    return sum(found) / len(found) if found else None


def confident_pages(pages: list[tuple[float, float | None]], threshold: float) -> tuple[int, float | None]:
    """From (reader's confidence, number recall) per page: how many pages the reader was at least this sure about, and how well it read their numbers.

    This answers whether the reader knows when it is wrong: if the sure pages are read well, only the unsure ones need the model.
    """
    sure = [recall for confidence, recall in pages if confidence >= threshold]
    return len(sure), mean(sure)
