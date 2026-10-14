from __future__ import annotations

import math

from app.services.atomize import AtomicRequirement
from app.services.evidence import Limit
from app.services.measure import alias_for, convert


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


def check_condition(
    limit: Limit, context: list[AtomicRequirement], aliases: dict[str, dict]
) -> tuple[bool, AtomicRequirement] | None:
    """Whether a statement's limit ("DN 40 - 600") covers what the tender asks for.

    Looks for a number the tender asks for that the limit speaks about (a size limit with the tender's size).
    None when there is no such number, so a person has to judge the condition.
    """
    for need in context:
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