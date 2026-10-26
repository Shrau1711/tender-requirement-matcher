"""Find (and optionally download) a manufacturer's catalogue PDFs from its website.

Usage, from the backend folder (lists what it would download; nothing is saved):
  python -m scripts.run.crawl_catalogues --category pumps --maker grundfos --start https://example.com/downloads --include databooklet datasheet --exclude price

Add --download to save the PDFs into data/categories/<category>/manufacturers/<maker>/ and append a line per file to
crawl_sources.csv in that folder (address, page it was found on, date, size, sha256): the source note for each document.
Respects robots.txt, waits between requests, stays on the start site, and skips content it already has.
"""
import argparse

from app.categories.config import CATEGORIES_DIR
from app.collecting.crawl import crawl
from app.collecting.download import polite_fetcher, save_pdf
from app.collecting.sources import known_hashes, record_source


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
    folder = CATEGORIES_DIR / args.category / "manufacturers" / args.maker
    fetch = polite_fetcher()
    known = known_hashes(folder)
    for found in crawl(args.start, fetch, args.include, args.exclude, args.depth, args.max_pdfs):
        if not args.download:
            print(f"{found.pdf}\n    linked from {found.found_on}")
            continue
        page = fetch(found.pdf)
        saved = save_pdf(found.pdf, found.found_on, page.body, folder, known) if page else None
        print(f"saved {saved.file}" if saved else f"skipped {found.pdf} (not a PDF, unreadable or already have it)")
        if saved:
            record_source(folder, saved)


if __name__ == "__main__":
    main()
