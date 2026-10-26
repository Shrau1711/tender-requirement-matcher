"""Chunk every PDF under a folder and say, per file, which strategy was used, why, and what came out.

Usage: python -m scripts.show_reading.show_chunks <folder> [strategy name or auto]
"""
import sys
import time
from collections import Counter
from pathlib import Path

from app.chunking.base import chunk_document
from app.chunking.router import CHUNKER, choose, chunker_for
from app.reading.pdf_reader import read_pdf


def main(root: str, setting: str = CHUNKER) -> None:
    for path in sorted(Path(root).rglob("*.pdf")):
        print(f"reading {path.parent.name}/{path.name} ...", end=" ", flush=True)
        start = time.time()
        doc = read_pdf(path)
        chunker = chunker_for(doc, setting)
        why = f" ({choose(doc)[1]})" if setting == "auto" else ""
        chunks = chunk_document(doc, chunker)
        by_page = Counter(c.pdf_page for c in chunks)
        empty = [p.pdf_page for p in doc.pages if p.pdf_page not in by_page]
        print(f"{chunker.name}{why}: {len(chunks)} chunks {dict(Counter(c.kind for c in chunks))}, "
              f"pages with no chunks: {empty or 'none'} ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
