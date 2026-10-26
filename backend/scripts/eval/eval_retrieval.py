"""Score the search index against hand-labelled queries.

Each case says: for this query and manufacturer, a correct chunk is on one of these pages.
A case passes if any of the top results comes from one of them. The first result is counted too, because on a short
document almost any search finds the right page somewhere in the top 5.

Usage: python -m scripts.eval.eval_retrieval <category_dir> <cases.json> [chunking strategy or auto]
"""
import json
import sys
from pathlib import Path

from app.chunking.corpus import load_chunks
from app.chunking.router import CHUNKER
from app.retrieval.search import Index, Mode

MODES: list[Mode] = ["keyword", "meaning", "hybrid"]
TOP_K = 5


# How far down the results the first right page is (1 is first), or None if it is not in the top TOP_K.
def rank(index: Index, case: dict, mode: Mode) -> int | None:
    hits = index.search(case["query"], case["manufacturer"], TOP_K, mode)
    return next((i for i, h in enumerate(hits, start=1) if h.chunk.pdf_page in case["pages"]), None)


def main(category_dir: str, cases_file: str, chunker: str = CHUNKER) -> None:
    cases = json.loads(Path(cases_file).read_text(encoding="utf-8"))
    index = Index(load_chunks(category_dir, chunker=chunker))
    ranks = {m: [] for m in MODES}
    print(f"{'query':45} {'maker':11}" + "".join(f"{m:>9}" for m in MODES))
    for case in cases:
        found = {m: rank(index, case, m) for m in MODES}
        for m in MODES:
            ranks[m].append(found[m])
        print(f"{case['query']:45} {case['manufacturer']:11}" + "".join(f"{found[m] or 'NO':>9}" for m in MODES))
    print(f"\nfound in top {TOP_K}: " + ", ".join(f"{m} {sum(r is not None for r in ranks[m])}/{len(cases)}" for m in MODES))
    print("found first: " + ", ".join(f"{m} {ranks[m].count(1)}/{len(cases)}" for m in MODES))


if __name__ == "__main__":
    main(*sys.argv[1:4])
