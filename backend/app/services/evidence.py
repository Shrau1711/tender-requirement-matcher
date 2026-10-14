from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from app.config import number_setting
from app.services.atomize import AtomicRequirement
from app.services.llm import LLM, ask
from app.services.parallel import run_parallel
from app.services.queries import queries_for
from app.services.search import Hit, Index

TOP_K = number_setting("EVIDENCE_TOP_K", 8)  # passages read per requirement and manufacturer: fewer is cheaper, more is thorough

SYSTEM = """You read passages from one manufacturer's documents and report what they state about one attribute.
Rules:
- Report only what a passage states. Never compare with the buyer's need and never judge whether it is enough.
- "stated" is the value as printed, with its unit. One finding per distinct statement.
- "product" is the product or product family the statement is about, as the passage names it (for example "BOAX-B butterfly valve" or "wafer dual plate check valve"). If the passage does not say, write "unclear".
- Each passage comes with "page_headings", the bold headings printed on its page. When the passage itself does not name its product, use the headings to tell which product the page is about. If the headings name several products and you cannot tell which one the passage belongs to, the product is "unclear".
- Each passage also comes with "document_headings", the headings of the document's first page (its cover). Use them only when neither the passage nor its page headings name the product: if the document headings name exactly one product or product range, that is the product. If they name no product, or several, the product is "unclear".
- "same_product_type" says whether that product is the same type of product as buyer_product: "yes", "no", or "unclear" if neither the passage nor the headings name the product. A check valve is not a butterfly valve.
- "quote" is copied word for word from the passage, as short as possible while still showing the statement. Never reword it.
- "passage" is the number of the passage the quote comes from.
- Report a passage if it states the wanted attribute (the passage may word it differently, for example "Operation: Lever" for handle type) or mentions one of the wanted values. A different attribute, or a list of industries, is not a match.
- A value printed in another unit than the wanted one is still a finding (for example "BARG: 20" or "PSIG: 175" for a wanted pressure in MPa, or inches for a wanted size in mm). Report it as printed; the comparison and any conversion are done afterwards, not by you.
- A wanted value may be an abbreviation (BW for butt weld, SS for stainless steel). A passage that writes it out in full states the same thing, so report it.
- If no passage qualifies, return an empty list. Do not guess.
Reading the statement into parts (copy what is printed, never convert units or calculate):
- "shape": "single" for one value, "options" for a list of alternatives (PN 10/16), "range" for from-to (40mm to 500mm), "up_to" for a maximum (Upto PN16), "at_least" for a minimum, "text" for words that are not numbers.
- "numbers": the numbers that are values of the attribute, as printed. A range gives its two ends. Leave empty for text.
- "unit": the unit or prefix printed with the numbers, such as mm, NB, DN, bar, PN, MPa, Class. "PN 16" has the unit PN. Null only when nothing is printed with the number.
- "items": for text statements, the separate options, such as ["Wafer", "Lugged", "Double Flanged"]. Empty for numbers.
- "condition": a limit the statement applies only under, such as "DN 40 - 600". Null if there is none. When one statement gives different values under different conditions, report each as its own finding with its own condition and quote.
- "condition_limit": when the condition is a number or a range of numbers (DN 40 - 600, 65 NB to 1200 NB, Upto PN10), read it like a value: its "shape", its "numbers" and its "unit". Null when the condition is words, such as "Dry Shaft" or "for vacuum levels".
"""


Shape = Literal["single", "options", "range", "up_to", "at_least", "text"]


class Limit(BaseModel):
    """A condition that is a number or range, such as "DN 40 - 600", read into parts."""

    shape: Shape
    numbers: list[float]
    unit: str | None = None


class Reading(BaseModel):
    """A stated value read into parts, so plain code can compare it."""

    shape: Shape = "text"
    numbers: list[float] = []
    unit: str | None = None
    items: list[str] = []
    condition: str | None = None
    condition_limit: Limit | None = None


class Finding(Reading):
    passage: int
    stated: str
    product: str
    same_product_type: Literal["yes", "no", "unclear"]
    quote: str


class Found(BaseModel):
    findings: list[Finding]


