"""Show what the model said about one manufacturer and requirement, and why each finding was kept or dropped.

Usage: python -m scripts.show_reading <tender folder or pdf> <category_dir> <manufacturer> <attribute>

When several items have the attribute, the first item's requirement is shown.
"""
import sys

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
from app.services.pipeline import read_atoms
from app.services.queries import load_unit_views
from app.services.search import Index


def main(tender: str, category_dir: str, manufacturer: str, attribute: str) -> None:
    llm, views = make_llm(), load_unit_views()
    read_image = reader_for(llm)
    index = Index(load_chunks(category_dir, read_image))
    atoms, _ = read_atoms(llm, tender, read_image)
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
