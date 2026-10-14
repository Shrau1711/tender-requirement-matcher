"""Write an empty label sheet for a tender, to be filled in by hand from the manufacturers' documents.

Usage: python -m scripts.make_gold <tender.pdf> <category_dir>
Fill in "status" (fully matched / partially matched / missing capability), "page" and "note" for each manufacturer.
Leave "status" as null for a manufacturer whose documents cannot be read. Never overwrites an existing sheet.
"""
import sys
from pathlib import Path

from app.services.corpus import manufacturers
from app.services.gold import GOLD_DIR, blank_gold, save_gold
from app.services.llm_factory import make_llm
from app.services.pipeline import read_atoms


def main(tender: str, category_dir: str) -> None:
    path = GOLD_DIR / f"{Path(tender).stem}.json"
    if path.exists():
        sys.exit(f"{path} already exists; not overwriting your labels")
    save_gold(blank_gold(read_atoms(make_llm(), tender), manufacturers(category_dir)), path)
    print(f"wrote {path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])