"""Replay the sample tenders from the shipped answers alone and save their reports, for the replay-only demo (Dockerfile.demo).

Usage: LLM_MAX_CALLS=0 CACHE_DIR=<an empty folder> python -m scripts.demo.replay_samples <tenders folder> <categories folder> <out folder>
Each tender in <tenders folder>/sources.csv is run against its recorded category. The model is replaced by one that refuses
every call (as in scripts.cost.export_demo_cache), so this can never spend anything. With an empty CACHE_DIR only the answers
shipped in data/demo_cache are used, so a tender that finishes here also finishes in the image. A tender that would need a
model call is reported and left out. Writes <out>/<tender>.json (the report) and <out>/runs.json (tender, category, calls).
"""
import csv
import json
import sys
from pathlib import Path

from app.llm.llm_factory import make_llm
from app.pipeline.runner import run_pipeline
from scripts.cost.export_demo_cache import NoCalls


def main(tenders: str, categories: str, out: str) -> None:
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((Path(tenders) / "sources.csv").read_text(encoding="utf-8").splitlines()))
    folders = {f.name: f for f in Path(tenders).glob("*/GeM-Bidding-*") if f.is_dir()}
    done, left_out = [], []
    for row in rows:
        name = f"GeM-Bidding-{row['bid_number']}"
        llm = make_llm()
        llm.inner = NoCalls(llm.inner)
        try:
            report, calls = run_pipeline("demo", folders[name], Path(categories) / row["category"], name, lambda text: None, llm=llm)
        except Exception as error:  # noqa: BLE001 - a tender that cannot be replayed is reported, not fatal
            left_out.append(name)
            print(f"left out {name}: {type(error).__name__}: {str(error)[:200]}", flush=True)
            continue
        (target / f"{name}.json").write_text(report, encoding="utf-8")
        done.append({"tender": name, "folder": str(folders[name].relative_to(tenders)).replace("\\", "/"), "category": row["category"], "model_calls": calls})
        print(f"replayed {name} ({row['category']}): {calls}", flush=True)
    (target / "runs.json").write_text(json.dumps(done, indent=2) + "\n", encoding="utf-8")
    print(f"{len(done)} replayed, {len(left_out)} left out: {', '.join(left_out) or 'none'}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
