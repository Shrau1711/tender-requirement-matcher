"""Sending each item of a tender to a product category, so a tender that buys pumps and valves is matched against both.

First by words: an item whose title names exactly one category's product word ("Ball Valve 150 mm" says "valve") goes
there. Otherwise by the categories' own documents: the item's title is compared by meaning with every chunk of every
category, and the category whose closest chunks are most alike wins. Nothing here calls the model.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.categories.config import CATEGORIES_DIR, category_by_words, load_categories
from app.embedding.embed_cache import embed_cached
from app.retrieval.search import Embedder, Index

CLOSEST = 5  # chunks per category whose similarity to the title is averaged

IndexFor = Callable[[Path], Index]


def closeness(index: Index, title_vector: np.ndarray) -> float:
    """How alike a title is to a category's documents: the mean similarity of its CLOSEST chunks."""
    if index.vectors is None:
        return float("-inf")
    scores = np.sort(index.vectors @ title_vector)[::-1][:CLOSEST]
    return float(scores.mean())


def by_documents(titles: list[str], indexes: dict[str, Index], embed: Embedder = embed_cached) -> dict[str, str]:
    """Each title's category by the documents, with ties going to the category that comes first by name."""
    vectors = embed(titles)
    return {t: max(sorted(indexes), key=lambda name: closeness(indexes[name], v)) for t, v in zip(titles, vectors, strict=True)}


def route_items(titles: list[str], index_for: IndexFor, root: Path = CATEGORIES_DIR, embed: Embedder = embed_cached) -> dict[str, str]:
    """{item title: category}. The categories' documents are only read when the words do not decide."""
    routed, undecided = {}, []
    for title in dict.fromkeys(titles):
        found = category_by_words(title, root)
        if len(found) == 1:
            routed[title] = found[0]
        else:
            undecided.append(title)
    if undecided:
        indexes = {c.name: index_for(root / c.name) for c in load_categories(root)}
        routed |= by_documents(undecided, indexes, embed)
    return routed


def by_category(routed: dict[str, str]) -> dict[str, list[str]]:
    """{category: its item titles}, categories in name order and titles in tender order."""
    groups: dict[str, list[str]] = {}
    for title, category in routed.items():
        groups.setdefault(category, []).append(title)
    return dict(sorted(groups.items()))
