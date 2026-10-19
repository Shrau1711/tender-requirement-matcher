"""Say, for free, what matching each tender in a folder would cost now: how many questions the cache already answers and how many are new.

Usage: python -m scripts.coverage <tenders dir> <categories dir>
Reading a tender is cached; every question about a manufacturer's documents is counted, never asked.
"""
import sys
from pathlib import Path

from app.services.bid_details import category_of
from app.services.corpus import load_chunks, manufacturers
from app.services.evidence import evidence_table
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import read_atoms
from app.services.queries import load_unit_views
from app.services.search import Index
from scripts.estimate_cost import CHARS_PER_TOKEN, DryRun


def main(tenders_dir: str, categories_dir: str) -> None:
    llm = make_llm()
    read_image = reader_for(llm)
    for tender in sorted(p for p in Path(tenders_dir).iterdir() if p.is_dir()):
        atoms, _ = read_atoms(llm, tender, read_image)
        category = category_of(" ".join(a.item.title for a in atoms))
        folder = Path(categories_dir) / (category or "")
        if not category or not folder.exists():
            print(f"{tender.name}: no category folder for '{category or 'unknown'}'")
            continue
        dry = DryRun(llm)
        evidence_table(dry, Index(load_chunks(str(folder), read_image)), atoms, manufacturers(str(folder)), load_unit_views())
        new = [chars for cached, chars in dry.asked if not cached]
        print(f"{tender.name} ({category}): {len(dry.asked)} questions, {len(new)} new, about {sum(new) // CHARS_PER_TOKEN:,} input tokens")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
