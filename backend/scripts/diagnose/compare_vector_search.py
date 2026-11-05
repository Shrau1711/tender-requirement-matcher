"""Compare Chroma's own ranking (VECTOR_SEARCH=chroma) with the exact NumPy ranking (exact, the default). No model calls.

Usage: python -m scripts.diagnose.compare_vector_search [report.json]

The catalogues are read as a run reads them, pictures of pages included, but only from saved transcriptions (no model
can be asked). For both categories, the same 127 queries as the default-results fingerprint (the 7 retrieval cases and the first 120
catalogue headings), for every manufacturer, in each search mode (keyword, meaning, hybrid): the 16 passages a question
reads (EVIDENCE_TOP_K) are compared, and so is the whole meaning ranking of the manufacturer's chunks. Every query whose
results differ is listed, with the first place they differ and the passage each search put there.
"""
import json
import sys
from pathlib import Path

from app.categories.config import CATEGORIES_DIR
from app.llm.llm_factory import saved_answers_only
from app.reading.ocr import reader_for
from app.retrieval.search import Index
from app.vectorstore.ingest import ingest, open_store

CASES = json.loads((CATEGORIES_DIR.parent / "eval" / "retrieval_cases.json").read_text(encoding="utf-8"))
TOP_K = 16
MODES = ("keyword", "meaning", "hybrid")


def queries_for(chunks) -> list[str]:
    return [c["query"] for c in CASES] + sorted({h for c in chunks for h in c.page_headings})[:120]


def main(out: str = "reports/vector_search_comparison.json") -> None:
    store = open_store("chroma")
    read_image = reader_for(saved_answers_only())
    report = {"compared": 0, "differ": [], "full_rankings_compared": 0, "full_rankings_differ": 0, "missing_from_chroma": {}}
    for category in ("valves", "pumps"):
        chunks = ingest(CATEGORIES_DIR / category, store, read_image)
        exact, native = (Index(chunks, store=store, category=category, scoring=s) for s in ("exact", "chroma"))
        makers = sorted({c.manufacturer for c in chunks})
        for q in queries_for(chunks):
            for maker in makers:
                a, b = exact.meanings([q], maker)[0], native.meanings([q], maker)[0]
                ranked_a = sorted(a, key=lambda i: (-a[i], i))
                report["full_rankings_compared"] += 1
                if list(b) != ranked_a:
                    report["full_rankings_differ"] += 1
                missing = set(a) - set(b)
                if missing:
                    key = f"{category}/{maker}"
                    report["missing_from_chroma"].setdefault(key, sorted({chunks[i].file + f" page {chunks[i].pdf_page}" for i in missing}))
                for mode in MODES:
                    hits_a = [(h.chunk.file, h.chunk.pdf_page, h.chunk.text[:60]) for h in exact.search_many([q], maker, TOP_K, mode)]
                    hits_b = [(h.chunk.file, h.chunk.pdf_page, h.chunk.text[:60]) for h in native.search_many([q], maker, TOP_K, mode)]
                    report["compared"] += 1
                    if hits_a != hits_b:
                        first = next((n for n, (x, y) in enumerate(zip(hits_a, hits_b)) if x != y), min(len(hits_a), len(hits_b)))
                        report["differ"].append({"category": category, "maker": maker, "mode": mode, "query": q, "first_place": first + 1,
                                                 "exact": hits_a[first] if first < len(hits_a) else None,
                                                 "chroma": hits_b[first] if first < len(hits_b) else None})
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    by_mode = {m: sum(d["mode"] == m for d in report["differ"]) for m in MODES}
    print(f"top-{TOP_K} results compared: {report['compared']}; differ: {len(report['differ'])} {by_mode}")
    print(f"whole meaning rankings compared: {report['full_rankings_compared']}; differ: {report['full_rankings_differ']}")
    print(f"chunks Chroma never returned: {report['missing_from_chroma'] or 'none'}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
