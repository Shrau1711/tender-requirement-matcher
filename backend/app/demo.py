"""The replay-only demo (Dockerfile.demo): the usual service and the built frontend from one process, on one port.

Uploads are refused with a plain message before anything is read, so a new tender never starts a run: the demo only shows
the sample runs loaded into the image (scripts.demo.load_samples). LLM_MAX_CALLS=0 in the image is a second guard.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import path_setting
from app.main import create_app

REPLAY_ONLY = "This demo replays saved examples only."


def create_demo_app(frontend_dir: Path | None = None) -> FastAPI:
    app = create_app()

    @app.middleware("http")
    async def refuse_uploads(request: Request, call_next):
        if request.method == "POST" and request.url.path.rstrip("/") == "/runs":
            return JSONResponse({"detail": REPLAY_ONLY}, status_code=403)
        return await call_next(request)

    # Mounted last, so every API route above is matched first; "/" serves the page.
    app.mount("/", StaticFiles(directory=frontend_dir or path_setting("FRONTEND_DIR", Path("/app/frontend")), html=True), name="frontend")
    return app
