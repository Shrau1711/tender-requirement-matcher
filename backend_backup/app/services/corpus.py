from __future__ import annotations

from pathlib import Path

from app.services.chunker import Chunk, chunk_document
from app.services.ocr import ImageReader
from app.services.pdf_reader import read_pdf


def load_chunks(category_dir: str | Path, read_image: ImageReader | None = None) -> list[Chunk]:
    """Read and chunk every manufacturer PDF under <category_dir>/manufacturers. Picture-only pages go to read_image."""
    pdfs = sorted(Path(category_dir).glob("manufacturers/*/*.[pP][dD][fF]"))
    return [chunk for pdf in pdfs for chunk in chunk_document(read_pdf(pdf, read_image))]


def manufacturers(category_dir: str | Path) -> list[str]:
    """Every manufacturer folder, including those whose documents gave no text."""
    return sorted(p.name for p in Path(category_dir, "manufacturers").iterdir() if p.is_dir())