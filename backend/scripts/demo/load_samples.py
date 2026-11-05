"""Load the replayed sample runs (scripts.demo.replay_samples) into a runs folder, as finished runs with their tender PDFs.

Usage: python -m scripts.demo.load_samples <demo runs folder> <tenders folder> <runs folder>
Used when the demo image is built. Nothing is computed: each saved report is stored as a finished run, and the tender's PDFs
are copied beside it so its pages open in the report.

A sample whose tender folder holds no PDF stops it before anything is loaded, so the image build fails instead of shipping
a sample whose pages and layout cannot open. The hold-out samples are not in git (.gitignore), so a build from a clean
checkout must have them copied in first (see docs/HF_SPACE_README.md).
"""
import json
import shutil
import sys
from pathlib import Path

from app.db.runs import RunStore


def missing_pdfs(samples: list[dict], tenders: Path) -> list[str]:
    """The sample folders that hold no PDF (or do not exist)."""
    return [s["folder"] for s in samples if not any((tenders / s["folder"]).glob("*.[pP][dD][fF]"))]


def main(demo_runs: str, tenders: str, runs: str) -> None:
    samples = json.loads((Path(demo_runs) / "runs.json").read_text(encoding="utf-8"))
    missing = missing_pdfs(samples, Path(tenders))
    if missing:
        sys.exit(f"These sample tender folders hold no PDF: {', '.join(missing)}. The hold-out samples are not in git; "
                 "copy them into data/tenders/ before building the demo image (see docs/HF_SPACE_README.md).")
    root = Path(runs)
    root.mkdir(parents=True, exist_ok=True)
    store = RunStore(root / "runs.sqlite")
    for sample in samples:
        run = store.create(sample["tender"], sample["category"])
        folder = root / run.id / "tender"
        folder.mkdir(parents=True)
        for pdf in (Path(tenders) / sample["folder"]).glob("*.[pP][dD][fF]"):
            shutil.copy2(pdf, folder / pdf.name)
        store.finish(run.id, (Path(demo_runs) / f"{sample['tender']}.json").read_text(encoding="utf-8"), sample["model_calls"])
        print(f"loaded {sample['tender']} as run {run.id}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
