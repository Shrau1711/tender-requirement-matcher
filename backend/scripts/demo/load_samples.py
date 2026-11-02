"""Load the replayed sample runs (scripts.demo.replay_samples) into a runs folder, as finished runs with their tender PDFs.

Usage: python -m scripts.demo.load_samples <demo runs folder> <tenders folder> <runs folder>
Used when the demo image is built. Nothing is computed: each saved report is stored as a finished run, and the tender's PDFs
are copied beside it so its pages open in the report.
"""
import json
import shutil
import sys
from pathlib import Path

from app.db.runs import RunStore


def main(demo_runs: str, tenders: str, runs: str) -> None:
    root = Path(runs)
    root.mkdir(parents=True, exist_ok=True)
    store = RunStore(root / "runs.sqlite")
    for sample in json.loads((Path(demo_runs) / "runs.json").read_text(encoding="utf-8")):
        run = store.create(sample["tender"], sample["category"])
        folder = root / run.id / "tender"
        folder.mkdir(parents=True)
        for pdf in (Path(tenders) / sample["folder"]).glob("*.[pP][dD][fF]"):
            shutil.copy2(pdf, folder / pdf.name)
        store.finish(run.id, (Path(demo_runs) / f"{sample['tender']}.json").read_text(encoding="utf-8"), sample["model_calls"])
        print(f"loaded {sample['tender']} as run {run.id}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
