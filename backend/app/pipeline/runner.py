from __future__ import annotations

import shutil
import threading
from collections.abc import Callable
from functools import cache
from pathlib import Path

from app.categories.routing import by_category, route_items
from app.cost.approval import APPROVALS, Declined, ask_person
from app.cost.estimate import Estimate
from app.db.runs import RunStore
from app.llm.llm import LLM
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import build_report, gather
from app.reading.ocr import OCR, reader_for
from app.tender.reader import read_tender
from app.vectorstore.ingest import ingest, open_index, open_store

Progress = Callable[[str], None]  # told what the job is doing, in words for the person
Runner = Callable[[str, Path, Path, str, Progress], tuple[str, str]]  # (run id, tender folder, category folder, tender name, progress) -> (report json, model-call summary)
Route = Callable[[Path, Path], dict[str, list[str]]]  # (tender folder, categories folder) -> {category: its item titles}
Ingest = Callable[[Path, str, str], int]  # (category folder, manufacturer, file) -> the file's chunks, once searchable

ONE_AT_A_TIME = threading.Lock()  # a run spends the model quota; two at once would only make both slow


def run_pipeline(
    run_id: str, tender_dir: Path, category_dir: Path, name: str, progress: Progress, llm: LLM | None = None, ask: Callable[[Estimate], None] | None = None,
    items: list[str] | None = None,
) -> tuple[str, str]:
    """The whole job for one tender: read it, search the manufacturers' documents, score, and report. ask, if given, may stop it before the search is paid for.
    items, if given, are the titles of the only items to match (the rest of the tender belongs to other categories)."""
    llm = llm or make_llm()
    found = gather(llm, tender_dir, category_dir, reader_for(llm), progress, ask, items)
    progress("Scoring the evidence and building the report")
    report = build_report(llm, found, name)
    return report.model_dump_json(), llm.summary()


def execute(
    store: RunStore, run_id: str, tender_dir: Path, category_dir: Path, name: str, runner: Runner = run_pipeline, items: list[str] | None = None
) -> None:
    """Run a job and record how it ended. Never raises: a failure is stored on the run for the person to read."""
    with ONE_AT_A_TIME:
        store.set_status(run_id, "running")
        asking = {"ask": lambda estimate: ask_person(store, run_id, estimate)} if APPROVALS.required(run_id) else {}
        only = {"items": items} if items else {}
        try:
            report_json, calls = runner(run_id, tender_dir, category_dir, name, lambda text: store.set_progress(run_id, text), **asking, **only)
        except Declined as no:
            store.cancel(run_id, str(no))
            return
        except Exception as error:  # noqa: BLE001 - whatever went wrong is shown to the person, not hidden
            store.fail(run_id, f"{type(error).__name__}: {error}")
            return
        store.finish(run_id, report_json, calls)


def route_tender(tender_dir: Path, categories_dir: Path) -> dict[str, list[str]]:
    """Read the tender's items (from the cache if it was read before) and send each to its category."""
    llm = make_llm()
    read_image = reader_for(llm)
    titles = [r.item.title for r in read_tender(llm, tender_dir, read_image).requirements]
    return by_category(route_items(titles, lambda folder: open_index(folder, read_image), categories_dir))


def add_to_search(category_dir: Path, maker: str, file: str) -> int:
    """Store a category's new documents now, with the page reader a run uses, so the next run finds them ready.
    The model is made only if a page is a picture and OCR is the model, so a document with its own text, or one read
    by a local reader, needs no key and costs nothing."""
    reader = cache(lambda: reader_for(make_llm() if OCR == "model" else None))
    chunks = ingest(category_dir, open_store(), lambda png: reader()(png))
    return sum(1 for c in chunks if c.manufacturer == maker and c.file == file)


def execute_routed(
    store: RunStore, run_id: str, tender_dir: Path, categories_dir: Path, name: str, runner: Runner = run_pipeline, route: Route = route_tender
) -> None:
    """A run started without a category: find the category of each item, then match each category's items in a run of its own.

    This run takes the first category. Every other category gets a new run with a copy of the tender, so its links to the
    tender's pages work on their own. A tender of one category is matched whole, exactly as if the category had been chosen.
    """
    store.set_progress(run_id, "Finding the product category of each item")
    try:
        groups = route(tender_dir, categories_dir)
    except Exception as error:  # noqa: BLE001 - shown to the person, like any failed run
        store.fail(run_id, f"{type(error).__name__}: {error}")
        return
    if not groups:
        store.fail(run_id, "No items with requirements were found in the tender, so there is nothing to match")
        return
    split = len(groups) > 1
    jobs = []
    for category, titles in groups.items():
        job_id = run_id if not jobs else store.create(f"{name} ({category})", category).id
        if jobs:
            shutil.copytree(tender_dir, tender_dir.parent.parent / job_id / "tender")
            if APPROVALS.required(run_id):
                APPROVALS.require(job_id)  # asked to wait before spending, like the run it came from
        elif split:
            store.rename(run_id, f"{name} ({category})")
        store.set_category(job_id, category)
        jobs.append((job_id, category, titles))
    for job_id, category, titles in jobs:
        execute(store, job_id, tender_dir.parent.parent / job_id / "tender", categories_dir / category, name, runner, titles if split else None)

