"""Keep what a tender costs inside a budget, and say so when it does.

Reading a manufacturer's documents is the only expensive step, and a tender can ask for thousands of questions. Before any question is asked, the cost of the
questions that are not already saved is estimated. If it is over the budget the system first reads fewer passages per question, and if that is still too much
it evaluates the first items of the tender only. Whatever was cut is named in the report's notes, so a smaller report is never mistaken for a complete one.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import number_setting
from app.cost.tokens import TOKEN_COUNTER, count_tokens
from app.extraction.atomize import AtomicRequirement
from app.extraction.evidence import (
    SYSTEM,
    TOP_K,
    Found,
    passages_prompt,
    question,
    question_jobs,
    retrieve,
    usable,
)
from app.llm.llm import LLM, request_system
from app.llm.llm_cache import MAX_CALLS
from app.retrieval.base import Retriever
from app.tender.items import distinct_items

TOKEN_BUDGET = number_setting("TENDER_TOKEN_BUDGET", 1_500_000)  # input tokens of new questions one tender may use (about 150 rupees at the current price)
RESERVED_CALLS = number_setting("RESERVED_CALLS", 60)  # model calls kept back for reading the tender and naming products
LISTED = 8  # how many skipped items are named in the note

Prices = dict[tuple, int]  # (question, manufacturer) -> estimated input tokens, 0 when the answer is already saved


@dataclass
class Plan:
    atoms: list[AtomicRequirement]  # the requirements that will be evaluated
    depth: int  # passages read per question
    notes: list[str]  # what was cut, for the report
    questions: int = 0  # new questions the model will be asked
    tokens: int = 0  # their input tokens


def price(llm: LLM, req: AtomicRequirement, hits: list) -> int:
    """Input tokens one question would cost: nothing if its answer is saved, or if there is nothing to read."""
    hits = usable(req, hits)
    if not hits:
        return 0
    user = passages_prompt(req, hits)
    sent = request_system(SYSTEM, Found)
    has = getattr(llm, "has", None)
    if has is not None and has(sent, user):
        return 0
    # The estimate has always counted the instructions without the answer format added to them (about 440 tokens less);
    # it still does, so estimates do not change. An exact counter is given what is really sent.
    return count_tokens(SYSTEM if TOKEN_COUNTER == "estimate" else sent, user)


def prices(llm: LLM, index: Retriever, atoms: list[AtomicRequirement], makers: list[str], views: dict, depth: int) -> Prices:
    _, first = question_jobs(atoms, makers)
    return {key: price(llm, atoms[i], retrieve(index, atoms[i], key[1], views, depth=depth)) for key, i in first.items()}


def keys_of(atoms: list[AtomicRequirement], makers: list[str]) -> set[tuple]:
    return {(question(a), m) for a in atoms if a.evidence == "product" for m in makers}


def atoms_within(atoms: list[AtomicRequirement], makers: list[str], priced: Prices, tokens: int, calls: int) -> list[AtomicRequirement]:
    """The first requirements of the tender whose new questions fit the budget, in tender order.

    Whole items are kept or dropped, so an item's score never rests on part of it. The one exception is the first item: if it alone is over the budget,
    its first requirements are kept (at least one), because the tender must be evaluated on something. A question two items share is paid for once.
    """
    kept: list[AtomicRequirement] = []
    paid: set[tuple] = set()
    spent = asked = 0
    for item in distinct_items(a.item for a in atoms):
        mine = [a for a in atoms if a.item == item]
        keys = keys_of(mine, makers) - paid
        if spent + sum(priced[k] for k in keys) <= tokens and asked + sum(priced[k] > 0 for k in keys) <= calls:
            kept += mine
            paid |= keys
            spent, asked = spent + sum(priced[k] for k in keys), asked + sum(priced[k] > 0 for k in keys)
            continue
        if not kept:
            for a in mine:
                own = keys_of([a], makers) - paid
                cost, new = sum(priced[k] for k in own), sum(priced[k] > 0 for k in own)
                if kept and (spent + cost > tokens or asked + new > calls):
                    break
                kept.append(a)
                paid |= own
                spent, asked = spent + cost, asked + new
        break
    return kept


def plan(
    llm: LLM, index: Retriever, atoms: list[AtomicRequirement], makers: list[str], views: dict,
    token_budget: int = TOKEN_BUDGET, depths: tuple[int, ...] = (TOP_K, max(1, TOP_K // 2)),
) -> Plan:
    """What can be evaluated within the budget: everything at full depth if it fits, else everything shallower, else the first requirements of the tender shallower."""
    calls = max(1, getattr(llm, "max_calls", MAX_CALLS) - getattr(llm, "calls", 0) - RESERVED_CALLS)
    for depth in depths:
        priced = prices(llm, index, atoms, makers, views, depth)
        kept = atoms_within(atoms, makers, priced, token_budget, calls)
        if len(kept) == len(atoms):
            break
    asked = [priced[k] for k in keys_of(kept, makers)]
    notes = []
    if depth < depths[0]:
        notes.append(
            f"This tender is large, so to keep the cost down each question was answered from the best {depth} passages instead of {depths[0]}. "
            "A requirement stated only on a lower-ranked page may be reported as missing."
        )
    if len(kept) < len(atoms):
        items = distinct_items(a.item for a in atoms)
        whole = [i for i in items if all(a in kept for a in atoms if a.item == i)]
        partial = [i for i in items if i not in whole and any(a in kept for a in atoms if a.item == i)]
        left = [i.title for i in items if i not in whole and i not in partial]
        notes.append(
            f"This tender is larger than the cost budget allows, so only part of it was evaluated: {len(whole)} of {len(items)} items in full"
            + (f", and for the item '{partial[0].title}' only its first {sum(a.item == partial[0] for a in kept)} of {sum(a.item == partial[0] for a in atoms)} requirements, "
               "so that item's score rests on those alone" if partial else "")
            + ". "
            + (f"These items were not evaluated and are in no score or count: {'; '.join(left[:LISTED])}{f'; and {len(left) - LISTED} more' if len(left) > LISTED else ''}. " if left else "")
            + "Raise TENDER_TOKEN_BUDGET to evaluate more."
        )
    return Plan(atoms=kept, depth=depth, notes=notes, questions=sum(t > 0 for t in asked), tokens=sum(asked))
