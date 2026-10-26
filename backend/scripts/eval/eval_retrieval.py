"""Score the search index against hand-labelled queries.

Each case says: for this query and manufacturer, a correct chunk is on one of these pages.
A case passes if any of the top results comes from one of them.

Usage: python -m scripts.eval.eval_retrieval <category_dir> <cases.json>
"""
import json
import sys
from pathlib import Path

from app.chunking.corpus import load_chunks
from app.retrieval.search import Index, Mode

MODES: list[Mode] = ["keyword", "meaning", "hybrid"]
TOP_K = 5


def passes(index: Index, case: dict, mode: Mode) -> bool:
    hits = index.search(case["query"], case["manufacturer"], TOP_K, mode)
    return any(h.chunk.pdf_page in case["pages"] for h in hits)


def main(category_dir: str, cases_file: str) -> None:
    cases = json.loads(Path(cases_file).read_text(encoding="utf-8"))
    index = Index(load_chunks(category_dir))
    totals = dict.fromkeys(MODES, 0)
    print(f"{'query':45} {'maker':11}" + "".join(f"{m:>9}" for m in MODES))
    for case in cases:
        results = {m: passes(index, case, m) for m in MODES}
        for m in MODES:
            totals[m] += results[m]
        print(f"{case['query']:45} {case['manufacturer']:11}" + "".join(f"{'yes' if results[m] else 'NO':>9}" for m in MODES))
    print(f"\nfound in top {TOP_K}: " + ", ".join(f"{m} {totals[m]}/{len(cases)}" for m in MODES))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])