"""Copy the saved model answers of finished tenders into data/demo_cache, so the code ships with them and a fresh install answers those tenders at no cost.

Usage: python -m scripts.cost.export_demo_cache <category_dir> <tender folder or pdf> [more tenders...]
All tenders must be of the category in category_dir. Only answers already saved are used: the model is replaced by one that refuses every call, so this can never spend anything.
A tender whose answers are not all saved stops with an error; run it first, then export it.
"""
import shutil
import sys
from pathlib import Path

from app.llm.llm_cache import shipped_path
from app.llm.llm_factory import SEED_DIR, make_llm
from app.pipeline.pipeline import build_report, gather
from app.reading.ocr import reader_for


class NoCalls:
    """Stands in for the model: same name and settings (so saved answers are found), but any real call is refused."""

    def __init__(self, real) -> None:
        self.model, self.settings = getattr(real, "model", ""), getattr(real, "settings", "")

    def generate(self, system: str, user: str):
        raise RuntimeError(f"This needs a real model call, so it is not saved yet: {user[:300]}")

    def transcribe(self, png: bytes, prompt: str):
        raise RuntimeError("A scanned page that is not saved yet would need a real model call.")


def copy_answers(paths: set[Path], out: Path) -> int:
    """Copies each saved answer into out, keeping its file name, in the subfolder shipped_path gives. Returns how many are there afterwards."""
    for path in paths:
        target = shipped_path(out, path.name)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return len(list(out.rglob("*.json")))


def main(category_dir: str, *tenders: str) -> None:
    llm = make_llm()
    llm.inner = NoCalls(llm.inner)  # nothing may be asked of the model; the call limit stays as in a normal run, so the budget plan is the same
    read_image = reader_for(llm)
    for tender in tenders:
        build_report(llm, gather(llm, tender, category_dir, read_image), Path(tender).stem)
        print(f"read {tender}: {len(llm.used)} saved answers so far")
    print(f"{copy_answers(llm.used, SEED_DIR)} answers in {SEED_DIR}")


if __name__ == "__main__":
    main(*sys.argv[1:])
