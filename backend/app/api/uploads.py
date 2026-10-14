from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import number_setting

MAX_UPLOAD_MB = number_setting("MAX_UPLOAD_MB", 60)


async def save_tender(files: list[UploadFile], folder: Path) -> list[str]:
    """Store the uploaded PDFs of one tender in a folder, refusing anything that is not a PDF or is too large. Returns the file names."""
    if not files:
        raise HTTPException(400, "Upload at least one PDF of the tender.")
    folder.mkdir(parents=True, exist_ok=True)
    names, total = [], 0
    for upload in files:
        name = Path(upload.filename or "").name
        data = await upload.read()
        total += len(data)
        if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
            raise HTTPException(400, f"{name or 'A file'} is not a PDF.")
        if total > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"The upload is larger than {MAX_UPLOAD_MB} MB.")
        (folder / name).write_bytes(data)
        names.append(name)
    return names
