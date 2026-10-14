"""Write a first draft of the tenders' sources file from the tenders themselves.

Usage: python -m scripts.make_tender_sources <tenders folder, e.g. ..\\data\\tenders>
Reads the bid page of each GeM-Bidding-<number> folder (buyer, product). where_found and date_downloaded
are left for a person to fill in. Never overwrites an existing file.
"""
import csv
import sys
from pathlib import Path

import pymupdf

from app.services.bid_details import parse_bid_details

COLUMNS = ["bid_number", "gem_file_number", "buyer", "product", "category", "where_found", "date_downloaded", "notes"]


def bid_page(folder: Path) -> tuple[str, str]:
    """The name and first-page text of the folder's bid document: the first PDF that has a bid details page."""
    for pdf in sorted(folder.glob("*.[pP][dD][fF]")):
        with pymupdf.open(pdf) as doc:
            text = doc[0].get_text() if len(doc) else ""
        if "Bid Details" in text:
            return pdf.name, text
    return "", ""


def main(root: str) -> None:
    target = Path(root) / "sources.csv"
    if target.exists():
        sys.exit(f"{target} already exists; not overwriting it")
    rows = []
    for folder in sorted(Path(root).glob("*/GeM-Bidding-*")):
        name, text = bid_page(folder)
        found = parse_bid_details(text)
        rows.append({
            "bid_number": folder.name.removeprefix("GeM-Bidding-"), "gem_file_number": name, **found,
            "where_found": "", "date_downloaded": "",
            "notes": "hold-out set, not used for tuning" if folder.parent.name == "holdout" else "",
        })
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {target}")


if __name__ == "__main__":
    main(sys.argv[1])
