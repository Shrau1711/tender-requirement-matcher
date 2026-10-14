from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.atomize import AtomicRequirement

ROLES_FILE = Path(__file__).resolve().parents[2] / "config" / "requirement_roles.json"

NEEDS_DOCUMENT = "needs a certificate, test report or other document, which a catalogue cannot show"
INFORMATION = "identifies the item or says where it is used; it is information, not a capability a product has"
NOT_COVERED = "none of the collected documents says anything about it for any manufacturer, so it cannot be judged"


@lru_cache
def load_roles(path: Path = ROLES_FILE) -> dict[str, list[str]]:
    """Attribute names that are information rather than capability (tag numbers, the place of use), written as data."""
    return json.loads(path.read_text(encoding="utf-8"))


def key_of(r: AtomicRequirement) -> tuple:
    return (r.item.title, r.file, r.pdf_page, r.source_name, r.source_value, r.attribute, tuple(r.values))


def set_aside(
    atoms: list[AtomicRequirement], makers: list[str], table: dict, roles: dict[str, list[str]] | None = None
) -> dict[tuple, str]:
    """The requirements that cannot count toward a percentage, each with the reason. Keyed by key_of.

    A requirement counts only if a catalogue could show it and at least one manufacturer's documents say something about it.
    Otherwise a score of zero would blame every manufacturer for a gap in the collected data.
    """
    information = set((roles or load_roles())["information"])
    covered = {key_of(a) for i, a in enumerate(atoms) if any(table.get((i, m)) for m in makers)}
    reasons: dict[tuple, str] = {}
    for a in atoms:
        key = key_of(a)
        if a.evidence == "paperwork":
            reasons[key] = NEEDS_DOCUMENT
        elif a.attribute in information:
            reasons[key] = INFORMATION
        elif key not in covered:
            reasons[key] = NOT_COVERED
    return reasons
