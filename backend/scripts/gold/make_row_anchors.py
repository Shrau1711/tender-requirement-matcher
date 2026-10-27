"""Write <tender>.rows.json next to a labelled tender's answer key: which answer-key entries each tender row produced.

Usage: python -m scripts.gold.make_row_anchors <tender folder>

It must be made from the same reading the labels were made from, so it uses the saved reading of the default model and
asks no model: a tender whose reading is not saved stops with an error. It checks that every answer-key entry is produced
by some row. See app.evaluation.rows for how scoring uses it.
"""
import sys
from pathlib import Path

from app.evaluation.gold import GOLD_DIR, load_gold
from app.evaluation.rows import anchors_file, row_anchors, save_anchors
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for


def main(tender: str) -> None:
    llm = make_llm()
    llm.max_calls = 0  # the saved reading only: a new reading would not be the one the labels were made from
    atoms, _ = read_atoms(llm, tender, reader_for(llm))
    anchors = row_anchors(atoms)
    gold = load_gold(GOLD_DIR / f"{Path(tender).name}.json")
    missing = set(gold) - {k for keys in anchors.values() for k in keys}
    if missing:
        raise SystemExit(f"These answer-key entries come from no row of this reading: {sorted(missing)}")
    save_anchors(anchors, anchors_file(Path(tender).name))
    print(f"{len(anchors)} rows, {len(atoms)} requirements, all {len(gold)} answer-key entries covered: {anchors_file(Path(tender).name)}")


if __name__ == "__main__":
    main(sys.argv[1])
