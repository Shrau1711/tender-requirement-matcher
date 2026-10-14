from __future__ import annotations

import math
import re

from pydantic import BaseModel

from app.services.abbreviations import canonical
from app.services.atomize import AtomicRequirement
from app.services.condition import check_condition, stated_by_tender
from app.services.evidence import Evidence
from app.services.measure import convert, unit_in
from app.services.scales import scale_verdict
from app.services.search import tokenize

PARTLY = 75  # the most a statement can earn when it only applies under a condition or for an unnamed product
EXCEEDS = 75  # rated higher than asked
DIFFERENT_READING = 50  # matches only if a trade unit such as PN is read the other way
CANNOT_COMPARE = 25  # a statement exists but is in units that cannot be converted
FAMILY_ONLY = 50  # the statement names the kind of thing (grey cast iron) but not the grade or number asked for (IS 210 FG 260)
CLASS_UNITS = ("class", "#", "lb")  # what a pressure class number is printed with
BARE_NUMBER = re.compile(r"^(?:class\s*)?#?\s*(\d+(?:\.\d+)?)\s*#?$", re.IGNORECASE)  # "1500#", "Class 1500", "1500"
FILLER = {"valve", "type", "body", "end", "ends", "connection"}  # words that say nothing about which kind it is


UNCLEAR_VALUE = "unclear tender value"
UNITS = "units"
UNIT_READING = "unit read the other way"
REFERENCE_ONLY = "reference only"
EQUIVALENT = "equivalent grade"
GRADE_NOT_STATED = "grade not stated"
CONDITION = "only under a condition"
PRODUCT_NOT_NAMED = "product not named"
SCANNED = "scanned page"


class Verdict(BaseModel):
    score: int
    reason: str
    flags: list[str] = []  # why a person should look at this one; empty when nobody needs to

    @property
    def review(self) -> bool:
        return bool(self.flags)


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
        if shape == "at_least":  # "above 25" is only a floor: it proves the wanted figure only if the floor is that high
            return 100 if low >= wanted or close(low, wanted) else CANNOT_COMPARE
        return 100 if high >= wanted or close(high, wanted) else 0
    if shape == "at_least":  # at_most wanted, but only a floor is stated ("above 25"): the top is unknown
        return CANNOT_COMPARE
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
        return Verdict(score=CANNOT_COMPARE, reason="the requirement's value is not a plain number", flags=[UNCLEAR_VALUE])
    unit = ev.unit or unit_in(ev.stated, req.attribute, aliases)
    stated = [convert(n, unit, req.unit, req.attribute, aliases) for n in ev.numbers]
    if None in stated:
        printed = f"stated in {unit}" if unit else "stated with no unit"
        target = f"cannot be converted to {req.unit}" if req.unit else "cannot be compared because the tender gives no unit"
        return Verdict(score=CANNOT_COMPARE, reason=f"{printed}, which {target}", flags=[UNITS])
    score = combine([reach(w, req.operator, ev.shape, stated) for w in wanted], req.operator)
    if score == 0:
        other = [convert(n, unit, req.unit, req.attribute, aliases, alternative=True) for n in ev.numbers]
        if None not in other and combine([reach(w, req.operator, ev.shape, other) for w in wanted], req.operator) == 100:
            return Verdict(score=DIFFERENT_READING, reason=f"{said} matches only if {unit} is read the other way", flags=[UNIT_READING])
    return Verdict(score=score, reason=f"stated {said}")


def class_verdict(req: AtomicRequirement, ev: Evidence) -> Verdict | None:
    """A class rating asked for as a bare number ("1500#"), against class numbers stated as a list or a range ("Class 150 - 2500").

    None when this does not apply, so the words are compared instead.
    """
    found = [BARE_NUMBER.match(v.strip()) for v in req.values]
    in_class = not ev.unit or any(u in ev.unit.lower() for u in CLASS_UNITS)  # PN or bar are another system
    if not all(found) or not ev.numbers or not in_class:
        return None
    score = combine([reach(float(m[1]), req.operator, ev.shape, ev.numbers) for m in found], req.operator)
    return Verdict(score=score, reason=f"states {' '.join(ev.stated.split())}")


def normal_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r":\s*\d{4}\b", "", text.lower()))  # "IS 13095:2008" -> "is13095"


