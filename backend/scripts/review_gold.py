"""List the rows of a drafted answer key that a person should check by hand, without drafting again.

Usage: python -m scripts.review_gold <tender folder or pdf> <category_dir> [number of agreeing rows to spot-check]
Reads the existing sheet in data/eval/gold and the (cached) pipeline results; writes reports/draft_review.md.
"""
import random
import sys
from pathlib import Path

from app.services.gold import GOLD_DIR, compare, load_gold
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import match_tender


def main(tender: str, category_dir: str, spot_checks: str = "12") -> None:
    path = GOLD_DIR / f"{Path(tender).stem}.json"
    if not path.exists():
        sys.exit(f"{path} does not exist; draft it first with scripts.draft_gold")
    gold = load_gold(path)
    llm = make_llm()
    _, _, outcomes = match_tender(llm, tender, category_dir, reader_for(llm))
    rows = compare(outcomes, gold)
    notes = {(key, m): label.note for key, labels in gold.items() for m, label in labels.items()}
    disagree = [r for r in rows if not r.agrees]
    unverified = [r for r in rows if r.agrees and "UNVERIFIED" in notes.get((r.attribute, r.manufacturer), "")]
    agree = [r for r in rows if r.agrees and r not in unverified]
    sample = random.Random(0).sample(agree, min(int(spot_checks), len(agree)))
    lines = ["# Rows to check by hand", "", f"{len(rows)} rows drafted; {len(disagree)} disagree with the pipeline, {len(unverified)} agree but quote nothing verifiable, {len(sample)} agreeing rows sampled.", ""]
    for title, group in (("Disagreements: the draft or the pipeline is wrong", disagree), ("Agreeing, but the quote was not found in the document", unverified), ("Spot checks of agreeing rows", sample)):
        lines += [f"## {title}", ""]
        lines += [f"- {r.attribute} / {r.manufacturer}: draft {r.gold} (pages {r.gold_pages}), pipeline {r.ours} {r.score} (page {r.our_page}). {notes.get((r.attribute, r.manufacturer), '')}" for r in group] or ["- none"]
        lines.append("")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/draft_review.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote reports/draft_review.md\n{len(rows)} rows: {len(disagree)} disagree, {len(unverified)} unverified, {len(sample)} spot checks\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
