from __future__ import annotations

from app.services.atomize import AtomicRequirement
from app.services.evidence import Evidence
from app.services.match import Outcome, match_all, summarize
from app.services.products import is_named
from app.services.roles import wrong_type
from app.services.tender import Item, distinct_items


def evidence_for(found: list[Evidence], product: str, files: set[str]) -> list[Evidence]:
    """What is known about one product: statements that name it, and statements that name no product but come from a document that describes it."""
    return [e for e in found if (is_named(e) and e.product == product) or (not is_named(e) and e.file in files)]


def files_of(table: dict[tuple[int, str], list[Evidence]], maker: str, product: str) -> set[str]:
    return {e.file for (_, m), found in table.items() if m == maker for e in found if is_named(e) and e.product == product}


def products_of(table: dict[tuple[int, str], list[Evidence]], maker: str) -> list[str]:
    return sorted({e.product for (_, m), found in table.items() if m == maker for e in found if is_named(e)})


def best_product(
    atoms: list[AtomicRequirement], maker: str, table: dict[tuple[int, str], list[Evidence]], aliases: dict[str, dict], readable: bool
) -> tuple[str | None, list[Outcome]]:
    """The single product of a manufacturer that meets the tender best, and its outcomes.

    Every requirement is scored against that one product only, so a manufacturer cannot earn credit by
    combining the strengths of different products. With no named product, all evidence is used.
    """
    candidates = products_of(table, maker)
    if not candidates:
        return None, match_all(atoms, [maker], table, aliases, {maker} if readable else set())

    def outcomes_for(product: str) -> list[Outcome]:
        files = files_of(table, maker, product)
        own = {key: evidence_for(found, product, files) for key, found in table.items() if key[1] == maker}
        return match_all(atoms, [maker], own, aliases, {maker} if readable else set())

    def rank(product: str) -> tuple[bool, float, float]:
        """A product that is not the kind the tender asks for is zeroed in the report, so it must not win here either."""
        outcomes = outcomes_for(product)
        summary = summarize(maker, outcomes)
        return (wrong_type(outcomes) is None, summary.compatibility or 0, summary.coverage or 0)

    chosen = max(candidates, key=rank)
    return chosen, outcomes_for(chosen)


def best_products(
    atoms: list[AtomicRequirement], maker: str, table: dict[tuple[int, str], list[Evidence]], aliases: dict[str, dict], readable: bool
) -> list[tuple[Item, str | None, list[Outcome]]]:
    """For each item of the tender, the single best product of a manufacturer. Different items can be met by different products."""
    result = []
    for item in distinct_items(a.item for a in atoms):
        own = [i for i, a in enumerate(atoms) if a.item == item]
        renumbered = {(n, m): found for n, i in enumerate(own) for (j, m), found in table.items() if j == i}
        product, outcomes = best_product([atoms[i] for i in own], maker, renumbered, aliases, readable)
        result.append((item, product, outcomes))
    return result
