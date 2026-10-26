"""Compare the pipeline's results with the gold labels (the answer key) and list every disagreement.

Usage: python -m scripts.eval.score_gold <tender folder or pdf> <category_dir>
"""
import sys
from pathlib import Path

from app.evaluation.gold import GOLD_DIR, compare, load_gold, share
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import match_tender
from app.reading.ocr import reader_for


def main(tender: str, category_dir: str) -> None:
    gold = load_gold(GOLD_DIR / f"{Path(tender).stem}.json")
    llm = make_llm()
    _, _, outcomes = match_tender(llm, tender, category_dir, reader_for(llm))
    rows = compare(outcomes, gold)
    for r in (r for r in rows if not r.agrees):
        print(f"\n{r.attribute} / {r.manufacturer}\n  gold label: {r.gold} (pages {r.gold_pages})\n  pipeline:   {r.ours} {r.score} (page {r.our_page})\n  because:    {r.reason}")
    both = [r for r in rows if r.gold != "missing capability" and r.ours != "missing capability"]
    for r in (r for r in both if not r.page_agrees):
        print(f"\n{r.attribute} / {r.manufacturer}: different page\n  gold label: pages {r.gold_pages}\n  pipeline:   page {r.our_page}")
    print(f"\nlabelled rows {len(rows)}")
    print(f"status agrees {share(sum(r.agrees for r in rows), len(rows))}")
    print(f"page agrees where both found something {share(sum(r.page_agrees for r in both), len(both))}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
