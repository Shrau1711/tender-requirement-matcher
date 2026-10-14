from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

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
