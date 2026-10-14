from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel

from app.services.llm import LLM, ask
from app.services.tender import Item, Requirement, by_item

SYSTEM = """You turn rows of a tender's technical specification into atomic requirements.
Rules:
- The input has "known_attributes" (names already used for other items) and "rows", each with an index, a name and a value. Cover every row at least once, using its index in "row".
- Split a row into several requirements only when it states independent conditions. Never split one value.
- Copy values exactly as printed. Never convert units or do arithmetic. If the name or value gives a unit, put it in "unit".
- attribute: a short snake_case name for what is specified, such as nominal_size or end_connection. If a known attribute means the same thing, reuse its exact name.
- kind: number, choice, text, standard (an identifier such as IS 13095), or yes_no.
- operator: equals, at_least, at_most, or one_of when any of several listed values is acceptable.
- evidence: "product" if a manufacturer's product brochure could show it, including the standard the product is made to (such as IS 13095). "paperwork" if it needs a certificate, test report, licence, undertaking or similar document.
"""


class Atom(BaseModel):
    row: int
    attribute: str
    kind: Literal["number", "choice", "text", "standard", "yes_no"]
    operator: Literal["equals", "at_least", "at_most", "one_of"]
    values: list[str]
    unit: str | None = None
    evidence: Literal["product", "paperwork"]


class Extraction(BaseModel):
    requirements: list[Atom]


class AtomicRequirement(BaseModel):
    item: Item
    pdf_page: int
    source_name: str
    source_value: str
    attribute: str
    kind: str
    operator: str
    values: list[str]
    unit: str | None
    evidence: str


def rows_prompt(rows: list[Requirement], known: list[str]) -> str:
    listed = [{"row": i, "name": r.name, "value": r.value} for i, r in enumerate(rows)]
    return json.dumps({"known_attributes": known, "rows": listed})


def to_atomic(source: Requirement, atom: Atom) -> AtomicRequirement:
    return AtomicRequirement(
        item=source.item, pdf_page=source.pdf_page, source_name=source.name, source_value=source.value,
        **atom.model_dump(exclude={"row"}),
    )


def atomize(llm: LLM, rows: list[Requirement], known: list[str]) -> list[AtomicRequirement]:
    """Atomic requirements for the rows of one item."""
    atoms = ask(llm, SYSTEM, rows_prompt(rows, known), Extraction).requirements
    missing = [a.row for a in atoms if not 0 <= a.row < len(rows)]
    if missing:
        raise ValueError(f"The model referred to rows that do not exist: {missing}")
    return [to_atomic(rows[a.row], a) for a in atoms]


def uncovered_rows(rows: list[Requirement], atoms: list[AtomicRequirement]) -> list[Requirement]:
    """Rows the model silently dropped."""
    return [r for r in rows if not any(a.source_name == r.name and a.source_value == r.value for a in atoms)]


def atomize_items(
    llm: LLM, requirements: list[Requirement]
) -> Iterator[tuple[Item, list[Requirement], list[AtomicRequirement]]]:
    """One model call per item. Each call is told the attribute names used so far, so names stay consistent."""
    known: set[str] = set()
    for item, rows in by_item(requirements):
        atoms = atomize(llm, rows, sorted(known))
        known |= {a.attribute for a in atoms}
        yield item, rows, atoms


def atomize_tender(llm: LLM, requirements: list[Requirement]) -> list[AtomicRequirement]:
    return [a for _, _, atoms in atomize_items(llm, requirements) for a in atoms]