class Evidence(Reading):
    manufacturer: str
    file: str
    pdf_page: int
    stated: str
    product: str
    same_product_type: Literal["yes", "unclear"]
    quote: str
    ocr: bool = False  # the quote is from text the model read off a picture of the page


def passages_prompt(req: AtomicRequirement, hits: list[Hit]) -> str:
    wanted = {"attribute": req.attribute, "values": req.values, "buyer_text": f"{req.source_name}: {req.source_value}"}
    passages = [{"passage": i, "page": h.chunk.pdf_page, "page_headings": h.chunk.page_headings, "document_headings": h.chunk.document_headings, "text": h.chunk.text} for i, h in enumerate(hits)]
    return json.dumps({"buyer_product": req.item.title, "attribute_wanted": wanted, "passages": passages})


def squash(text: str) -> str:
    return " ".join(text.split()).lower()


def is_verbatim(quote: str, text: str) -> bool:
    """True when the quote really appears in the passage. Exact match, so identifiers can never be 'close enough'."""
    return bool(quote.strip()) and squash(quote) in squash(text)


def usable(req: AtomicRequirement, hits: list[Hit]) -> list[Hit]:
    """A standard's identifier either appears in the text or it does not, so only chunks containing it are worth reading."""
    return [h for h in hits if h.keyword > 0] if req.kind == "standard" else hits


def unique(found: list[Evidence]) -> list[Evidence]:
    """The same statement quoted from several rows of one page counts once."""
    seen: set[tuple[int, str, str, str | None]] = set()
    kept = []
    for e in found:
        if (e.pdf_page, e.stated, e.product, e.condition) not in seen:
            seen.add((e.pdf_page, e.stated, e.product, e.condition))
            kept.append(e)
    return kept


def find_evidence(llm: LLM, req: AtomicRequirement, hits: list[Hit]) -> list[Evidence]:
    """What the given chunks state about the requirement.

    Dropped: findings whose quote is not in the cited chunk, and statements about another type of product.
    """
    hits = usable(req, hits)
    if not hits:
        return []
    found = ask(llm, SYSTEM, passages_prompt(req, hits), Found).findings
    checked = [
        f for f in found
        if f.same_product_type != "no" and 0 <= f.passage < len(hits) and is_verbatim(f.quote, hits[f.passage].chunk.text)
    ]
    return unique([
        Evidence(
            manufacturer=hits[f.passage].chunk.manufacturer, file=hits[f.passage].chunk.file,
            pdf_page=hits[f.passage].chunk.pdf_page, ocr=hits[f.passage].chunk.ocr,
            **f.model_dump(exclude={"passage"}),
        )
        for f in checked
    ])


def retrieve(
    index: Index, req: AtomicRequirement, manufacturer: str, views: dict[str, list[dict]]
) -> list[Hit]:
    """The chunks of one manufacturer most likely to state the requirement."""
    return index.search_many(queries_for(req, views), manufacturer, TOP_K)


def question(req: AtomicRequirement) -> tuple:
    """What a requirement asks of a manufacturer, whichever item it belongs to."""
    return req.attribute, req.kind, req.operator, tuple(req.values), req.unit, req.source_name, req.source_value


def evidence_table(
    llm: LLM, index: Index, atoms: list[AtomicRequirement], makers: list[str], views: dict[str, list[dict]]
) -> dict[tuple[int, str], list[Evidence]]:
    """Evidence for every product requirement and manufacturer, keyed by (position of the requirement, manufacturer).

    A requirement that several items share is looked up once per manufacturer, not once per item.
    """
    pairs = [(i, m) for i, a in enumerate(atoms) if a.evidence == "product" for m in makers]
    first: dict[tuple, int] = {}
    for i, m in pairs:
        first.setdefault((question(atoms[i]), m), i)
    jobs = list(first.items())
    searched = [(atoms[i], retrieve(index, atoms[i], m, views)) for (_, m), i in jobs]  # searching is quick, so one at a time
    found = dict(zip(first, run_parallel(lambda job: find_evidence(llm, *job), searched), strict=True))  # reading is slow, so all at once
    return {(i, m): found[question(atoms[i]), m] for i, m in pairs}
