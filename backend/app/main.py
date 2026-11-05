from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents
from app.api.openapi import with_file_pickers
from app.api.reviews import router as reviews
from app.api.routes import router
from app.categories.config import CATEGORIES_DIR
from app.collecting.crawl import Fetch
from app.collecting.download import polite_fetcher
from app.config import path_setting
from app.db.reviews import ReviewStore
from app.db.runs import RunStore
from app.pipeline.runner import (
    Ingest,
    Route,
    Runner,
    add_to_search,
    route_tender,
    run_pipeline,
)

BACKEND = Path(__file__).resolve().parents[1]


def create_app(
    categories_dir: Path | None = None, runs_dir: Path | None = None, runner: Runner = run_pipeline, origins: list[str] | None = None,
    route: Route = route_tender, ingest: Ingest = add_to_search, fetch: Fetch | None = None,
) -> FastAPI:
    """The web service. Folders, the job runner, the item router, the ingest of an added document and the web fetcher are
    parameters so tests (and containers) can supply their own."""
    app = FastAPI(title="Tender matcher", description="Match a GeM tender's technical requirements against manufacturers' documents.")
    app.state.categories_dir = categories_dir or CATEGORIES_DIR
    app.state.runs_dir = runs_dir or path_setting("RUNS_DIR", BACKEND / "runs")
    app.state.store = RunStore(app.state.runs_dir / "runs.sqlite")
    app.state.reviews = ReviewStore(app.state.runs_dir / "runs.sqlite")
    app.state.store.fail_unfinished("The server restarted before this run finished. Upload the tender again.")
    app.state.runner, app.state.route = runner, route
    app.state.ingest, app.state.fetch = ingest, fetch or polite_fetcher()
    app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(documents)
    app.include_router(reviews)
    describe = app.openapi
    app.openapi = lambda: with_file_pickers(describe())  # type: ignore[method-assign]
    return app

