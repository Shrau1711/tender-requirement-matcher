from __future__ import annotations

from pathlib import Path

from app.chunking.base import Chunk, chunk_document
from app.chunking.router import CHUNKER, chunker_for
from app.reading.ocr import ImageReader
from app.reading.pdf_reader import read_pdf


def load_chunks(category_dir: str | Path, read_image: ImageReader | None = None, chunker: str = CHUNKER) -> list[Chunk]:
    """Read and chunk every manufacturer PDF under <category_dir>/manufacturers. Picture-only pages go to read_image.

    chunker is a strategy name or "auto" (see app.chunking.router)."""
    pdfs = sorted(Path(category_dir).glob("manufacturers/*/*.[pP][dD][fF]"))
    docs = (read_pdf(pdf, read_image) for pdf in pdfs)
    return [chunk for doc in docs for chunk in chunk_document(doc, chunker_for(doc, chunker))]


def manufacturers(category_dir: str | Path) -> list[str]:
    """Every manufacturer folder, including those whose documents gave no text."""
    return sorted(p.name for p in Path(category_dir, "manufacturers").iterdir() if p.is_dir())
