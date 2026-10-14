from __future__ import annotations

import math
import re

from app.services.atomize import AtomicRequirement
from app.services.evidence import Limit
from app.services.measure import alias_for, convert
from app.services.search import tokenize


def inside(wanted: float, limit: Limit, numbers: list[float]) -> bool:
    low, high = min(numbers), max(numbers)
    if limit.shape == "up_to":
        return wanted <= high
    if limit.shape == "at_least":
        return wanted >= low
    if limit.shape == "range":
        return low <= wanted <= high
    return any(math.isclose(wanted, n, rel_tol=1e-6) for n in numbers)


def speaks_about(unit: str | None, need: AtomicRequirement, aliases: dict[str, dict]) -> bool:
    """A limit is about what the tender asks for only if it is written in that unit or in a trade unit made for it.

    Units that merely convert (a vacuum level in mbar against a pressure rating in MPa) are not the same thing.
    """
    return (unit or "").lower() == (need.unit or "").lower() or alias_for(unit, need.attribute, aliases) is not None


SIZE_AS_WRITTEN = re.compile(r"^(?:nb|dn)\s*(\d+(?:\.\d+)?)$", re.IGNORECASE)


def as_number(need: AtomicRequirement) -> AtomicRequirement:
    """A size written as "Nb40" is the number 40 mm, so a condition such as "DN 40 - 600" can be checked against it."""
    sizes = [SIZE_AS_WRITTEN.match(v.strip()) for v in need.values]
    if need.kind == "number" or "size" not in need.attribute or not all(sizes):
        return need
    return need.model_copy(update={"kind": "number", "unit": "mm", "values": [m.group(1) for m in sizes]})


def check_condition(
    limit: Limit, context: list[AtomicRequirement], aliases: dict[str, dict]
) -> tuple[bool, AtomicRequirement] | None:
    """Whether a statement's limit ("DN 40 - 600") covers what the tender asks for.

    Looks for a number the tender asks for that the limit speaks about (a size limit with the tender's size).
    None when there is no such number, so a person has to judge the condition.
    """
    needs = sorted((as_number(n) for n in context), key=lambda n: "nominal" not in n.attribute)
    for need in needs:
        if need.kind != "number" or need.unit is None or not limit.numbers or not speaks_about(limit.unit, need, aliases):
            continue
        try:
            wanted = [float(v) for v in need.values]
        except ValueError:
            continue
        converted = [convert(n, limit.unit, need.unit, need.attribute, aliases) for n in limit.numbers]
        numbers = [n for n in converted if n is not None]
        if len(numbers) < len(converted):
            continue
        results = [inside(w, limit, numbers) for w in wanted]
        return (any(results) if need.operator == "one_of" else all(results)), need
    return None


def stated_by_tender(condition: str, context: list[AtomicRequirement]) -> bool:
    """True when the condition ("50 Hz", "clean water") is itself something the tender asks for, so it holds by definition."""
    words = set(tokenize(condition))
    return bool(words) and any(words <= set(tokenize(" ".join([n.source_name, n.source_value, *n.values, n.unit or ""]))) for n in context)
