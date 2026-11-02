from __future__ import annotations

import json
import re

from pydantic import BaseModel

from app.extraction.evidence import Evidence
from app.llm.llm import LLM, ask
from app.vocabulary.roles import load_roles
from app.vocabulary.words import singular

SYSTEM = """You are given the names of products found in one manufacturer's documents. The same product is often written in several ways (with or without a model code, with or without "butterfly valve", different dashes or capital letters).
Group the names that mean the same product. Different models, seat types or constructions are different products, even when their names are similar.
A body style or end connection (wafer, lug, flanged) is a variant of the same product, not another product.
"cover_headings" may be given: the headings of the manufacturer's first page, which say what its main product line is. A name that only describes a variant of that product line belongs to it.
Every name must appear in exactly one group. Copy the names exactly as given."""

UNNAMED = "unclear"


class Groups(BaseModel):
    groups: list[list[str]]


def is_component(name: str) -> bool:
    """True when the name is a part fitted to a product ("Standard motors", "Cartridge seal"), not a product of its own.

    The head noun decides: the last word before any bracket or dash, so "Canned Motor Pump - i-CM" is still a pump.
    """
    head = re.split(r"\(| - ", name)[0].split()
    return bool(head) and singular(head[-1].lower().strip(",.")) in load_roles()["components"]


def is_named(e: Evidence) -> bool:
    """A statement counts as naming a product when it names one that is not just a part. Statements about a part
    (a motor's enclosure, a seal's material) belong to the product of the document they come from."""
    return e.same_product_type == "yes" and e.product.strip().lower() != UNNAMED and not is_component(e.product)


def canonical_names(llm: LLM, names: list[str], cover: list[str] | None = None) -> dict[str, str]:
    """Every name mapped to the longest (most descriptive) name of its group. Names the model leaves out stay as they are."""
    if len(names) < 2:
        return {n: n for n in names}
    groups = ask(llm, SYSTEM, json.dumps({"cover_headings": cover or [], "names": names}), Groups).groups
    mapping: dict[str, str] = {}
    for group in groups:
        members = [n for n in group if n in names and n not in mapping]
        for n in members:
            mapping[n] = max(members, key=len)
    return {n: mapping.get(n, n) for n in names}


def canonical_table(
    llm: LLM, table: dict[tuple[int, str], list[Evidence]], makers: list[str], covers: dict[str, list[str]] | None = None
) -> dict[tuple[int, str], list[Evidence]]:
    """The evidence table with each manufacturer's product names unified. covers holds each manufacturer's cover headings."""
    renamed: dict[str, dict[str, str]] = {}
    for maker in makers:
        names = sorted({e.product for (_, m), found in table.items() if m == maker for e in found if is_named(e)})
        renamed[maker] = canonical_names(llm, names, (covers or {}).get(maker))
    return {
        (i, m): [e.model_copy(update={"product": renamed[m].get(e.product, e.product)}) if is_named(e) else e for e in found]
        for (i, m), found in table.items()
    }
