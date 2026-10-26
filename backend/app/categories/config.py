"""Each category's own words and rules, read from data/categories/<name>/category.json.

    {
      "product_words": ["pump"],            # a tender item whose title says one of these belongs here
      "type_attributes": ["pump_type"],     # attribute names that say which kind of product it is
      "filler_words": [],                   # words that say nothing about which kind it is ("valve" in "gate valve")
      "extraction_rules": ["A duty point ..."]  # extra rules for reading a tender's rows, added to the shared ones
    }

Every field may be left out. The vocabulary is the union over all categories, so a tender that holds pumps and valves is
read with both, and the result does not depend on which category an item was sent to.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from app.config import path_setting

CATEGORIES_DIR = path_setting("CATEGORIES_DIR", Path(__file__).resolve().parents[3] / "data" / "categories")
CONFIG_FILE = "category.json"


class CategoryConfig(BaseModel):
    name: str
    product_words: list[str] = []
    type_attributes: list[str] = []
    filler_words: list[str] = []
    extraction_rules: list[str] = []


def category_dirs(root: Path) -> list[Path]:
    """Every category folder: one that holds a manufacturers/ folder, in name order."""
    return sorted(p for p in root.iterdir() if (p / "manufacturers").is_dir()) if root.is_dir() else []


def read_config(folder: Path) -> CategoryConfig:
    """The folder's category.json; the folder's name is the category's name. No file means no words or rules of its own."""
    file = folder / CONFIG_FILE
    fields = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
    return CategoryConfig(name=folder.name, **fields)


@cache
def load_categories(root: Path = CATEGORIES_DIR) -> tuple[CategoryConfig, ...]:
    """Every category's config, read once per process: a new category's words are used after a restart."""
    return tuple(read_config(folder) for folder in category_dirs(root))


def union(field: str, root: Path = CATEGORIES_DIR) -> list[str]:
    """One field of every category's config, in category order, without repeats."""
    return list(dict.fromkeys(value for config in load_categories(root) for value in getattr(config, field)))


def category_by_words(title: str, root: Path = CATEGORIES_DIR) -> list[str]:
    """The categories whose product words the title mentions, e.g. "BALL VALVE 150 mm" -> ["valves"]."""
    text = title.lower()
    return [c.name for c in load_categories(root) if any(word in text for word in c.product_words)]
