from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from app.config import number_setting

A = TypeVar("A")
B = TypeVar("B")

WORKERS = number_setting("LLM_WORKERS", 8)  # model calls wait on the network, so threads are enough; lower it when the service answers 429 (too many requests)


def run_parallel(work: Callable[[A], B], jobs: Iterable[A], workers: int = WORKERS) -> list[B]:
    """work(job) for every job at the same time, results in the order of the jobs."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(work, jobs))
