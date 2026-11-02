"""Lets a person say yes or no to a run's estimate before any money is spent.

A run asked to wait stops after the estimate. The page's Proceed and Cancel buttons answer it. If nobody answers in time the run is cancelled,
because a waiting run holds up every run behind it.
"""
from __future__ import annotations

import threading

from app.config import number_setting
from app.cost.estimate import Estimate
from app.db.runs import RunStore

WAIT_MINUTES = number_setting("APPROVAL_WAIT_MINUTES", 30)


class Declined(Exception):  # not an error: the person chose not to go on
    """The person cancelled the run, or never answered."""


class Approvals:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.waiting: set[str] = set()  # runs that must be approved before they spend anything
        self.answers: dict[str, bool] = {}
        self.signals: dict[str, threading.Event] = {}

    def require(self, run_id: str) -> None:
        with self.lock:
            self.waiting.add(run_id)
            self.signals[run_id] = threading.Event()

    def required(self, run_id: str) -> bool:
        with self.lock:
            return run_id in self.waiting

    def answer(self, run_id: str, yes: bool) -> None:
        with self.lock:
            self.answers[run_id] = yes
            signal = self.signals.get(run_id)
        if signal:
            signal.set()

    def wait(self, run_id: str, seconds: float) -> bool:
        """True if the person said yes. No answer in time counts as no."""
        with self.lock:
            signal = self.signals[run_id]
        signal.wait(seconds)
        with self.lock:
            yes = self.answers.pop(run_id, False)
            self.waiting.discard(run_id)
            self.signals.pop(run_id, None)
        return yes


APPROVALS = Approvals()


def ask_person(store: RunStore, run_id: str, estimate: Estimate, approvals: Approvals = APPROVALS, seconds: float = WAIT_MINUTES * 60) -> None:
    """Show the estimate on the run and wait for the answer. Returns if the person said yes; raises Declined if not."""
    store.await_approval(run_id, estimate)
    if not approvals.wait(run_id, seconds):
        raise Declined("Cancelled before any question was asked about the manufacturers' documents.")
    store.set_status(run_id, "running")
