"""Why was a page the person cited not among the passages the model read? No model call.

For each such page it prints where the search ranked its best passage (among all of that maker's passages), the passage the
search put first instead, and the start of the cited passage, so a ranking problem (rank 9 to 60: read more, or search better)
can be told from a text problem (the page's words never reach the search).

Usage: python -m scripts.diagnose.why_not_read <tender folder or pdf> <category_dir>
"""
import sys
from pathlib import Path

from app.chunking.corpus import load_chunks
from app.evaluation.gold import GOLD_DIR, cited, load_gold
from app.extraction.evidence import retrieve
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for
from app.retrieval.queries import load_unit_views, queries_for
from app.retrieval.search import Hit, Index

SNIPPET = 150


def snippet(hit: Hit) -> str:
    return " ".join(hit.chunk.text.split())[:SNIPPET]


def main(tender: str, category_dir: str) -> None:
    gold = load_gold(GOLD_DIR / f"{Path(tender).stem}.json")
    llm = make_llm()
    read_image = reader_for(llm)
    atoms, _ = read_atoms(llm, tender, read_image)
    index, views = Index(load_chunks(category_dir, read_image)), load_unit_views()
    for a, key, maker, pages in cited(gold, atoms):
        if pages & {h.chunk.pdf_page for h in retrieve(index, a, maker, views)}:
            continue
        ranking = index.search_many(queries_for(a, views), maker, len(index.chunks))
        at = next(((r, h) for r, h in enumerate(ranking, 1) if h.chunk.pdf_page in pages), None)
        print(f"\n{key} / {maker}  (cited pages {sorted(pages)})")
        print(f"  asked: {a.attribute} {a.values} {a.unit or ''}")
        print(f"  first ranked: p{ranking[0].chunk.pdf_page} {snippet(ranking[0])}" if ranking else "  nothing ranked")
        if at:
            print(f"  cited page ranked {at[0]} of {len(ranking)}, p{at[1].chunk.pdf_page} {at[1].chunk.kind}: {snippet(at[1])}")
        else:
            print("  the cited page has no passage of its own in the search")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
