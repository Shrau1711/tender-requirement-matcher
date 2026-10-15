"""Copy your hand-checked labels to the identical requirement of the tender's other products, so each is checked once.

Usage: python -m scripts.mirror_gold <tender folder or pdf> <category_dir>
Only copies where the requirement is word for word the same; never overwrites a row you have already checked.
"""
import sys
from pathlib import Path

from app.services.gold import GOLD_DIR, load_gold, mirror, save_gold
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import read_atoms


def main(tender: str, category_dir: str) -> None:
    path = GOLD_DIR / f"{Path(tender).stem}.json"
    gold = load_gold(path)
    llm = make_llm()
    atoms, _ = read_atoms(llm, tender, reader_for(llm))
    copied = mirror(gold, atoms)
    save_gold(gold, path)
    for source, target, maker in copied:
        print(f"{maker}: {source}  ->  {target}")
    print(f"copied {len(copied)} labels into {path.name}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
