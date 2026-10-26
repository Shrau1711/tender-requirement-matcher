from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.chunking.corpus import load_chunks, manufacturers
from app.cost.budget import plan
from app.cost.estimate import Estimate, make_estimate
from app.extraction.atomize import AtomicRequirement, atomize_tender, contradictions
from app.extraction.evidence import Evidence, evidence_table
from app.extraction.products import canonical_table
from app.judging.by_product import best_products
from app.judging.match import Outcome, match_all
from app.judging.measure import load_aliases
from app.llm.llm import LLM
from app.reading.ocr import ImageReader
from app.reporting.report import Report, assemble
from app.retrieval.queries import load_unit_views
from app.retrieval.search import Index
from app.tender.items import Item
from app.tender.reader import read_tender


@dataclass
class Gathered:
    """Everything found for a tender, before any scoring."""

    atoms: list[AtomicRequirement]
    notes: list[str]  # how the tender was read: copies skipped, scanned pages, dropped requirements, items without requirements, files that contradict each other
    makers: list[str]
    table: dict[tuple[int, str], list[Evidence]]  # evidence for (requirement position, manufacturer)
    readable: set[str]  # manufacturers whose documents gave some text
    covers: dict[str, list[str]]  # each manufacturer's cover headings, which say what its main product line is


# Reads the tender and splits it into single checkable requirements, with notes on how it was read.
def read_atoms(llm: LLM, tender: str | Path, read_image: ImageReader | None = None) -> tuple[list[AtomicRequirement], list[str]]:
    """Every item of the tender split into single checkable requirements, and notes on how the tender was read.

    The tender is one PDF or a folder of PDFs. read_image reads the pages that are only pictures.
    """
    read = read_tender(llm, tender, read_image)
    atoms = atomize_tender(llm, read.requirements)
    return atoms, read.notes + contradictions(atoms)


# Reads the manufacturers' documents and the tender, estimates the cost (and asks the person if asked to), then finds
# evidence for every requirement. This is the only step that costs money.
def gather(
    llm: LLM, tender: str | Path, category_dir: str | Path, read_image: ImageReader | None = None, progress: Callable[[str], None] = lambda _: None,
    ask: Callable[[Estimate], None] | None = None,
) -> Gathered:
    """Read the tender and the manufacturers' documents, and find the evidence for every requirement.

    read_image reads the pages of the tender's and the manufacturers' documents that are only pictures. progress is told each stage as it starts.
    ask, if given, is shown what the search will cost before it is paid for, and stops the job by raising if the person says no.
    """
    progress("Reading the manufacturers' documents")
    chunks = load_chunks(category_dir, read_image)
    progress("Reading the tender and splitting it into requirements")
    atoms, notes = read_atoms(llm, tender, read_image)
    makers = manufacturers(category_dir)
    progress(f"Checking what reading the documents for {len(atoms)} requirements would cost")
    index, views = Index(chunks), load_unit_views()
    chosen = plan(llm, index, atoms, makers, views)
    if ask:
        ask(make_estimate(len(chosen.atoms), chosen.questions, chosen.tokens, notes + chosen.notes))
    progress(f"Searching the documents for evidence on {len(chosen.atoms)} requirements")
    table = evidence_table(llm, index, chosen.atoms, makers, views, chosen.depth)
    covers = {c.manufacturer: c.document_headings for c in chunks}
    return Gathered(chosen.atoms, notes + chosen.notes, makers, table, set(covers), covers)


# Judges the evidence in plain code: one outcome per requirement and manufacturer.
def score(found: Gathered) -> list[Outcome]:
    """One outcome per requirement and manufacturer, taking the best evidence for each requirement on its own."""
    return match_all(found.atoms, found.makers, found.table, load_aliases(), found.readable)


# For each manufacturer and item, picks the single best product and its outcomes.
def score_by_product(llm: LLM, found: Gathered) -> dict[str, list[tuple[Item, str | None, list[Outcome]]]]:
    """For each manufacturer and each item, its single best product and that product's outcomes."""
    table = canonical_table(llm, found.table, found.makers, found.covers)
    aliases = load_aliases()
    return {m: best_products(found.atoms, m, table, aliases, m in found.readable) for m in found.makers}


# Assembles the report: ranking, scores, statuses and the evidence behind each.
def build_report(llm: LLM, found: Gathered, tender: str) -> Report:
    """The report for a tender: ranking, scores, statuses and the evidence behind each. Costs only the model calls that grouping product names needs."""
    return assemble(tender, found.atoms, found.notes, found.makers, found.table, found.readable, score_by_product(llm, found), score(found))


# Everything from tender and documents to one outcome per requirement and manufacturer.
def match_tender(
    llm: LLM, tender: str | Path, category_dir: str | Path, read_image: ImageReader | None = None
) -> tuple[list[AtomicRequirement], list[str], list[Outcome]]:
    """Everything from tender and manufacturer documents to one outcome per requirement and manufacturer."""
    found = gather(llm, tender, category_dir, read_image)
    return found.atoms, found.makers, score(found)
