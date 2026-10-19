from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.services.atomize import AtomicRequirement
from app.services.match import Outcome, Status
from app.services.tender import Item

GOLD_DIR = Path(__file__).resolve().parents[3] / "data" / "eval" / "gold"


class Label(BaseModel):
    """What a person found in the manufacturer's documents. status None means not labelled yet."""

    status: Status | None = None
    page: int | list[int] | None = None  # one page, or every page where it is stated
    note: str = ""
    checked: bool = False  # a person looked at the cited page and confirmed the label

    @property
    def pages(self) -> list[int]:
        return [] if self.page is None else self.page if isinstance(self.page, list) else [self.page]


class Row(BaseModel):
    attribute: str
    manufacturer: str
    gold: Status
    ours: Status
    score: int
    gold_pages: list[int]
    our_page: int | None
    reason: str
    checked: bool = False
    flags: list[str] = []  # the warnings our answer carried, such as "scanned page"
    found: bool = False  # some evidence was found, whether or not it meets the requirement

    @property
    def agrees(self) -> bool:
        return self.gold == self.ours

    @property
    def page_agrees(self) -> bool:
        return self.our_page in self.gold_pages


Gold = dict[str, dict[str, Label]]  # attribute -> manufacturer -> label


def key_for(item: Item, attribute: str, several_items: bool) -> str:
    """The label sheet's name for a requirement: the attribute alone, or with the item when a tender has several."""
    return f"{item.title} | {attribute}" if several_items else attribute


def has_several(items: list[Item]) -> bool:
    """True when the tender names more than one product. The same product listed twice with different quantities is still one."""
    return len({item.title for item in items}) > 1


def blank_gold(atoms: list[AtomicRequirement], makers: list[str]) -> Gold:
    """An empty label sheet: one entry for every requirement a catalogue could answer, for every manufacturer."""
    several = has_several([a.item for a in atoms])
    return {key_for(a.item, a.attribute, several): {m: Label() for m in makers} for a in atoms if a.evidence == "product"}


def save_gold(gold: Gold, path: Path) -> None:
    data = {attribute: {m: label.model_dump() for m, label in labels.items()} for attribute, labels in gold.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_gold(path: Path) -> Gold:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {attribute: {m: Label(**label) for m, label in labels.items()} for attribute, labels in data.items()}


def compare(outcomes: list[Outcome], gold: Gold) -> list[Row]:
    """Our outcome next to the person's label, for every labelled row of a manufacturer we could read."""
    rows, seen = [], set()
    several = has_several([o.requirement.item for o in outcomes])
    for o in outcomes:
        key = key_for(o.requirement.item, o.requirement.attribute, several)
        label = gold.get(key, {}).get(o.manufacturer)
        if label and label.status and o.assessed and o.status != "unsupported requirement" and (key, o.manufacturer) not in seen:
            seen.add((key, o.manufacturer))  # a label is compared once, even if the same product is listed twice
            rows.append(Row(
                attribute=key, manufacturer=o.manufacturer, gold=label.status, ours=o.status, score=o.score,
                gold_pages=label.pages, our_page=o.evidence.pdf_page if o.evidence else None, reason=o.reason, checked=label.checked, flags=o.flags, found=o.found,
            ))
    return rows


def cited(gold: Gold, atoms: list[AtomicRequirement]) -> list[tuple[AtomicRequirement, str, str, set[int]]]:
    """Every (requirement, label key, manufacturer, pages) where a person found something and said on which pages.

    A requirement that several items share is listed once per manufacturer.
    """
    several = has_several([a.item for a in atoms])
    found, seen = [], set()
    for a in atoms:
        key = key_for(a.item, a.attribute, several)
        for maker, label in gold.get(key, {}).items():
            if label.status in ("fully matched", "partially matched") and label.pages and (key, maker) not in seen:
                seen.add((key, maker))
                found.append((a, key, maker, set(label.pages)))
    return found


def share(hits: int, total: int) -> str:
    return f"{hits}/{total} ({100 * hits / total:.0f}%)" if total else "none"


def mirror(gold: Gold, atoms: list[AtomicRequirement]) -> list[tuple[str, str, str]]:
    """Copy each hand-checked label to the same requirement of the tender's other items, when it asks exactly the same thing.

    A tender often lists nearly identical products with the same line of requirements; the documents say the same for all of them.
    Returns (from key, to key, manufacturer) for every label copied. Labels already checked by hand are never overwritten.
    """
    from app.services.evidence import question

    several = has_several([a.item for a in atoms])
    same: dict[tuple, list[str]] = {}
    for a in atoms:
        key = key_for(a.item, a.attribute, several)
        if a.evidence == "product" and key not in same.setdefault(question(a), []):
            same[question(a)].append(key)
    copied = []
    for keys in same.values():
        for source in keys:
            for maker, label in gold.get(source, {}).items():
                if not label.checked:
                    continue
                for target in (k for k in keys if k != source):
                    other = gold.get(target, {}).get(maker)
                    if other is not None and not other.checked:
                        gold[target][maker] = label.model_copy()
                        copied.append((source, target, maker))
    return copied
