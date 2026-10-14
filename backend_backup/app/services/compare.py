from __future__ import annotations

import math
import re

from pydantic import BaseModel

from app.services.atomize import AtomicRequirement
from app.services.condition import check_condition
from app.services.evidence import Evidence
from app.services.measure import convert, unit_in
from app.services.search import tokenize

PARTLY = 75  # the most a statement can earn when it only applies under a condition or for an unnamed product
EXCEEDS = 75  # rated higher than asked
DIFFERENT_READING = 50  # matches only if a trade unit such as PN is read the other way
CANNOT_COMPARE = 25  # a statement exists but is in units that cannot be converted
FILLER = {"valve", "type", "body", "end", "ends", "connection"}  # words that say nothing about which kind it is


class Verdict(BaseModel):
    score: int
    reason: str
    review: bool = False  # a person should look at this one


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-6)


def reach(wanted: float, operator: str, shape: str, numbers: list[float]) -> int:
    """How well one stated number, range or list serves one wanted number."""
    low, high = min(numbers), max(numbers)
    if operator in ("equals", "one_of"):
        if shape == "up_to":
            return 100 if close(wanted, high) else EXCEEDS if high > wanted else 0
        if shape == "at_least":
            return 100 if low <= wanted else 0
        if shape == "range":
            return 100 if low <= wanted <= high or close(wanted, low) or close(wanted, high) else 0
        return 100 if any(close(wanted, n) for n in numbers) else 0
    if operator == "at_least":
        return 100 if shape == "at_least" or high >= wanted or close(high, wanted) else 0
    return 100 if low <= wanted or close(low, wanted) else 0  # at_most


def combine(scores: list[int], operator: str) -> int:
    return max(scores) if operator == "one_of" else round(sum(scores) / len(scores))


def number_verdict(req: AtomicRequirement, ev: Evidence, aliases: dict[str, dict]) -> Verdict:
    said = " ".join(ev.stated.split())
    if not ev.numbers:
        return Verdict(score=0, reason="no number is stated")
    try:
        wanted = [float(v) for v in req.values]
    except ValueError:
        return Verdict(score=CANNOT_COMPARE, reason="the requirement's value is not a plain number", review=True)
    unit = ev.unit or unit_in(ev.stated, req.attribute, aliases)
    stated = [convert(n, unit, req.unit, req.attribute, aliases) for n in ev.numbers]
    if None in stated:
        printed = f"stated in {unit}" if unit else "stated with no unit"
        return Verdict(score=CANNOT_COMPARE, reason=f"{printed}, which cannot be converted to {req.unit}", review=True)
    score = combine([reach(w, req.operator, ev.shape, stated) for w in wanted], req.operator)
    if score == 0:
        other = [convert(n, unit, req.unit, req.attribute, aliases, alternative=True) for n in ev.numbers]
        if None not in other and combine([reach(w, req.operator, ev.shape, other) for w in wanted], req.operator) == 100:
            return Verdict(score=DIFFERENT_READING, reason=f"{said} matches only if {unit} is read the other way", review=True)
    return Verdict(score=score, reason=f"stated {said}")


def normal_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r":\s*\d{4}\b", "", text.lower()))  # "IS 13095:2008" -> "is13095"


def kind_words(text: str) -> set[str]:
    words = {w[:-1] if w.endswith("s") and len(w) > 3 else w for w in tokenize(text)}
    return words - FILLER


def same_thing(kind: str, wanted: str, stated: str) -> bool:
    if kind == "standard":
        return normal_identifier(wanted) == normal_identifier(stated)
    want, have = kind_words(wanted), kind_words(stated)
    want_numbers, have_numbers = {w for w in want if w[0].isdigit()}, {w for w in have if w[0].isdigit()}
    if want_numbers and have_numbers and not want_numbers & have_numbers:
        return False  # "Class 125" is not "Class 150", however many words they share
    return bool(want & have)


def names_a_reference(req: AtomicRequirement, items: list[str]) -> bool:
    """True when every stated item is a code or document name (it has a digit) sharing no word with the requirement."""
    wanted = set().union(*(kind_words(w) for w in req.values))
    return req.kind != "standard" and all(any(c.isdigit() for c in i) and not kind_words(i) & wanted for i in items)


def items_verdict(req: AtomicRequirement, ev: Evidence) -> Verdict:
    items = ev.items or [ev.stated]
    heard = [*items, ev.stated] if req.kind != "standard" else items  # the printed label counts too: "Levers: SR+, SP+"
    scores = [100 if any(same_thing(req.kind, w, i) for i in heard) else 0 for w in req.values]
    score = combine(scores, req.operator)
    if not score and names_a_reference(req, items):
        return Verdict(score=CANNOT_COMPARE, reason=f"states {', '.join(items)}, which names a reference but not the thing asked for", review=True)
    return Verdict(score=score, reason=f"states {', '.join(items)}")


def verdict(req: AtomicRequirement, ev: Evidence, aliases: dict[str, dict], context: list[AtomicRequirement] | None = None) -> Verdict:
    """How one piece of evidence measures up to one requirement. Only plain code decides this.

    context is the item's other requirements: a condition such as "DN 40 - 600" is checked against the size asked for.
    """
    found = number_verdict(req, ev, aliases) if req.kind == "number" else items_verdict(req, ev)
    notes = []
    if ev.condition and found.score:
        checked = check_condition(ev.condition_limit, context or [], aliases) if ev.condition_limit else None
        if checked and not checked[0]:
            need = checked[1]
            return Verdict(score=0, reason=f"{found.reason}; but only {ev.condition}, which does not include the {need.attribute} asked for ({' / '.join(need.values)} {need.unit})")
        if not checked:
            notes.append(f"only {ev.condition}")
    if ev.same_product_type == "unclear" and found.score:
        notes.append("the product is not named")
    if notes:
        found = Verdict(score=min(found.score, PARTLY), reason=f"{found.reason}; {'; '.join(notes)}", review=True)
    if ev.ocr and found.score:
        found = Verdict(score=found.score, reason=f"{found.reason}; read from a scanned page", review=True)
    return found