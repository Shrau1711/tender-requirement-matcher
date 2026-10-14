from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.atomize import AtomicRequirement, atomize_items
from app.services.by_product import best_product
from app.services.corpus import load_chunks, manufacturers
from app.services.evidence import Evidence, evidence_table
from app.services.llm import LLM
from app.services.match import Outcome, match_all
from app.services.measure import load_aliases
from app.services.ocr import ImageReader
from app.services.pdf_reader import read_pdf
from app.services.products import canonical_table
from app.services.queries import load_unit_views
from app.services.search import Index
from app.services.tender import read_requirements


@dataclass
class Gathered:
    """Everything found for a tender, before any scoring."""

    atoms: list[AtomicRequirement]
    makers: list[str]
    table: dict[tuple[int, str], list[Evidence]]  # evidence for (requirement position, manufacturer)
    readable: set[str]  # manufacturers whose documents gave some text
    covers: dict[str, list[str]]  # each manufacturer's cover headings, which say what its main product line is


def read_atoms(llm: LLM, tender: str | Path) -> list[AtomicRequirement]:
    """The tender's first item, split into single checkable requirements."""
    _, _, atoms = next(atomize_items(llm, read_requirements(read_pdf(tender))))  # first item only
    return atoms


def gather(llm: LLM, tender: str | Path, category_dir: str | Path, read_image: ImageReader | None = None) -> Gathered:
    """Read the tender and the manufacturers' documents, and find the evidence for every requirement.

    read_image reads the pages of the manufacturers' documents that are only pictures.
    """
    chunks = load_chunks(category_dir, read_image)
    atoms = read_atoms(llm, tender)
    makers = manufacturers(category_dir)
    table = evidence_table(llm, Index(chunks), atoms, makers, load_unit_views())
    covers = {c.manufacturer: c.document_headings for c in chunks}
    return Gathered(atoms, makers, table, set(covers), covers)


def score(found: Gathered) -> list[Outcome]:
    """One outcome per requirement and manufacturer, taking the best evidence for each requirement on its own."""
    return match_all(found.atoms, found.makers, found.table, load_aliases(), found.readable)


def score_by_product(llm: LLM, found: Gathered) -> dict[str, tuple[str | None, list[Outcome]]]:
    """For each manufacturer, its single best product and that product's outcomes."""
    table = canonical_table(llm, found.table, found.makers, found.covers)
    aliases = load_aliases()
    return {m: best_product(found.atoms, m, table, aliases, m in found.readable) for m in found.makers}


def match_tender(
    llm: LLM, tender: str | Path, category_dir: str | Path, read_image: ImageReader | None = None
) -> tuple[list[AtomicRequirement], list[str], list[Outcome]]:
    """Everything from tender and manufacturer documents to one outcome per requirement and manufacturer."""
    found = gather(llm, tender, category_dir, read_image)
    return found.atoms, found.makers, score(found)