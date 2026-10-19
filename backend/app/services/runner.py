from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from app.db.runs import RunStore
from app.services.approval import APPROVALS, Declined, ask_person
from app.services.estimate import Estimate
from app.services.llm import LLM
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import build_report, gather

Progress = Callable[[str], None]  # told what the job is doing, in words for the person
Runner = Callable[[str, Path, Path, str, Progress], tuple[str, str]]  # (run id, tender folder, category folder, tender name, progress) -> (report json, model-call summary)

ONE_AT_A_TIME = threading.Lock()  # a run spends the model quota; two at once would only make both slow


def run_pipeline(
    run_id: str, tender_dir: Path, category_dir: Path, name: str, progress: Progress, llm: LLM | None = None, ask: Callable[[Estimate], None] | None = None
) -> tuple[str, str]:
    """The whole job for one tender: read it, search the manufacturers' documents, score, and report. ask, if given, may stop it before the search is paid for."""
    llm = llm or make_llm()
    found = gather(llm, tender_dir, category_dir, reader_for(llm), progress, ask)
    progress("Scoring the evidence and building the report")
    report = build_report(llm, found, name)
    return report.model_dump_json(), llm.summary()


def execute(store: RunStore, run_id: str, tender_dir: Path, category_dir: Path, name: str, runner: Runner = run_pipeline) -> None:
    """Run a job and record how it ended. Never raises: a failure is stored on the run for the person to read."""
    with ONE_AT_A_TIME:
        store.set_status(run_id, "running")
        asking = {"ask": lambda estimate: ask_person(store, run_id, estimate)} if APPROVALS.required(run_id) else {}
        try:
            report_json, calls = runner(run_id, tender_dir, category_dir, name, lambda text: store.set_progress(run_id, text), **asking)
        except Declined as no:
            store.cancel(run_id, str(no))
            return
        except Exception as error:  # noqa: BLE001 - whatever went wrong is shown to the person, not hidden
            store.fail(run_id, f"{type(error).__name__}: {error}")
            return
        store.finish(run_id, report_json, calls)
