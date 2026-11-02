from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.reading.ocr import ImageReader
from app.reading.pdf_reader import ReadDocument, read_pdf, sha256_file

BID_DOCUMENT_PREFIX = "gem-bidding"  # the file GeM names the bid document itself; the other files are its attachments


@dataclass
class TenderDocuments:
    documents: list[ReadDocument]
    duplicates: list[str]  # files skipped because an identical file was already there


def tender_pdfs(path: str | Path) -> list[Path]:
    """The PDFs of a tender: one file, or every PDF in a tender's folder. The bid document comes first, as it lists the items."""
    path = Path(path)
    if path.is_file():
        return [path]
    pdfs = sorted(path.glob("*.[pP][dD][fF]"), key=lambda p: (not p.name.lower().startswith(BID_DOCUMENT_PREFIX), p.name.lower()))
    if not pdfs:
        raise ValueError(f"No PDF files found in {path}")
    return pdfs


def read_tender_documents(path: str | Path, read_image: ImageReader | None = None) -> TenderDocuments:
    """Read every PDF of a tender once. A file that is byte for byte a copy of an earlier one is skipped."""
    documents, duplicates, seen = [], [], set()
    for pdf in tender_pdfs(path):
        digest = sha256_file(pdf)
        if digest in seen:
            duplicates.append(pdf.name)
            continue
        seen.add(digest)
        documents.append(read_pdf(pdf, read_image))
    return TenderDocuments(documents, duplicates)
