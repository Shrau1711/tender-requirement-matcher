"""Find (and optionally download) a manufacturer's catalogue PDFs from its website.

Usage, from the backend folder (lists what it would download; nothing is saved):
  python -m scripts.crawl_catalogues --category pumps --maker grundfos --start https://example.com/downloads --include databooklet datasheet --exclude price

Add --download to save the PDFs into data/categories/<category>/manufacturers/<maker>/ and append a line per file to
crawl_sources.csv in that folder (address, page it was found on, date, size, sha256): the source note for each document.
Respects robots.txt, waits between requests, stays on the start site, and skips content it already has.
"""
import argparse
import csv
from pathlib import Path

from app.config import path_setting
from app.services.crawl import crawl
from app.services.download import Saved, polite_fetcher, save_pdf

CATEGORIES = path_setting("CATEGORIES_DIR", Path(__file__).resolve().parents[2] / "data" / "categories")
LOG_NAME = "crawl_sources.csv"


def known_hashes(log: Path) -> set[str]:
    if not log.exists():
        return set()
    with log.open(newline="", encoding="utf-8") as f:
        return {row["sha256"] for row in csv.DictReader(f)}


def append_record(log: Path, record: Saved) -> None:
    new = not log.exists()
    with log.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(Saved._fields)
        writer.writerow(record)


def parse() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category", required=True, help="folder name under data/categories, e.g. pumps")
    ap.add_argument("--maker", required=True, help="manufacturer folder name, e.g. grundfos")
    ap.add_argument("--start", required=True, nargs="+", help="page(s) that list the catalogues; the crawl stays on these sites")
    ap.add_argument("--include", nargs="*", default=[], help="keep a PDF only if its address has one of these words")
    ap.add_argument("--exclude", nargs="*", default=[], help="skip a PDF whose address has any of these words")
    ap.add_argument("--depth", type=int, default=2, help="how many links deep to follow from the start pages")
    ap.add_argument("--max-pdfs", type=int, default=30)
    ap.add_argument("--download", action="store_true", help="save the files; without it only the list is shown")
    return ap.parse_args()


def main() -> None:
    args = parse()
    folder = CATEGORIES / args.category / "manufacturers" / args.maker
    log, fetch = folder / LOG_NAME, polite_fetcher()
    known = known_hashes(log)
    for found in crawl(args.start, fetch, args.include, args.exclude, args.depth, args.max_pdfs):
        if not args.download:
            print(f"{found.pdf}\n    linked from {found.found_on}")
            continue
        page = fetch(found.pdf)
        saved = save_pdf(found.pdf, found.found_on, page.body, folder, known) if page else None
        print(f"saved {saved.file}" if saved else f"skipped {found.pdf} (not a PDF, unreadable or already have it)")
        if saved:
            append_record(log, saved)


if __name__ == "__main__":
    main()