def kind_words(text: str) -> set[str]:
    words = {w[:-1] if w.endswith("s") and len(w) > 3 else w for w in tokenize(canonical(text))}
    return words - FILLER


def closeness(kind: str, wanted: str, stated: str) -> int:
    """100 when the stated thing is the wanted one, FAMILY_ONLY when it is only the same kind of thing, else 0."""
    if kind == "standard":
        return 100 if normal_identifier(wanted) == normal_identifier(stated) else 0
    want, have = kind_words(wanted), kind_words(stated)
    want_numbers, have_numbers = {w for w in want if w[0].isdigit()}, {w for w in have if w[0].isdigit()}
    if want_numbers and have_numbers and not want_numbers & have_numbers:
        return 0  # "Class 125" is not "Class 150", however many words they share
    if not want & have:
        return 0
    if any(len(n) > 1 for n in want_numbers) and not have_numbers:
        return FAMILY_ONLY  # "grey cast iron" does not say it is "IS 210 FG 260"
    return 100


def names_a_reference(req: AtomicRequirement, items: list[str]) -> bool:
    """True when every stated item is a code or document name (it has a digit) sharing no word with the requirement."""
    wanted = set().union(*(kind_words(w) for w in req.values))
    if req.kind == "standard" or all(w[0].isdigit() for w in wanted):
        return False  # a plain number asked for ("1500") is compared with the numbers stated, not treated as a document name
    return all(any(c.isdigit() for c in i) and not kind_words(i) & wanted for i in items)


def items_verdict(req: AtomicRequirement, ev: Evidence) -> Verdict:
    items = ev.items or [ev.stated]
    heard = [*items, ev.stated] if req.kind != "standard" else items  # the printed label counts too: "Levers: SR+, SP+"
    ranked = scale_verdict(req, heard)
    if ranked:
        return Verdict(score=ranked[0], reason=ranked[1])
    scores = [max(closeness(req.kind, w, i) for i in heard) for w in req.values]
    score = combine(scores, req.operator)
    if not score and names_a_reference(req, items):
        return Verdict(score=CANNOT_COMPARE, reason=f"states {', '.join(items)}, which names a reference but not the thing asked for", flags=[REFERENCE_ONLY])
    if not score and "equivalent" in req.source_value.lower() and any(kind_words(w) & kind_words(i) for w in req.values for i in heard):
        return Verdict(score=CANNOT_COMPARE, reason=f"states {', '.join(items)}; the tender accepts an equivalent, and whether this is one needs a person", flags=[EQUIVALENT])
    if FAMILY_ONLY in scores and score < 100:
        return Verdict(score=score, reason=f"states {', '.join(items)}: the kind of thing, but not the grade or number asked for", flags=[GRADE_NOT_STATED])
    return Verdict(score=score, reason=f"states {', '.join(items)}")


def verdict(req: AtomicRequirement, ev: Evidence, aliases: dict[str, dict], context: list[AtomicRequirement] | None = None) -> Verdict:
    """How one piece of evidence measures up to one requirement. Only plain code decides this.

    context is the item's other requirements: a condition such as "DN 40 - 600" is checked against the size asked for.
    """
    found = number_verdict(req, ev, aliases) if req.kind == "number" else class_verdict(req, ev) or items_verdict(req, ev)
    notes, flags = [], []
    if ev.condition and found.score:
        checked = check_condition(ev.condition_limit, context or [], aliases) if ev.condition_limit else None
        if checked and not checked[0]:
            need = checked[1]
            return Verdict(score=0, reason=f"{found.reason}; but only {ev.condition}, which does not include the {need.attribute} asked for ({' / '.join(need.values)} {need.unit})")
        if not checked and not stated_by_tender(ev.condition, context or []):
            notes.append(f"only {ev.condition}")
            flags.append(CONDITION)
    if ev.same_product_type == "unclear" and found.score:
        notes.append("the product is not named")
        flags.append(PRODUCT_NOT_NAMED)
    if notes:
        found = Verdict(score=min(found.score, PARTLY), reason=f"{found.reason}; {'; '.join(notes)}", flags=[*found.flags, *flags])
    if ev.ocr and found.score:
        found = Verdict(score=found.score, reason=f"{found.reason}; read from a scanned page", flags=[*found.flags, SCANNED])
    return found
