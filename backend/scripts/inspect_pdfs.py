"""Run the reader over PDFs and print a per-file health report.

Usage: python -m scripts.inspect_pdfs <file-or-dir> [...]
"""
import sys
from pathlib import Path

from app.services.pdf_reader import read_pdf


def main(args: list[str]) -> None:
    files: list[Path] = []
    for a in args:
        p = Path(a)
        files += sorted(p.rglob("*.pdf")) if p.is_dir() else [p]
    for f in files:
        d = read_pdf(f)
        ocr = [p.pdf_page for p in d.pages if p.needs_ocr]
        labels = [(p.pdf_page, p.printed_label) for p in d.pages if p.printed_label]
        print(f"\n== {f.name}  pages={d.n_pages}  sha256={d.sha256[:12]}")
        print(f"   chars/page: {[p.n_chars for p in d.pages]}")
        print(f"   needs OCR: {ocr or 'none'}")
        if labels:
            print(f"   page labels: {labels[:6]}")


if __name__ == "__main__":
    main(sys.argv[1:])