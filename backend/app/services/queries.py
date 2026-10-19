from __future__ import annotations

import json
import tokenize
from pathlib import Path

import pint

from app.services.abbreviations import Groups, alternatives, load_abbreviations
from app.services.atomize import AtomicRequirement
from app.services.measure import spelled
from app.services.roles import load_roles

UNIT_VIEWS_FILE = Path(__file__).resolve().parents[2] / "config" / "units.json"
ureg = pint.UnitRegistry()


def load_unit_views(path: Path = UNIT_VIEWS_FILE) -> dict[str, list[dict]]:
    return json.loads(path.read_text(encoding="utf-8"))


def number(x: float) -> str:
    return f"{x:.6g}"  # 16.000000000000004 -> 16


def has_dimension(quantity: pint.Quantity, dimension: str) -> bool:
    """Whether the quantity measures that dimension. A unit pint cannot classify (a decibel level, say) measures none of them."""
    try:
        return quantity.check(dimension)
    except (AttributeError, pint.errors.PintError):
        return False


def unit_views(attribute: str, value: str, unit: str, views: dict[str, list[dict]]) -> list[str]:
    """The same quantity written the other ways brochures write it, e.g. 1.6 MPa -> 16 bar, PN 16."""
    if not spelled(unit):
        return []  # a bare number has no other spellings
    try:
        quantity = ureg.Quantity(float(value), spelled(unit))  # "LPS" is a flow to us, though pint does not know it
    except (ValueError, pint.errors.PintError, tokenize.TokenError):
        return []
    found = []
    for dimension, targets in views.items():
        if not has_dimension(quantity, dimension):
            continue
        for target in targets:
            if any(part in attribute for part in target.get("attribute_contains", [""])):
                size = quantity.to(target["unit"]).magnitude
                n = number(round(size) if target.get("round") else size)
                found += [template.format(n=n) for template in target["templates"]]
    return found


def product_words(title: str) -> str:
    """The product's name: the words of an item title before its first number, code or linking word.

    "1600677219 VALVE GATE 250 1500# BW A217 WC" -> "VALVE GATE". A leading code is skipped.
    "Type-1 pump with motor along with spare mechanical seals" -> "pump": what comes after "with" are extras, not the product.
    A line break that lost the space ("pumpwith motor") is read as "pump with".
    """
    stop = load_roles()["title_stop"]
    words = title.split()
    has_digit = [any(c.isdigit() for c in w) for w in words]
    start = has_digit.index(False) if False in has_digit else len(words)
    name = []
    for word, digit in zip(words[start:], has_digit[start:], strict=True):
        if digit:
            break
        glued = next((word[: -len(s)] for s in stop if word.lower().endswith(s) and len(word) >= len(s) + 4), None)
        if word.lower() in stop or glued is not None:
            if glued:
                name.append(glued)
            break
        name.append(word)
    return " ".join(name)


def queries_for(req: AtomicRequirement, views: dict[str, list[dict]], abbreviations: Groups | None = None) -> list[str]:
    """Search queries for one requirement: its own words, plus equivalent spellings of any number and any abbreviation,
    each also with the product's name in front."""
    groups = load_abbreviations() if abbreviations is None else abbreviations
    words = "" if req.kind == "standard" else req.attribute.replace("_", " ")  # an identifier is searched alone
    queries = []
    for value in req.values:
        query = " ".join(part for part in (words, value, req.unit) if part)
        queries += [query, *alternatives(query, groups)]
        if req.unit and req.kind == "number":
            queries += unit_views(req.attribute, value, req.unit, views)
    product = product_words(req.item.title)
    if product and req.kind != "standard":  # a booklet for another valve type may state the same value, so name the product too
        queries += [f"{product} {q}" for q in queries]
    return list(dict.fromkeys(queries))  # drop repeats, keep order
