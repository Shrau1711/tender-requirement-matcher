import sys
import time
from collections import Counter
from pathlib import Path

from app.chunking.chunker import chunk_document
from app.reading.pdf_reader import read_pdf


def main(root: str) -> None:
    for path in sorted(Path(root).rglob("*.pdf")):
        print(f"reading {path.parent.name}/{path.name} ...", end=" ", flush=True)
        start = time.time()
        doc = read_pdf(path)
        chunks = chunk_document(doc)
        by_page = Counter(c.pdf_page for c in chunks)
        empty = [p.pdf_page for p in doc.pages if p.pdf_page not in by_page]
        print(f"{len(chunks)} chunks {dict(Counter(c.kind for c in chunks))}, "
              f"pages with no chunks: {empty or 'none'} ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main(sys.argv[1])
