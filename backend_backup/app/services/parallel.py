from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

A = TypeVar("A")
B = TypeVar("B")

WORKERS = 8  # model calls spend their time waiting for the network, so threads are enough


def run_parallel(work: Callable[[A], B], jobs: Iterable[A], workers: int = WORKERS) -> list[B]:
    """work(job) for every job at the same time, results in the order of the jobs."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(work, jobs))