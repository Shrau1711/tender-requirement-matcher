from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.uploads import MAX_UPLOAD_MB
from app.collecting.add import Refused, add_document, download, is_web_address

router = APIRouter()


def child_dir(parent: Path | None, name: str) -> Path | None:
    """The sub-folder with exactly this name, found by listing rather than by building a path from user input."""
    if parent is None or not parent.is_dir():
        return None
    return next((p for p in parent.iterdir() if p.is_dir() and p.name == name), None)


def pdf_named(folder: Path | None, name: str) -> Path:
    """The PDF in this folder with exactly this file name.

    The name is looked up among the folder's own files instead of being joined onto the path,
    so "../" or an absolute path can never reach anything else.
    """
    match = next((p for p in folder.glob("*.[pP][dD][fF]") if p.is_file() and p.name == name), None) if folder is not None and folder.is_dir() else None
    if match is None:
        raise HTTPException(404, "No such document.")
    return match


def inline_pdf(path: Path) -> FileResponse:
    """Shown in the browser, so a link ending in #page=N opens on that page."""
    return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{path.name}"'})


@router.get("/categories/{category}/manufacturers/{maker}/documents/{name}")
def manufacturer_document(request: Request, category: str, maker: str, name: str) -> FileResponse:
    """A manufacturer's source document, as collected."""
    root: Path = request.app.state.categories_dir
    folder = child_dir(child_dir(child_dir(root, category), "manufacturers"), maker)
    return inline_pdf(pdf_named(folder, name))


@router.get("/runs/{run_id}/tender/{name}")
def tender_document(request: Request, run_id: str, name: str) -> FileResponse:
    """A PDF that was uploaded for this run."""
    if request.app.state.store.get(run_id) is None:
        raise HTTPException(404, "No such run.")
    return inline_pdf(pdf_named(request.app.state.runs_dir / run_id / "tender", name))


class AddedDocument(BaseModel):
    category: str
    manufacturer: str
    file: str
    source_url: str
    date_downloaded: str
    chunks: int | None  # passages now searchable; None if reading it failed (the next run tries again)
    problem: str | None = None


@router.post("/categories/{category}/documents", status_code=201)
def add_manufacturer_document(
    request: Request, category: str, manufacturer: str = Form(...), file: UploadFile | None = None, url: str = Form(""),
    source: str = Form(""),
) -> AddedDocument:
    """Add a manufacturer's document: upload a PDF (source: where it came from, optional) or give the address of one.
    It is saved in the manufacturer's folder, recorded in sources.csv with its source and date, and made searchable."""
    state, url, maker = request.app.state, url.strip(), manufacturer.strip().lower()
    if (file is None) == (not url):
        raise HTTPException(400, "Upload a PDF or give its address, one or the other.")
    try:
        if file is not None:
            body = file.file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
            if len(body) > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(413, f"The file is larger than {MAX_UPLOAD_MB} MB.")
            source = source.strip()
            if source and not is_web_address(source):
                raise HTTPException(400, "The source should be the web address the file came from.")
            row = add_document(state.categories_dir, category, maker, body, Path(file.filename or "document.pdf").name, source)
        else:
            row = add_document(state.categories_dir, category, maker, download(url, state.fetch), url, url)
    except Refused as refused:
        raise HTTPException(refused.status, str(refused)) from refused
    try:
        chunks, problem = state.ingest(state.categories_dir / category, maker, row["file"]), None
    except Exception as error:  # noqa: BLE001 - the file is saved and recorded; the person is told why it is not searchable yet
        chunks, problem = None, f"Saved and recorded, but reading it failed ({type(error).__name__}: {error}). The next run tries again."
    return AddedDocument(**{k: row[k] for k in ("category", "manufacturer", "file", "source_url", "date_downloaded")},
                         chunks=chunks, problem=problem)
