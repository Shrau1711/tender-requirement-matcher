from __future__ import annotations

import re
from functools import lru_cache

from app.chunking.base import Chunk
from app.extraction.atomize import AtomicRequirement
from app.vocabulary.roles import load_roles
from app.vocabulary.words import kind_words, singular

ENOUGH = 0.6  # a chunk is a candidate when it says this share of the words the requirement is made of
NUMBER = re.compile(r"\d+(?:\.\d+)?")


@lru_cache(maxsize=None)
def words_in(text: str) -> tuple[frozenset[str], str]:
    """The meaningful words and numbers a passage says, and the same words as one string for quick substring checks.

    Remembered, because the same passages are scanned for every requirement.
    """
    words = frozenset(kind_words(text) | set(NUMBER.findall(text)))
    return words, " ".join(words)


def words_asked(req: AtomicRequirement) -> set[str]:
    """The words a passage would use if it answered the requirement: the attribute's name and the wanted values, without boilerplate."""
    skip = {singular(w) for w in load_roles()["generic"]}
    return (kind_words(req.attribute) | {w for v in req.values for w in kind_words(v)}) - skip


def numbers_asked(req: AtomicRequirement) -> set[str]:
    return {n for v in req.values for n in NUMBER.findall(v)}


def share_of(wanted: set[str], numbers: set[str], chunk: Chunk) -> float:
    """How much of the wanted words the chunk says: 0 to 1. A wanted number that is absent from the chunk rules it out."""
    have, joined = words_in(chunk.text)
    if not wanted or not numbers <= have:
        return 0.0
    return sum(w in have or (len(w) >= 4 and w in joined) for w in wanted) / len(wanted)  # "line" is said by "inline"


def share_said(req: AtomicRequirement, chunk: Chunk) -> float:
    """How much of what the requirement asks for the chunk says: 0 to 1."""
    return share_of(words_asked(req), numbers_asked(req), chunk)


def candidates(req: AtomicRequirement, chunks: list[Chunk], limit: int = 3) -> list[Chunk]:
    """Chunks anywhere in a manufacturer's documents that say the words and numbers the requirement is made of, best first.

    A plain scan with no ranking by meaning, so it finds a passage the search ranked low because it was worded unexpectedly.
    """
    wanted, numbers = words_asked(req), numbers_asked(req)
    scored = [(share_of(wanted, numbers, c), -len(c.text), c) for c in chunks]
    return [c for s, _, c in sorted(scored, key=lambda t: (t[0], t[1]), reverse=True)[:limit] if s >= ENOUGH]
