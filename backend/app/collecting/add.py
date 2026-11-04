"""Adding one manufacturer document from the web app: a PDF that was uploaded, or fetched from an address.

The collector's own code does the work: the polite fetcher (robots.txt, a pause), save_pdf (a safe name, the same content
never saved twice) and a line in sources.csv with the source and date. Making it searchable is left to the one ingest
function (app.vectorstore.ingest), so an added document is read exactly as every other one.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from app.categories.config import category_dirs
from app.collecting.crawl import Fetch
from app.collecting.download import file_name, save_pdf
from app.collecting.sources import known_hashes, record_by_hand

MAKER_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")  # a folder name, as the shipped ones are: ksb, l_and_t


class Refused(ValueError):
    """Why a document was not added, in words for the person, with the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def maker_folder(root: Path, category: str, maker: str) -> Path:
    """The manufacturer's folder in a known category. A new manufacturer gets a new folder."""
    folder = next((p for p in category_dirs(root) if p.name == category), None)
    if folder is None:
        raise Refused(404, f"Unknown category: {category}")
    if not MAKER_NAME.fullmatch(maker):
        raise Refused(400, "A manufacturer's name is lower-case letters, digits, - and _, as in l_and_t.")
    return folder / "manufacturers" / maker


def is_web_address(text: str) -> bool:
    return urlparse(text).scheme in ("http", "https") and bool(urlparse(text).netloc)


def download(url: str, fetch: Fetch) -> bytes:
    """The PDF at this address, fetched politely. Refused when the site does not answer, forbids it, or sends no PDF."""
    if not is_web_address(url):
        raise Refused(400, "Give an address that starts with http:// or https://.")
    page = fetch(url)
    if page is None:
        raise Refused(502, "Could not download it: the site did not answer, or its robots.txt does not allow it.")
    if not page.body.startswith(b"%PDF"):
        raise Refused(400, "That address did not give a PDF. Give the address of the PDF itself.")
    return page.body


def pdf_name(text: str) -> str:
    name = file_name(text)
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


def add_document(root: Path, category: str, maker: str, body: bytes, name: str, source: str = "",
                 today: date | None = None) -> dict[str, str]:
    """Save the PDF into the manufacturer's folder and record it in sources.csv. Returns the recorded line.
    name is the uploaded file's name or the address it came from; source, where it came from (the address, for a download)."""
    folder = maker_folder(root, category, maker)
    if not body.startswith(b"%PDF"):
        raise Refused(400, "That file is not a PDF.")
    known = known_hashes(folder) | {hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*.[pP][dD][fF]")}
    saved = save_pdf(source or name, "added in the web app", body, folder, known, today, name=pdf_name(name))
    if saved is None:
        raise Refused(409, f"This document is already in {maker}'s folder.")
    row = {"category": category, "manufacturer": maker, "file": saved.file, "document_type": "added in the web app",
           "source_url": source, "document_year": "", "date_downloaded": saved.date_downloaded, "products_covered": "",
           "notes": "" if source else "uploaded in the web app; source not given"}
    record_by_hand(root, row)
    return row
