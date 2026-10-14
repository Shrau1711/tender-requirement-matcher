"""Show what the model said about one manufacturer and requirement, and why each finding was kept or dropped.

Usage: python -m scripts.show_reading <tender.pdf> <category_dir> <manufacturer> <attribute>
"""
import sys

from app.services.atomize import atomize_items
from app.services.corpus import load_chunks
from app.services.evidence import (
    SYSTEM,
    Found,
    is_verbatim,
    passages_prompt,
    retrieve,
    usable,
)
from app.services.llm import ask
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pdf_reader import read_pdf
from app.services.queries import load_unit_views
from app.services.search import Index
from app.services.tender import read_requirements


def main(tender: str, category_dir: str, manufacturer: str, attribute: str) -> None:
    llm, views = make_llm(), load_unit_views()
    index = Index(load_chunks(category_dir, reader_for(llm)))
    _, _, atoms = next(atomize_items(llm, read_requirements(read_pdf(tender))))  # first item only
    req = next(a for a in atoms if a.attribute == attribute)
    hits = usable(req, retrieve(index, req, manufacturer, views))
    found = ask(llm, SYSTEM, passages_prompt(req, hits), Found).findings
    print(f"{len(hits)} passages given, {len(found)} findings returned")
    for f in found:
        in_range = 0 <= f.passage < len(hits)
        quoted = in_range and is_verbatim(f.quote, hits[f.passage].chunk.text)
        kept = quoted and f.same_product_type != "no"
        print(f"\n{'KEPT' if kept else 'DROPPED'}: passage {f.passage} [{f.product}] same_product_type={f.same_product_type} quote_in_passage={quoted}")
        print(f"  stated: {f.stated}\n  quote:  {f.quote!r}\n  read:   {f.shape} {f.numbers} unit={f.unit}")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:5])