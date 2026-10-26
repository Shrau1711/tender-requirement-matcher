from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from app.config import number_setting
from app.extraction.atomize import AtomicRequirement
from app.llm.llm import LLM, ask
from app.llm.parallel import run_parallel
from app.retrieval.queries import queries_for
from app.retrieval.search import Hit, Index, tokenize
from app.vocabulary.terms import candidates

TOP_K = number_setting("EVIDENCE_TOP_K", 16)  # passages read per requirement and manufacturer: fewer is cheaper, more is thorough
SCATTER = number_setting("EVIDENCE_QUOTE_SCATTER", 40)  # other words allowed between the first and last word of a quote that joins a table heading to its cell
RESCUED = number_setting("EVIDENCE_RESCUED", 3)  # more passages read because they say the requirement's own words and numbers, wherever the search ranked them

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
    """True when the quote's words stand in the passage in that order, close together.

    Spacing and table separators ("|", ";", ">") are not words, so a model that rejoins the cells of a table row has still quoted it faithfully.
    A table quote may join a column heading to its cell ("Speed [rpm] 2900-2900") with other cells between them in the text, so the words may be a little apart,
    but never out of order, never missing, and never spread over more than a short stretch. Every word and number must match exactly, so an identifier can never be 'close enough'.
    """
    words, have = tokenize(quote), tokenize(text)
    if not words:
        return False
    reach = len(words) + SCATTER
    for start in (i for i, w in enumerate(have) if w == words[0]):
        at = start
        for w in words[1:]:
            at = next((j for j in range(at + 1, min(len(have), start + reach)) if have[j] == w), -1)
            if at < 0:
                break
        else:
            return True
    return False


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


def rejected(finding: Finding, hits: list[Hit]) -> str | None:
    """Why a finding is set aside, or None when it stands."""
    if finding.same_product_type == "no":
        return "about another type of product"
    if not 0 <= finding.passage < len(hits):
        return "cites a passage that does not exist"
    if not is_verbatim(finding.quote, hits[finding.passage].chunk.text):
        return "quote is not word for word in the passage"
    return None


def find_evidence(llm: LLM, req: AtomicRequirement, hits: list[Hit]) -> list[Evidence]:
    """What the given chunks state about the requirement.

    Dropped: findings whose quote is not in the cited chunk, and statements about another type of product.
    """
    hits = usable(req, hits)
    if not hits:
        return []
    found = ask(llm, SYSTEM, passages_prompt(req, hits), Found).findings
    checked = [f for f in found if rejected(f, hits) is None]
    return unique([
        Evidence(
            manufacturer=hits[f.passage].chunk.manufacturer, file=hits[f.passage].chunk.file,
            pdf_page=hits[f.passage].chunk.pdf_page, ocr=hits[f.passage].chunk.ocr,
            **f.model_dump(exclude={"passage"}),
        )
        for f in checked
    ])


def retrieve(
    index: Index, req: AtomicRequirement, manufacturer: str, views: dict[str, list[dict]], rescue: bool = True, depth: int = TOP_K
) -> list[Hit]:
    """The chunks of one manufacturer most likely to state the requirement.

    The search ranks by keyword and meaning together. Then a plain scan adds the passages that say the requirement's own words
    and numbers but were ranked too low to be read, so a passage worded unexpectedly is not lost.
    """
    hits = index.search_many(queries_for(req, views), manufacturer, depth)
    if not rescue or req.kind == "standard":  # an identifier is found by the keyword search or not at all
        return hits
    shown = {(h.chunk.file, h.chunk.pdf_page, h.chunk.text) for h in hits}
    own = [c for c in index.chunks if c.manufacturer == manufacturer]
    extra = [c for c in candidates(req, own, RESCUED + len(hits)) if (c.file, c.pdf_page, c.text) not in shown][:RESCUED]
    return hits + [Hit(score=0.0, keyword=0.0, meaning=0.0, chunk=c) for c in extra]


def question(req: AtomicRequirement) -> tuple:
    """What a requirement asks of a manufacturer, whichever item it belongs to."""
    return req.attribute, req.kind, req.operator, tuple(req.values), req.unit, req.source_name, req.source_value


def question_jobs(atoms: list[AtomicRequirement], makers: list[str]) -> tuple[list[tuple[int, str]], dict[tuple, int]]:
    """Every (requirement position, manufacturer) that needs evidence, and the first position that asks each distinct question of a manufacturer."""
    pairs = [(i, m) for i, a in enumerate(atoms) if a.evidence == "product" for m in makers]
    first: dict[tuple, int] = {}
    for i, m in pairs:
        first.setdefault((question(atoms[i]), m), i)
    return pairs, first


def evidence_table(
    llm: LLM, index: Index, atoms: list[AtomicRequirement], makers: list[str], views: dict[str, list[dict]], depth: int = TOP_K
) -> dict[tuple[int, str], list[Evidence]]:
    """Evidence for every product requirement and manufacturer, keyed by (position of the requirement, manufacturer).

    A requirement that several items share is looked up once per manufacturer, not once per item. depth is how many passages are read per question.
    """
    pairs, first = question_jobs(atoms, makers)
    jobs = list(first.items())
    searched = [(atoms[i], retrieve(index, atoms[i], m, views, depth=depth)) for (_, m), i in jobs]  # searching is quick, so one at a time
    found = dict(zip(first, run_parallel(lambda job: find_evidence(llm, *job), searched), strict=True))  # reading is slow, so all at once
    return {(i, m): found[question(atoms[i]), m] for i, m in pairs}
