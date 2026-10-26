from __future__ import annotations

import re
from pathlib import Path

from app.categories.config import CATEGORIES_DIR, category_by_words

MAX_PRODUCT = 200


def label_value(lines: list[str], label: str) -> str:
    """The line after the line that carries the label (a GeM bid page prints the Hindi and English label together)."""
    for i, line in enumerate(lines):
        if label.lower() in line.lower():
            return lines[i + 1].strip() if i + 1 < len(lines) else ""
    return ""


def item_category(lines: list[str]) -> str:
    """What is being bought: the lines after the "Item Category" label, up to the next label (those carry Hindi)."""
    for i, line in enumerate(lines):
        if "item category" in line.lower():
            found = []
            for text in lines[i + 1:i + 12]:
                if "GeMARPTS" in text or not text.isascii():
                    break
                found.append(text.strip())
            return " ".join(found)
    return ""


def category_of(product: str, root: Path = CATEGORIES_DIR) -> str:
    """The first category whose product word the product mentions, e.g. "pump" -> pumps (see category.json). Blank when none."""
    found = category_by_words(product, root)
    return found[0] if found else ""


def parse_bid_details(text: str) -> dict[str, str]:
    """The buyer and the product from the first page of a GeM bid document. Fields it cannot find are left empty."""
    lines = [line for line in text.splitlines() if line.strip()]
    product = item_category(lines)
    if len(product) > MAX_PRODUCT:
        product = product[:MAX_PRODUCT].rsplit(" ", 1)[0] + " ..."
    return {
        "buyer": label_value(lines, "Organisation Name"),
        "product": re.sub(r"\s+", " ", product),
        "category": category_of(product),
    }
