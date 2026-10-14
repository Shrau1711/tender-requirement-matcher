from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.services.atomize import AtomicRequirement
from app.services.match import Outcome, Status
from app.services.tender import Item, distinct_items

GOLD_DIR = Path(__file__).resolve().parents[3] / "data" / "eval" / "gold"


class Label(BaseModel):
    """What a person found in the manufacturer's documents. status None means not labelled yet."""

    status: Status | None = None
    page: int | list[int] | None = None  # one page, or every page where it is stated
    note: str = ""

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


def blank_gold(atoms: list[AtomicRequirement], makers: list[str]) -> Gold:
    """An empty label sheet: one entry for every requirement a catalogue could answer, for every manufacturer."""
    several = len(distinct_items(a.item for a in atoms)) > 1
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
    rows = []
    several = len(distinct_items(o.requirement.item for o in outcomes)) > 1
    for o in outcomes:
        key = key_for(o.requirement.item, o.requirement.attribute, several)
        label = gold.get(key, {}).get(o.manufacturer)
        if label and label.status and o.assessed and o.status != "unsupported requirement":
            rows.append(Row(
                attribute=key, manufacturer=o.manufacturer, gold=label.status, ours=o.status, score=o.score,
                gold_pages=label.pages, our_page=o.evidence.pdf_page if o.evidence else None, reason=o.reason,
            ))
    return rows


def share(hits: int, total: int) -> str:
    return f"{hits}/{total} ({100 * hits / total:.0f}%)" if total else "none"
