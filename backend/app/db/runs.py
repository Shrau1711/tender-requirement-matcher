from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

from app.cost.estimate import Estimate

Status = Literal["queued", "awaiting", "running", "done", "failed", "cancelled"]  # awaiting: the person has an estimate to approve

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    tender TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    model_calls TEXT,
    report TEXT,
    progress TEXT,
    estimate TEXT
)
"""

COLUMNS = "id, tender, category, status, error, created_at, finished_at, model_calls, progress, estimate"


class RunInfo(BaseModel):
    """What is known about a run, without its (large) report."""

    id: str
    tender: str
    category: str
    status: Status
    error: str | None = None
    created_at: str
    finished_at: str | None = None
    model_calls: str | None = None
    progress: str | None = None  # what the run is doing right now, while it runs
    estimate: Estimate | None = None  # what the search will cost, while the person decides

    @field_validator("estimate", mode="before")
    @classmethod
    def stored_estimate(cls, value):
        return Estimate.model_validate_json(value) if isinstance(value, str) else value


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunStore:
    """Past runs and their reports, kept in one SQLite file so they survive a restart."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute(SCHEMA)
            have = {row["name"] for row in db.execute("PRAGMA table_info(runs)")}
            for column in ("progress", "estimate"):
                if column not in have:
                    db.execute(f"ALTER TABLE runs ADD COLUMN {column} TEXT")  # a database made before this was kept

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def create(self, tender: str, category: str) -> RunInfo:
        run = RunInfo(id=uuid.uuid4().hex[:12], tender=tender, category=category, status="queued", created_at=now())
        with self.connect() as db:
            db.execute("INSERT INTO runs (id, tender, category, status, created_at) VALUES (?, ?, ?, ?, ?)", (run.id, tender, category, run.status, run.created_at))
        return run

    def set_status(self, run_id: str, status: Status) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status = ? WHERE id = ?", (status, run_id))

    def set_progress(self, run_id: str, text: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET progress = ? WHERE id = ?", (text, run_id))

    def await_approval(self, run_id: str, estimate: Estimate) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status = 'awaiting', progress = NULL, estimate = ? WHERE id = ?", (estimate.model_dump_json(), run_id))

    def cancel(self, run_id: str, reason: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status = 'cancelled', progress = NULL, error = ?, finished_at = ? WHERE id = ?", (reason, now(), run_id))

    def rename(self, run_id: str, name: str) -> bool:
        with self.connect() as db:
            return db.execute("UPDATE runs SET tender = ? WHERE id = ?", (name, run_id)).rowcount > 0

    def finish(self, run_id: str, report_json: str, model_calls: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status = 'done', progress = NULL, estimate = NULL, report = ?, model_calls = ?, finished_at = ? WHERE id = ?", (report_json, model_calls, now(), run_id))

    def fail(self, run_id: str, error: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status = 'failed', progress = NULL, error = ?, finished_at = ? WHERE id = ?", (error, now(), run_id))

    def get(self, run_id: str) -> RunInfo | None:
        with self.connect() as db:
            row = db.execute(f"SELECT {COLUMNS} FROM runs WHERE id = ?", (run_id,)).fetchone()
        return RunInfo(**row) if row else None

    def report(self, run_id: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT report FROM runs WHERE id = ?", (run_id,)).fetchone()
        return row["report"] if row else None

    def all(self) -> list[RunInfo]:
        with self.connect() as db:
            rows = db.execute(f"SELECT {COLUMNS} FROM runs ORDER BY created_at DESC, rowid DESC").fetchall()
        return [RunInfo(**r) for r in rows]

    def delete(self, run_id: str) -> bool:
        with self.connect() as db:
            return db.execute("DELETE FROM runs WHERE id = ?", (run_id,)).rowcount > 0

    def fail_unfinished(self, reason: str) -> None:
        """Runs a restart interrupted can never finish; say so instead of leaving them 'running' forever."""
        with self.connect() as db:
            db.execute("UPDATE runs SET status = 'failed', error = ?, finished_at = ? WHERE status IN ('queued', 'awaiting', 'running')", (reason, now()))
