"""Check a sample of a tender's answers by hand, when the whole tender is too big to label.

  python -m scripts.spot_check sample <tender folder> <category_dir> [rows per kind, default 12]
      writes reports/spot_<tender>.csv: a random sample of the answers, with the cited file, page and quote.
  python -m scripts.spot_check tally <csv>
      counts the verdicts you typed in the "verdict" column: y (right), n (wrong) or ? (cannot tell).

Two kinds of row are sampled: answers that cite evidence (is the quote on that page, and does it support the status?)
and answers that found nothing (is the catalogue really silent on it? search the documents for the attribute).
This is a spot check, not an evaluation: a few dozen rows say how often an answer can be trusted, not how accurate the tender is overall.
"""
import csv
import random
import sys
from collections import Counter
from pathlib import Path

from app.services.llm_factory import make_llm
from app.services.match import Outcome
from app.services.ocr import reader_for
from app.services.pipeline import match_tender

SEED = 7  # the same sample every time, so the sheet does not change under you
COLUMNS = ["id", "kind", "manufacturer", "item", "requirement", "our_status", "score", "flags", "file", "page", "quote", "verdict", "note"]


def row(i: int, o: Outcome) -> dict:
    e, r = o.evidence, o.requirement
    return {
        "id": i, "kind": "cites evidence" if e else "found nothing", "manufacturer": o.manufacturer, "item": r.item.title,
        "requirement": f"{r.source_name}: {r.source_value} (attribute: {r.attribute})", "our_status": o.status, "score": o.score,
        "flags": "; ".join(o.flags), "file": e.file if e else "", "page": e.pdf_page if e else "", "quote": e.quote if e else "",
        "verdict": "", "note": "",
    }


def sample(tender: str, category_dir: str, per_kind: int) -> None:
    llm = make_llm()
    _, _, outcomes = match_tender(llm, tender, category_dir, reader_for(llm))
    assessed = [o for o in outcomes if o.assessed]
    pools = [[o for o in assessed if o.evidence], [o for o in assessed if not o.evidence]]
    rng = random.Random(SEED)
    chosen = [o for pool in pools for o in rng.sample(pool, min(per_kind, len(pool)))]
    out = Path("reports") / f"spot_{Path(tender).stem}.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, COLUMNS)
        writer.writeheader()
        writer.writerows(row(i + 1, o) for i, o in enumerate(chosen))
    print(f"Wrote {out}: {len(chosen)} rows of {len(assessed)}. Fill the verdict column (y / n / ?), then run the tally.\n{llm.summary()}")


def tally(path: str) -> None:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for kind in ("cites evidence", "found nothing"):
        marks = Counter(r["verdict"].strip().lower() for r in rows if r["kind"] == kind and r["verdict"].strip())
        total = sum(marks.values())
        right = marks["y"]
        share = f"{right}/{total} ({100 * right // total}%)" if total else "no verdicts yet"
        print(f"{kind}: right {share}, wrong {marks['n']}, could not tell {marks['?']}")
    print(f"unmarked rows: {sum(1 for r in rows if not r['verdict'].strip())}")


if __name__ == "__main__":
    {"sample": lambda a: sample(a[0], a[1], int(a[2]) if len(a) > 2 else 12), "tally": lambda a: tally(a[0])}[sys.argv[1]](sys.argv[2:])
