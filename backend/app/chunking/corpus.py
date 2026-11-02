from __future__ import annotations

from pathlib import Path

from app.chunking.base import Chunk, chunk_document
from app.chunking.router import CHUNKER, chunker_for
from app.reading.ocr import ImageReader
from app.reading.pdf_reader import read_pdf


def pdf_files(category_dir: str | Path) -> list[Path]:
    """Every manufacturer PDF of a category: <category_dir>/manufacturers/<maker>/<file>.pdf, in a fixed order."""
    return sorted(Path(category_dir).glob("manufacturers/*/*.[pP][dD][fF]"))


def chunk_file(pdf: Path, read_image: ImageReader | None = None, chunker: str = CHUNKER) -> list[Chunk]:
    """Read one PDF and cut it into chunks. Picture-only pages go to read_image. chunker is a strategy name or "auto"."""
    doc = read_pdf(pdf, read_image)
    return chunk_document(doc, chunker_for(doc, chunker))


def load_chunks(category_dir: str | Path, read_image: ImageReader | None = None, chunker: str = CHUNKER) -> list[Chunk]:
    """Read and chunk every manufacturer PDF of a category (see app.chunking.router for chunker)."""
    return [chunk for pdf in pdf_files(category_dir) for chunk in chunk_file(pdf, read_image, chunker)]


def manufacturers(category_dir: str | Path) -> list[str]:
    """Every manufacturer folder, including those whose documents gave no text."""
    return sorted(p.name for p in Path(category_dir, "manufacturers").iterdir() if p.is_dir())
