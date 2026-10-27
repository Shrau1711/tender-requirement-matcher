"""Score every labelled tender against its answer key and write one evaluation report.

Each answer key in data/eval/gold is matched to the tender folder of the same name, and the tender's category (pumps, valves, ...)
is read from what it buys, so a new labelled tender needs no change here.

Usage: python -m scripts.eval.eval_all <tenders dir> <categories dir> [output file]
"""
import sys
from pathlib import Path

from app.evaluation.evaluation import to_markdown
from app.evaluation.gold import answer_keys
from app.evaluation.rows import score_against_key
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import match_tender, read_atoms
from app.reading.ocr import reader_for
from app.tender.bid_details import category_of


def main(tenders_dir: str, categories_dir: str, out: str = "reports/evaluation.md") -> None:
    llm = make_llm()
    read_image = reader_for(llm)
    by_tender = {}
    for gold_file in answer_keys():
        tender = Path(tenders_dir) / gold_file.stem
        if not tender.exists():
            print(f"skipped {gold_file.stem}: no tender folder in {tenders_dir}")
            continue
        atoms, _ = read_atoms(llm, tender, read_image)
        category = category_of(" ".join(a.item.title for a in atoms))
        if not category or not (Path(categories_dir) / category).exists():
            print(f"skipped {gold_file.stem}: no category folder for '{category or 'unknown'}'")
            continue
        _, _, outcomes = match_tender(llm, tender, Path(categories_dir) / category, read_image)
        by_tender[gold_file.stem], _ = score_against_key(outcomes, gold_file.stem)
        print(f"scored {gold_file.stem} ({category}): {len(by_tender[gold_file.stem])} labelled rows")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(to_markdown(by_tender), encoding="utf-8")
    print(f"\nWrote {out}\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
