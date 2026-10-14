from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents
from app.api.openapi import with_file_pickers
from app.api.reviews import router as reviews
from app.api.routes import router
from app.config import path_setting
from app.db.reviews import ReviewStore
from app.db.runs import RunStore
from app.services.runner import Runner, run_pipeline

BACKEND = Path(__file__).resolve().parents[1]


def create_app(
    categories_dir: Path | None = None, runs_dir: Path | None = None, runner: Runner = run_pipeline, origins: list[str] | None = None
) -> FastAPI:
    """The web service. Folders and the job runner are parameters so tests (and containers) can supply their own."""
    app = FastAPI(title="Tender matcher", description="Match a GeM tender's technical requirements against manufacturers' documents.")
    app.state.categories_dir = categories_dir or path_setting("CATEGORIES_DIR", BACKEND.parent / "data" / "categories")
    app.state.runs_dir = runs_dir or path_setting("RUNS_DIR", BACKEND / "runs")
    app.state.store = RunStore(app.state.runs_dir / "runs.sqlite")
    app.state.reviews = ReviewStore(app.state.runs_dir / "runs.sqlite")
    app.state.store.fail_unfinished("The server restarted before this run finished. Upload the tender again.")
    app.state.runner = runner
    app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(documents)
    app.include_router(reviews)
    describe = app.openapi
    app.openapi = lambda: with_file_pickers(describe())  # type: ignore[method-assign]
    return app

