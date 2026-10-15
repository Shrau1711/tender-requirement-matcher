"""Measure the search against the answer key without any model call: is a page the person cited among the passages the model is given to read?

Prints the share with and without the plain term scan that adds passages saying the requirement's own words and numbers.

Usage: python -m scripts.eval_candidates <tender folder or pdf> <category_dir>
"""
import sys
from pathlib import Path

from app.services.corpus import load_chunks
from app.services.evidence import retrieve
from app.services.gold import GOLD_DIR, cited, load_gold, share
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import read_atoms
from app.services.queries import load_unit_views
from app.services.search import Index


def main(tender: str, category_dir: str) -> None:
    gold = load_gold(GOLD_DIR / f"{Path(tender).stem}.json")
    llm = make_llm()
    read_image = reader_for(llm)
    atoms, _ = read_atoms(llm, tender, read_image)
    index, views = Index(load_chunks(category_dir, read_image)), load_unit_views()
    wanted = cited(gold, atoms)
    for rescue in (False, True):
        misses = [(key, maker, pages) for a, key, maker, pages in wanted
                  if not pages & {h.chunk.pdf_page for h in retrieve(index, a, maker, views, rescue)}]
        print(f"{'with' if rescue else 'without'} the term scan: a cited page is among the passages read for {share(len(wanted) - len(misses), len(wanted))}")
        for key, maker, pages in misses:
            print(f"    not read: {key} / {maker} (cited pages {sorted(pages)})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
