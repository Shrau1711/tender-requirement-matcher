"""Where each manufacturer document came from, so every cited page can be traced back to the manufacturer's own site.

A document is recorded in one of two places:
- data/categories/sources.csv, for documents collected by hand or added in the web app (category, manufacturer, file, address, ...);
- crawl_sources.csv in the manufacturer's folder, one line written by the crawler for each file it saves (address, the page it
  was found on, date, size and SHA-256).
unrecorded() lists the PDFs found in neither, and a test runs it over the shipped documents.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.categories.config import category_dirs
from app.collecting.download import Saved

HAND_RECORDS = "sources.csv"         # in the categories folder
CRAWL_RECORDS = "crawl_sources.csv"  # in each manufacturer's folder


def read_rows(file: Path) -> list[dict[str, str]]:
    if not file.exists():
        return []
    with file.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def known_hashes(maker_folder: Path) -> set[str]:
    """The content hashes the crawler has already saved for this manufacturer, so the same file is not saved twice."""
    return {row["sha256"] for row in read_rows(maker_folder / CRAWL_RECORDS)}


def record_source(maker_folder: Path, saved: Saved) -> None:
    """Add the saved file's source to the manufacturer's crawl_sources.csv, writing the header the first time."""
    log = maker_folder / CRAWL_RECORDS
    new = not log.exists()
    with log.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(Saved._fields)
        writer.writerow(saved)


def record_by_hand(root: Path, row: dict[str, str]) -> None:
    """Add a line to sources.csv in the categories folder, in the order of its own header (written the first time)."""
    log = root / HAND_RECORDS
    new = not log.exists() or not log.stat().st_size
    if new:
        fields = list(row)
    else:
        with log.open(newline="", encoding="utf-8") as f:
            fields = next(csv.reader(f))
    with log.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow(row)


def unrecorded(root: Path) -> list[Path]:
    """Every manufacturer PDF under the categories folder whose source is not recorded anywhere."""
    by_hand = {(r["category"], r["manufacturer"], r["file"]) for r in read_rows(root / HAND_RECORDS)}
    missing = []
    for category in category_dirs(root):
        for maker in sorted(p for p in (category / "manufacturers").iterdir() if p.is_dir()):
            crawled = {row["file"] for row in read_rows(maker / CRAWL_RECORDS)}
            missing += [pdf for pdf in sorted(maker.glob("*.[pP][dD][fF]"))
                        if pdf.name not in crawled and (category.name, maker.name, pdf.name) not in by_hand]
    return missing
