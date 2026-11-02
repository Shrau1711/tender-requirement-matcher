"""The replay-only demo (Dockerfile.demo): the usual service and the built frontend from one process, on one port.

Uploads are refused with a plain message before anything is read, so a new tender never starts a run: the demo only shows
the sample runs loaded into the image (scripts.demo.load_samples). LLM_MAX_CALLS=0 in the image is a second guard.
The samples are shared by every visitor, so deleting or renaming one is refused too. Review decisions can still be saved.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import path_setting
from app.main import create_app

REPLAY_ONLY = "This demo replays saved examples only."
KEPT = "The saved examples cannot be deleted or renamed in this demo."
ONE_RUN = re.compile(r"/runs/[^/]+/?")  # a run itself, not its report, documents or reviews


def refusal(method: str, path: str) -> str | None:
    """Why the demo refuses this request, or None. Every run in the demo is a sample shared by all visitors."""
    if method == "POST" and path.rstrip("/") == "/runs":
        return REPLAY_ONLY
    if method in ("DELETE", "PATCH") and ONE_RUN.fullmatch(path):
        return KEPT
    return None


def create_demo_app(frontend_dir: Path | None = None) -> FastAPI:
    app = create_app()

    @app.middleware("http")
    async def refuse_changes(request: Request, call_next):
        reason = refusal(request.method, request.url.path)
        if reason:
            return JSONResponse({"detail": reason}, status_code=403)
        return await call_next(request)

    # Mounted last, so every API route above is matched first; "/" serves the page.
    app.mount("/", StaticFiles(directory=frontend_dir or path_setting("FRONTEND_DIR", Path("/app/frontend")), html=True), name="frontend")
    return app
