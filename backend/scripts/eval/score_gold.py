"""Compare the pipeline's results with the gold labels (the answer key) and list every disagreement.

Usage: python -m scripts.eval.score_gold <tender folder or pdf> <category_dir>

When the tender has a row anchors file, each requirement is matched to the answer key by the tender row it was read from
(see app.evaluation.rows), so a model that names a requirement differently is still scored on every labelled row.
"""
import sys
from pathlib import Path

from app.evaluation.gold import share
from app.evaluation.rows import score_against_key
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import match_tender
from app.reading.ocr import reader_for


def main(tender: str, category_dir: str) -> None:
    llm = make_llm()
    _, _, outcomes = match_tender(llm, tender, category_dir, reader_for(llm))
    rows, how = score_against_key(outcomes, Path(tender).stem)
    for r in (r for r in rows if not r.agrees):
        print(f"\n{r.attribute} / {r.manufacturer}\n  gold label: {r.gold} (pages {r.gold_pages})\n  pipeline:   {r.ours} {r.score} (page {r.our_page})\n  because:    {r.reason}")
    both = [r for r in rows if r.gold != "missing capability" and r.ours != "missing capability"]
    for r in (r for r in both if not r.page_agrees):
        print(f"\n{r.attribute} / {r.manufacturer}: different page\n  gold label: pages {r.gold_pages}\n  pipeline:   page {r.our_page}")
    print(f"\nlabelled rows {len(rows)}" + (f" (answer-key entries found by tender row {how['row']}, by name {how['name']})" if how else ""))
    print(f"status agrees {share(sum(r.agrees for r in rows), len(rows))}")
    print(f"page agrees where both found something {share(sum(r.page_agrees for r in both), len(both))}")
    print(llm.summary())  # what the run really cost: new calls and their tokens


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
