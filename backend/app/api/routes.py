from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.categories import Category, list_categories
from app.api.uploads import MAX_UPLOAD_MB, save_tender
from app.cost.approval import APPROVALS
from app.db.runs import RunInfo, RunStore
from app.llm.llm_cache import MAX_CALLS
from app.pipeline.runner import Runner, execute, execute_routed
from app.reporting.report import Report
from app.reporting.report_markdown import to_markdown
from app.reporting.report_xlsx import build_workbook

router = APIRouter()


def store_of(request: Request) -> RunStore:
    return request.app.state.store


def known_run(request: Request, run_id: str) -> RunInfo:
    run = store_of(request).get(run_id)
    if run is None:
        raise HTTPException(404, "No such run.")
    return run


def finished_report(request: Request, run_id: str) -> str:
    run = known_run(request, run_id)
    if run.status == "failed":
        raise HTTPException(409, f"The run failed: {run.error}")
    report = store_of(request).report(run_id)
    if run.status != "done" or report is None:
        raise HTTPException(409, f"The run is {run.status}; the report is not ready.")
    return report


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config")
def settings() -> dict[str, int]:
    """Limits the interface tells people about before they start a run."""
    return {"max_model_calls": MAX_CALLS, "max_upload_mb": MAX_UPLOAD_MB}


@router.get("/categories")
def categories(request: Request) -> list[Category]:
    return list_categories(request.app.state.categories_dir)


@router.post("/runs", status_code=202)
async def create_run(
    request: Request, background: BackgroundTasks, files: list[UploadFile], category: str | None = Form(None), name: str | None = Form(None),
    ask_first: bool = Form(False),
) -> RunInfo:
    """Upload a tender (one or more PDFs) and start matching it against a category's manufacturers. Poll GET /runs/{id}.

    Without a category, each item of the tender is sent to the category it belongs to. A tender with items of several
    categories gets one run for each: this run takes the first, and the others appear in GET /runs.

    With ask_first the run stops once it knows what the search will cost (status "awaiting", with its estimate) until POST /runs/{id}/proceed or /cancel.
    """
    state = request.app.state
    if category and category not in {c.name for c in list_categories(state.categories_dir)}:
        raise HTTPException(404, f"Unknown category: {category}")
    first = Path(files[0].filename or "tender").stem if files else "tender"
    run = state.store.create((name or first).strip() or first, category or "")
    folder = state.runs_dir / run.id / "tender"
    try:
        await save_tender(files, folder)
    except HTTPException:
        state.store.delete(run.id)
        shutil.rmtree(state.runs_dir / run.id, ignore_errors=True)
        raise
    if ask_first:
        APPROVALS.require(run.id)
    runner: Runner = state.runner
    if category:
        background.add_task(execute, state.store, run.id, folder, state.categories_dir / category, run.tender, runner)
    else:
        background.add_task(execute_routed, state.store, run.id, folder, state.categories_dir, run.tender, runner, state.route)
    return run


@router.get("/runs")
def list_runs(request: Request) -> list[RunInfo]:
    return store_of(request).all()


@router.get("/runs/{run_id}")
def get_run(request: Request, run_id: str) -> RunInfo:
    return known_run(request, run_id)


def answer_estimate(request: Request, run_id: str, yes: bool) -> RunInfo:
    run = known_run(request, run_id)
    if run.status != "awaiting":
        raise HTTPException(409, f"The run is {run.status}, so there is no estimate to answer.")
    APPROVALS.answer(run_id, yes)
    return run


@router.post("/runs/{run_id}/proceed")
def proceed(request: Request, run_id: str) -> RunInfo:
    """Say yes to the estimate of a run that is awaiting it."""
    return answer_estimate(request, run_id, True)


@router.post("/runs/{run_id}/cancel")
def cancel(request: Request, run_id: str) -> RunInfo:
    """Say no to the estimate of a run that is awaiting it. Nothing more is spent."""
    return answer_estimate(request, run_id, False)


@router.get("/runs/{run_id}/report")
def get_report(request: Request, run_id: str) -> Response:
    """The report as JSON, for programs."""
    return Response(finished_report(request, run_id), media_type="application/json")


@router.get("/runs/{run_id}/report.md")
def get_report_markdown(request: Request, run_id: str) -> Response:
    """The same report as Markdown, for the bid manager."""
    text = to_markdown(Report.model_validate_json(finished_report(request, run_id)))
    return Response(text, media_type="text/markdown; charset=utf-8")


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.patch("/runs/{run_id}")
def rename_run(request: Request, run_id: str, body: Rename) -> RunInfo:
    known_run(request, run_id)
    store_of(request).rename(run_id, body.name.strip() or "untitled")
    return known_run(request, run_id)


@router.get("/runs/{run_id}/report.xlsx")
def get_report_excel(request: Request, run_id: str) -> Response:
    """The same report as an Excel workbook, with any decisions people have recorded."""
    report = Report.model_validate_json(finished_report(request, run_id))
    data = build_workbook(report, {r.key: r for r in request.app.state.reviews.all(run_id)})
    media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{run_id}-report.xlsx"'})


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(request: Request, run_id: str) -> None:
    known_run(request, run_id)
    store_of(request).delete(run_id)
    request.app.state.reviews.clear(run_id)
    shutil.rmtree(request.app.state.runs_dir / run_id, ignore_errors=True)
