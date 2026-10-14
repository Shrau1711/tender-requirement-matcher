from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.db.runs import now
from app.services.match import Status

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    run_id TEXT NOT NULL,
    key TEXT NOT NULL,
    decision TEXT NOT NULL,
    status TEXT,
    note TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, key)
)
"""


class Decision(BaseModel):
    """A person's decision on one row. None clears it."""

    key: str = Field(max_length=2000)
    decision: Literal["confirmed", "changed"] | None = None
    status: Status | None = None  # the status the person says is right, when they changed it
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def consistent(self) -> "Decision":
        if self.decision == "changed" and self.status is None:
            raise ValueError("A changed decision needs the status the person says is right.")
        if self.decision != "changed":
            self.status = None
        return self


class Review(Decision):
    updated_at: str


class ReviewStore:
    """What people decided about the rows of each run, kept next to the runs. It never changes the computed scores."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with self.connect() as db:
            db.execute(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def save(self, run_id: str, decisions: list[Decision]) -> None:
        with self.connect() as db:
            for d in decisions:
                if d.decision is None:
                    db.execute("DELETE FROM reviews WHERE run_id = ? AND key = ?", (run_id, d.key))
                else:
                    db.execute(
                        "INSERT INTO reviews (run_id, key, decision, status, note, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT (run_id, key) DO UPDATE SET decision = excluded.decision, status = excluded.status, note = excluded.note, updated_at = excluded.updated_at",
                        (run_id, d.key, d.decision, d.status, d.note, now()),
                    )

    def all(self, run_id: str) -> list[Review]:
        with self.connect() as db:
            rows = db.execute("SELECT key, decision, status, note, updated_at FROM reviews WHERE run_id = ? ORDER BY key", (run_id,)).fetchall()
        return [Review(**r) for r in rows]

    def clear(self, run_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM reviews WHERE run_id = ?", (run_id,))
