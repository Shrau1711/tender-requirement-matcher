from __future__ import annotations

import json
import re
from pathlib import Path

import pint

ALIASES_FILE = Path(__file__).resolve().parents[2] / "config" / "unit_aliases.json"
ureg = pint.UnitRegistry()


def load_aliases(path: Path = ALIASES_FILE) -> dict[str, dict]:
    """Trade 'units' that pint does not know (PN, DN, NB, INCH for nominal sizes), written as data."""
    return json.loads(path.read_text(encoding="utf-8"))


def alias_for(unit: str | None, attribute: str, aliases: dict[str, dict]) -> dict | None:
    entry = aliases.get((unit or "").upper())
    if entry and any(part in attribute for part in entry["attribute_contains"]):
        return entry
    return None


def unit_in(text: str, attribute: str, aliases: dict[str, dict]) -> str | None:
    """A trade unit written in the statement itself ("PN 1.6"), for when the reading left the unit out."""
    words = {w.upper() for w in re.findall(r"[A-Za-z]+", text)}
    return next((u for u in aliases if u in words and alias_for(u, attribute, aliases)), None)


def convert(
    value: float, unit: str | None, target: str | None, attribute: str, aliases: dict[str, dict], alternative: bool = False
) -> float | None:
    """value in unit, written in the target unit. None when the two cannot be compared.

    alternative=True uses the other common reading of a trade unit (PN 1.6 meaning 1.6 MPa); None if it has none.
    """
    if (unit or "").lower() == (target or "").lower():
        return None if alternative else value
    if unit is None or target is None:
        return None
    entry = alias_for(unit, attribute, aliases)
    if entry:
        factor = entry.get("alternative_factor") if alternative else entry["factor"]
        if factor is None:
            return None
        value, unit = value * factor, entry["unit"]
    elif alternative:
        return None
    try:
        return float(ureg.Quantity(value, unit).to(target).magnitude)
    except (pint.errors.PintError, TypeError):
        return None