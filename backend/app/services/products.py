from __future__ import annotations

import json

from pydantic import BaseModel

from app.services.evidence import Evidence
from app.services.llm import LLM, ask

SYSTEM = """You are given the names of products found in one manufacturer's documents. The same product is often written in several ways (with or without a model code, with or without "butterfly valve", different dashes or capital letters).
Group the names that mean the same product. Different models, seat types or constructions are different products, even when their names are similar.
A body style or end connection (wafer, lug, flanged) is a variant of the same product, not another product.
"cover_headings" may be given: the headings of the manufacturer's first page, which say what its main product line is. A name that only describes a variant of that product line belongs to it.
Every name must appear in exactly one group. Copy the names exactly as given."""

UNNAMED = "unclear"


class Groups(BaseModel):
    groups: list[list[str]]


def is_named(e: Evidence) -> bool:
    return e.same_product_type == "yes" and e.product.strip().lower() != UNNAMED


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