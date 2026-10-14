import sys
from collections import Counter
from pathlib import Path

from app.services.chunker import chunk_document
from app.services.pdf_reader import read_pdf


def main(root: str) -> None:
    for path in sorted(Path(root).rglob("*.pdf")):
        doc = read_pdf(path)
        chunks = chunk_document(doc)
        by_page = Counter(c.pdf_page for c in chunks)
        empty = [p.pdf_page for p in doc.pages if p.pdf_page not in by_page]
        print(f"{path.parent.name}/{path.name}: {len(chunks)} chunks "
              f"{dict(Counter(c.kind for c in chunks))}, pages with no chunks: {empty or 'none'}")

if __name__ == "__main__":
    main(sys.argv[1])