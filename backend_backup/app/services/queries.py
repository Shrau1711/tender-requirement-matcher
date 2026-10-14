from __future__ import annotations

import json
from pathlib import Path

import pint

from app.services.atomize import AtomicRequirement

UNIT_VIEWS_FILE = Path(__file__).resolve().parents[2] / "config" / "units.json"
ureg = pint.UnitRegistry()


def load_unit_views(path: Path = UNIT_VIEWS_FILE) -> dict[str, list[dict]]:
    return json.loads(path.read_text(encoding="utf-8"))


def number(x: float) -> str:
    return f"{x:.6g}"  # 16.000000000000004 -> 16


def unit_views(attribute: str, value: str, unit: str, views: dict[str, list[dict]]) -> list[str]:
    """The same quantity written the other ways brochures write it, e.g. 1.6 MPa -> 16 bar, PN 16."""
    try:
        quantity = ureg.Quantity(float(value), unit)
    except (ValueError, pint.errors.PintError):
        return []
    found = []
    for dimension, targets in views.items():
        if not quantity.check(dimension):
            continue
        for target in targets:
            if any(part in attribute for part in target.get("attribute_contains", [""])):
                n = number(quantity.to(target["unit"]).magnitude)
                found += [template.format(n=n) for template in target["templates"]]
    return found


def queries_for(req: AtomicRequirement, views: dict[str, list[dict]]) -> list[str]:
    """Search queries for one requirement: its own words, plus equivalent spellings of any number."""
    words = "" if req.kind == "standard" else req.attribute.replace("_", " ")  # an identifier is searched alone
    queries = []
    for value in req.values:
        queries.append(" ".join(part for part in (words, value, req.unit) if part))
        if req.unit and req.kind == "number":
            queries += unit_views(req.attribute, value, req.unit, views)
    return list(dict.fromkeys(queries))  # drop repeats, keep order