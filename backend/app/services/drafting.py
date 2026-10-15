from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from app.services.atomize import AtomicRequirement
from app.services.evidence import is_verbatim, question
from app.services.gold import Gold, Label, has_several, key_for

Judged = Literal["fully matched", "partially matched", "missing capability"]
RANK = {"missing capability": 0, "partially matched": 1, "fully matched": 2}

SYSTEM = """You read one manufacturer document, in full, and judge what it states about each of a buyer's requirements. Your answers are a draft answer key that a person will check.
Rules:
- The document is marked page by page ("=== PAGE 12 ==="). Cite the page number from the marker.
- Judge only for the product in this document that is the same type of product as the buyer's product. If this document is about another type of product, answer "missing capability" for every requirement.
- "fully matched": the document states the requirement and what it states meets it (a wanted number inside a stated range or equal to a stated value; every part of a wanted description stated).
- "partially matched": the document states something relevant that does not fully settle it: a higher or lower figure, only some words of a description, a statement that applies only under a condition, or a similar but not identical thing.
- "missing capability": the document states nothing about it, or states something that does not meet it.
- "quote" is copied word for word from the cited page, as short as possible. Empty for "missing capability". Never reword it, never guess.
- "product" is the product the statement is about. "note" is one short sentence saying why.
- Answer every requirement id."""


class Answer(BaseModel):
    id: int
    status: Judged
    page: int | None = None
    quote: str = ""
    product: str = ""
    note: str = ""


class Drafted(BaseModel):
    answers: list[Answer]


class Draft(BaseModel):
    """One manufacturer's drafted label for one question, with where it came from."""

    status: Judged
    pages: list[int]
    file: str | None
    quote: str
    verified: bool  # the quote was found word for word in the document


def questions(atoms: list[AtomicRequirement]) -> list[AtomicRequirement]:
    """The distinct questions the tender asks of a catalogue, in order. Two items asking the same thing are one question."""
    seen, asked = set(), []
    for a in atoms:
        if a.evidence == "product" and question(a) not in seen:
            seen.add(question(a))
            asked.append(a)
    return asked


def document_prompt(titles: list[str], asked: list[AtomicRequirement], pages: list[tuple[int, str]]) -> str:
    wanted = [{"id": i, "attribute": a.attribute, "values": a.values, "unit": a.unit, "buyer_text": f"{a.source_name}: {a.source_value}"} for i, a in enumerate(asked)]
    text = "\n".join(f"=== PAGE {n} ===\n{body}" for n, body in pages)
    return json.dumps({"buyer_products": titles, "requirements": wanted, "document": text})


def check(answer: Answer, pages: dict[int, str]) -> tuple[Answer, bool]:
    """The answer with its page corrected when the quote is on another page, and whether the quote was found at all."""
    if answer.status == "missing capability":
        return answer, True
    if answer.page in pages and is_verbatim(answer.quote, pages[answer.page]):
        return answer, True
    elsewhere = next((n for n, body in pages.items() if is_verbatim(answer.quote, body)), None)
    return (answer.model_copy(update={"page": elsewhere}), True) if elsewhere else (answer, False)


def merge(found: list[tuple[str, Answer, bool]]) -> Draft:
    """The best of one manufacturer's answers across its documents: a checked answer beats an unchecked one, then the stronger status wins."""
    best = max(found, key=lambda f: (f[2], RANK[f[1].status]))
    file, answer, verified = best
    same = [a for f, a, v in found if v == verified and a.status == answer.status and a.page]
    return Draft(status=answer.status, pages=sorted({a.page for a in same}), file=file if answer.status != "missing capability" else None, quote=answer.quote, verified=verified)


def label_of(draft: Draft) -> Label:
    if draft.status == "missing capability":
        return Label(status=draft.status, note="AI-drafted: the documents state nothing that meets it")
    warning = "" if draft.verified else "UNVERIFIED QUOTE, check by hand. "
    return Label(status=draft.status, page=draft.pages or None, note=f'{warning}AI-drafted from a full read of {draft.file}: "{draft.quote}"')


def to_gold(atoms: list[AtomicRequirement], makers: list[str], drafts: dict[tuple[tuple, str], Draft]) -> Gold:
    """The drafted label sheet in the same shape a person fills in by hand."""
    several = has_several([a.item for a in atoms])
    gold: Gold = {}
    for a in atoms:
        if a.evidence != "product":
            continue
        row = gold.setdefault(key_for(a.item, a.attribute, several), {})
        for m in makers:
            if m not in row and (question(a), m) in drafts:
                row[m] = label_of(drafts[question(a), m])
    return gold
